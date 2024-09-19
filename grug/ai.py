"""Integration to OpenAI for interacting with the OpenAI API. """

import asyncio
import inspect
import json

from loguru import logger
from openai import AsyncOpenAI, OpenAI
from openai.types.beta.threads import RequiredActionFunctionToolCall
from pydantic import BaseModel

from grug.models import Group, User
from grug.settings import settings

# TODO: setup monitor/log/handle openai rate limits:
#       https://platform.openai.com/docs/guides/rate-limits/rate-limits-in-headers
# TODO: log/track cost/usage of openai to a table to track costs and usage (having a TTL based chat history log would
#       be nice too, to help with debugging and whatnot)
# TODO: configure file uploading for the assistant and load useful files for the assistant to use.
#       - pathfinder wonderful items list
#       - pathfinder spells list
#       - pathfinder wizard class information


class AssistantResponse(BaseModel):
    """Pydantic model for an assistant response."""

    response: str
    thread_id: str
    tools_used: set[str] = set()
    respond_ephemeraly: bool = False


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
        from grug.ai_functions import assistant_functions

        if not settings.openai_key:
            raise ValueError("OpenAI API key is required to use the Assistant class.")

        self.response_wait_seconds = response_wait_seconds
        self.async_client = AsyncOpenAI(api_key=settings.openai_key.get_secret_value())
        self.sync_client = OpenAI(api_key=settings.openai_key.get_secret_value())
        self._tools = {str(tool.__name__): tool for tool in assistant_functions}

        # Create, or Update and Retrieve the assistant
        assistants = {a.name: a.id for a in self.sync_client.beta.assistants.list().data}
        bot_name = settings.openai_assistant_name.lower() + "-" + settings.environment.lower()

        if bot_name not in assistants:
            self.assistant = self.sync_client.beta.assistants.create(
                name=bot_name,
                instructions=settings.openai_assistant_instructions,
                model=settings.openai_model,
                tools=self._get_assistant_tools(),
            )
        else:
            self.assistant = self.sync_client.beta.assistants.update(
                assistant_id=assistants[bot_name],
                instructions=settings.openai_assistant_instructions,
                model=settings.openai_model,
                tools=self._get_assistant_tools(),
            )

    async def send_message(
        self,
        message: str,
        user: User,
        group: Group | None = None,
        thread_id: str | None = None,
    ) -> AssistantResponse:
        """
        Send a message to the assistant and get the response.

        Args:
            message (str): The message to send to the assistant.
            user (User): The player sending the message.
            group (Group): The group the player is in.
            thread_id (str): The thread_id for the given message.

        Returns:
            AssistantResponse: The response from the assistant.
        """
        # Get the thread
        if thread_id:
            thread = await self.async_client.beta.threads.retrieve(thread_id=thread_id)
        else:
            thread = await self.async_client.beta.threads.create()

        # track the tools used
        tools_used: set[str] = set()

        # Send the message to the assistant
        await self.async_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=(
                f"This message is from {user.friendly_name}.  The following is their message:\n"
                f"{message}\n\n"
                "[AI should not factor the person's name into its response.]\n"
                "[AI should not state that they received a message from the person.]"
            ),
        )

        # Create a new run (https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps)
        run = await self.async_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant.id,
        )

        while run.status != "completed":
            # noinspection PyUnresolvedReferences
            run = await self.async_client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

            if run.status == "failed":
                if run.last_error.code == "rate_limit_exceeded":
                    logger.warning(f"Rate limit exceeded. Retrying with {settings.openai_fallback_model}.")

                    # If the rate limit is exceeded, retry with a fallback model
                    # noinspection PyUnresolvedReferences
                    run = await self.async_client.beta.threads.runs.create(
                        thread_id=thread.id,
                        assistant_id=self.assistant.id,
                        model=settings.openai_fallback_model,
                    )

                else:
                    raise Exception(f"Run failed with message: {run.last_error.code}: {run.last_error.message}")

            elif run.status == "in_progress" or run.status == "queued":
                await asyncio.sleep(self.response_wait_seconds)

            elif run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                if tool_calls:
                    # Add the tools used to the set of tools used
                    tools_used.union({tool_call.function.name for tool_call in tool_calls})

                    # execute the tool calls
                    # TODO: figure out how to toggle ephemeral responses
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
            response=response_message.content[0].text.value, thread_id=thread.id, tools_used=tools_used
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
assistant = Assistant() if settings.openai_key else None
