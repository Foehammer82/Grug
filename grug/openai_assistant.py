"""Integration to OpenAI for interacting with the OpenAI API. """

import asyncio
import inspect
import json
from collections.abc import Callable

from loguru import logger
from openai import AsyncOpenAI, OpenAI
from openai.types.beta import Thread
from openai.types.beta.threads import RequiredActionFunctionToolCall

from grug.db import async_session
from grug.models import AssistantResponse, Player
from grug.settings import settings
from grug.utils.aon import search_aon
from grug.utils.food import get_food_history, send_discord_food_reminder

# TODO: setup monitor/log/handle openai rate limits:
#       https://platform.openai.com/docs/guides/rate-limits/rate-limits-in-headers


class Assistant:
    """https://platform.openai.com/docs/assistants/overview?context=with-streaming"""

    response_wait_seconds: float = 0.5

    def __init__(self, assistant_functions: list[Callable] | None = None):
        self.async_client = AsyncOpenAI(api_key=settings.openai_key.get_secret_value())
        self.sync_client = OpenAI(api_key=settings.openai_key.get_secret_value())
        self._tools = (
            {str(tool.__name__): tool for tool in assistant_functions}
            if assistant_functions
            else {}
        )

        # Create, or Update and Retrieve the assistant
        assistants = {a.name: a.id for a in self.sync_client.beta.assistants.list().data}
        bot_name = settings.bot_name.lower()

        # Configure tools
        assistant_functions = self._get_assistant_tools()

        if bot_name not in assistants:
            self.assistant = self.sync_client.beta.assistants.create(
                name=bot_name,
                instructions=settings.bot_instructions,
                model=settings.openai_model,
                tools=assistant_functions,
            )
        else:
            self.assistant = self.sync_client.beta.assistants.update(
                assistant_id=assistants[bot_name],
                instructions=settings.bot_instructions,
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
        player: Player,
    ) -> AssistantResponse:
        """
        Send a direct message from a player to the assistant and get the response.

        Args:
            message (str): The message to send to the assistant.
            player (Player): The player sending the message.

        Returns:
            AssistantResponse: The response from the assistant.
        """
        if player.assistant_thread_id is None:
            thread = await self.async_client.beta.threads.create()

            # Update the user with the thread_id
            async with async_session() as session:
                player.assistant_thread_id = thread.id
                session.add(player)
                await session.commit()
        else:
            thread = await self.async_client.beta.threads.retrieve(
                thread_id=player.assistant_thread_id
            )

        return await self._send_message(
            thread=thread,
            message=message,
        )

    async def send_group_message(
        self,
        message: str,
        player: Player,
        thread_id: str | None = None,
    ) -> AssistantResponse:
        """
        Send a message to a group thread and get the response.

        Args:
            message (str): The message to send to the assistant.
            thread_id (str): The thread_id of the group thread.
            player (Player): The player sending the message.

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
                f"This message is from {player.discord_username}.  The following is their message:"
                f"\n{message}"
                "\n\n[AI should not factor the person's name into its response.]"
                "\n[AI should not state that they received a message from the person.]"
            ),
        )

    async def _send_message(self, thread: Thread, message: str):
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
            run = await self.async_client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )

            if run.status == "failed":
                raise Exception(
                    f"Run failed with message: {run.last_error.code}: {run.last_error.message}"
                )

            elif run.status == "in_progress" or run.status == "queued":
                await asyncio.sleep(self.response_wait_seconds)

            elif run.status == "requires_action":
                if (
                    tool_calls := run.required_action.submit_tool_outputs.tool_calls
                ) is not None:
                    run = await self.async_client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run.id,
                        tool_outputs=[
                            await self._call_tool_function(tool_call)
                            for tool_call in tool_calls
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
                                arg: {
                                    "type": openai_type_map[
                                        function_arg_spec.annotations[arg]
                                    ]
                                }
                                for arg in function_arg_spec.args
                            },
                            "required": (
                                function_arg_spec.args[: -len(function_arg_spec.defaults)]
                                if function_arg_spec.defaults
                                else []
                            ),
                        },
                    },
                }
            )

        return tools

    async def _call_tool_function(self, tool_call: RequiredActionFunctionToolCall):
        """Call the tool function and return the output."""
        logger.info(f"Calling tool function: {tool_call.function.name}")

        try:
            tool_callable = self._tools[tool_call.function.name]
            function_args = json.loads(tool_call.function.arguments)

            for arg in inspect.getfullargspec(self._tools[tool_call.function.name]).args:
                if arg not in function_args:
                    raise ValueError(
                        f"Missing argument: {arg} from function call {tool_callable.__name__}"
                    )

            if inspect.iscoroutinefunction(tool_callable):
                tools_response = await tool_callable(**function_args)
            elif inspect.isfunction(tool_callable):
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
            return {
                "tool_call_id": tool_call.id,
                "output": str(e),
            }


assistant = Assistant(
    assistant_functions=[
        search_aon,
        get_food_history,
        send_discord_food_reminder,
    ]
)
