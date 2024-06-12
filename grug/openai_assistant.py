"""Integration to OpenAI for interacting with the OpenAI API. """

import asyncio
import inspect
import json

from loguru import logger
from openai import AsyncOpenAI, OpenAI
from openai.types.beta import Thread
from openai.types.beta.threads import RequiredActionFunctionToolCall
from pydantic import BaseModel

from grug.assistant_functions import get_assistant_functions
from grug.db import async_session
from grug.models import Group, User
from grug.settings import settings

# TODO: reconfigure the app so that there is a distinct assistant for each group.  this way we can have funciton tools
#       be aware of group specific information.

# TODO: setup monitor/log/handle openai rate limits:
#       https://platform.openai.com/docs/guides/rate-limits/rate-limits-in-headers


class AssistantResponse(BaseModel):
    """Pydantic model for an assistant response."""

    response: str
    thread_id: str


class Assistant:
    """Class for interacting with the OpenAI API."""

    def __init__(
        self,
        response_wait_seconds: float = 0.5,
    ):
        """
        Initialize the Assistant class.

        Args:
            response_wait_seconds (float, optional): The number of seconds to wait between checking the assistant's
                                                     response. Defaults to 0.5.
        """
        self.response_wait_seconds = response_wait_seconds
        self.async_client = AsyncOpenAI(api_key=settings.openai_key.get_secret_value())
        self.sync_client = OpenAI(api_key=settings.openai_key.get_secret_value())
        self._tools = {str(tool.__name__): tool for tool in get_assistant_functions()}

        # Create, or Update and Retrieve the assistant
        assistants = {a.name: a.id for a in self.sync_client.beta.assistants.list().data}
        bot_name = settings.openai_assistant_name.lower()

        # Configure tools
        assistant_functions = self._get_assistant_tools()

        if bot_name not in assistants:
            self.assistant = self.sync_client.beta.assistants.create(
                name=bot_name,
                instructions=settings.openai_assistant_instructions,
                model=settings.openai_model,
                tools=assistant_functions,
            )
        else:
            self.assistant = self.sync_client.beta.assistants.update(
                assistant_id=assistants[bot_name],
                instructions=settings.openai_assistant_instructions,
                model=settings.openai_model,
                tools=assistant_functions,
            )

    async def send_anonymous_message(
        self,
        message: str,
    ) -> AssistantResponse:
        """
        Send an anonymous message to the assistant and get the response.

        Args:
            message (str): The message to send to the assistant.

        Returns:
            AssistantResponse: The response from the assistant.
        """
        return await self._send_message(
            thread=await self.async_client.beta.threads.create(),
            message=message,
        )

    async def send_direct_message(
        self,
        message: str,
        user: User,
        session: async_session,
    ) -> AssistantResponse:
        """
        Send a direct message from a player to the assistant and get the response.

        Args:
            message (str): The message to send to the assistant.
            user (Player): The player sending the message.
            session (async_session): The session to use for database operations.

        Returns:
            AssistantResponse: The response from the assistant.
        """
        if user.assistant_thread_id is None:
            thread = await self.async_client.beta.threads.create()

            # Update the user with the thread_id
            user.assistant_thread_id = thread.id
            session.add(user)
            await session.commit()
        else:
            thread = await self.async_client.beta.threads.retrieve(thread_id=user.assistant_thread_id)

        return await self._send_message(
            thread=thread,
            message=message,
            user=user,
        )

    async def send_group_message(
        self,
        message: str,
        user: User,
        group: Group,
        thread_id: str | None = None,
    ) -> AssistantResponse:
        """
        Send a message to a group thread and get the response.

        Args:
            message (str): The message to send to the assistant.
            thread_id (str): The thread_id of the group thread.
            user (User): The player sending the message.
            group (Group): The group the player is in.

        Returns:
            AssistantResponse: The response from the assistant.
        """

        return await self._send_message(
            thread=(
                await self.async_client.beta.threads.retrieve(thread_id=thread_id)
                if thread_id
                else await self.async_client.beta.threads.create()
            ),
            message=(
                f"This message is from {user.friendly_name}.  The following is their message:"
                f"\n{message}"
                "\n\n[AI should not factor the person's name into its response.]"
                "\n[AI should not state that they received a message from the person.]"
            ),
            user=user,
            group=group,
        )

    async def _send_message(
        self,
        thread: Thread,
        message: str,
        user: User | None = None,
        group: Group | None = None,
    ) -> AssistantResponse:
        """
        Send a message to the assistant and get the response.

        Args:
            thread (Thread): The thread to send the message to.
            message (str): The message to send to the assistant.

        Returns:
            AssistantResponse: The response from the assistant.
        """
        await self.async_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message,
        )

        # Create a new run (https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps)
        run = await self.async_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant.id,
        )

        while run.status != "completed":
            run = await self.async_client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

            if run.status == "failed":
                raise Exception(f"Run failed with message: {run.last_error.code}: {run.last_error.message}")

            elif run.status == "in_progress" or run.status == "queued":
                await asyncio.sleep(self.response_wait_seconds)

            elif run.status == "requires_action":
                if (tool_calls := run.required_action.submit_tool_outputs.tool_calls) is not None:
                    run = await self.async_client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run.id,
                        tool_outputs=[
                            await self._call_tool_function(tool_call, user, group) for tool_call in tool_calls
                        ],
                    )

            elif run.status == "completed":
                continue

            else:
                raise ValueError(f"Unknown run status: {run.status}")

        # Get the response message from the run
        response_message = (
            await self.async_client.beta.threads.messages.list(
                thread_id=thread.id,
                order="desc",
                limit=1,
            )
        ).data[0]

        return AssistantResponse(
            response=response_message.content[0].text.value,
            thread_id=thread.id,
        )

    def _get_assistant_tools(self) -> list[dict]:
        """Get the tools from the assistant_tools module."""
        tools = []

        openai_type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }

        ignored_args = ["user", "group"]

        for function_name, function in self._tools.items():
            function_arg_spec = inspect.getfullargspec(function)

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "description": inspect.getdoc(function),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                arg: {"type": openai_type_map[function_arg_spec.annotations[arg]]}
                                for arg in function_arg_spec.args
                                if arg not in ignored_args
                            },
                            "required": (
                                [
                                    arg
                                    for arg in function_arg_spec.args[: -len(function_arg_spec.defaults)]
                                    if arg not in ignored_args
                                ]
                                if function_arg_spec.defaults
                                else []
                            ),
                        },
                    },
                }
            )

        return tools

    async def _call_tool_function(
        self,
        tool_call: RequiredActionFunctionToolCall,
        user: User | None = None,
        group: Group | None = None,
    ):
        """Call the tool function and return the output."""
        # TODO: evaluate running tools from as a distributed job using apschedulers job capabilities.
        #       - evaluate how much additional time this takes
        #       - evaluate if this will work well for scaling (the idea is to put as little computational overhead on
        #         the main app(s) as possible)
        # TODO: setup auditing on tool calls to track when the tools were called and if they raised errors or not, and
        #       details around what was passed to the tool and received back from the tool.

        logger.info(f"Calling tool function: {tool_call.function.name}")

        try:
            tool_callable = self._tools[tool_call.function.name]
            function_args = json.loads(tool_call.function.arguments)
            tool_args: list[str] = inspect.getfullargspec(self._tools[tool_call.function.name]).args

            # pass in the user object to the function if it's in the function's arguments
            if "user" in tool_args:
                function_args["user"] = user

            # pass in the group object to the function if it's in the function's arguments
            if "group" in tool_args:
                function_args["group"] = group

            for arg in tool_args:
                if arg not in function_args:
                    raise ValueError(f"Missing argument: {arg} from function call {tool_callable.__name__}")

            if inspect.iscoroutinefunction(tool_callable):
                # noinspection PyArgumentList
                tools_response = await tool_callable(**function_args)
            elif inspect.isfunction(tool_callable):
                # noinspection PyArgumentList
                tools_response = tool_callable(**function_args)
            else:
                raise ValueError(
                    f"Expected a function or coroutine function for {tool_callable.__name__}.  "
                    f"Got {type(tool_callable)}."
                )

            return {
                "tool_call_id": tool_call.id,
                "output": str(tools_response),
            }

        except Exception as e:
            logger.error(f"Error calling tool function: {tool_call.function.name} - {e}")
            return {
                "tool_call_id": tool_call.id,
                "output": str(e),
            }


# Instantiate the assistant singleton for use in the application
assistant = Assistant()
