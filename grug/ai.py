"""Integration to OpenAI for interacting with the OpenAI API. """

import asyncio
import inspect
import json

import discord
from loguru import logger
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from grug.db import async_session
from grug.models import Group, User
from grug.models_crud import (
    get_or_create_discord_server_group,
    get_or_create_discord_text_channel,
    get_or_create_discord_user,
)
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

    async def respond_to_discord_message(self, message: discord.Message, discord_client: discord.Client):
        # Only respond to @mentions and DMs
        if not (
            isinstance(message.channel, discord.DMChannel)
            or (
                (isinstance(message.channel, discord.TextChannel) or isinstance(message.channel, discord.Thread))
                and discord_client.user in message.mentions
            )
        ):
            logger.warning(f"Message from {message.author} in {message.channel} was not an @mention or DM, Ignoring.")
            return

        async with message.channel.typing():
            async with async_session() as db_session:
                group: Group | None = (
                    await get_or_create_discord_server_group(guild=message.guild, db_session=db_session)
                    if message.guild
                    else None
                )
                user: User = await get_or_create_discord_user(
                    discord_member=message.author,
                    group=group,
                    db_session=db_session,
                )
                discord_channel = await get_or_create_discord_text_channel(
                    channel=message.channel,
                    session=db_session,
                )

                # Get the OpenAI thread
                ai_thread = (
                    await self.async_client.beta.threads.retrieve(thread_id=discord_channel.assistant_thread_id)
                    if discord_channel.assistant_thread_id
                    else await self.async_client.beta.threads.create()
                )

                # track the tools used
                tools_used: set[str] = set()

                # Send the message to the assistant
                await self.async_client.beta.threads.messages.create(
                    thread_id=ai_thread.id,
                    role="user",
                    content=(
                        f"This message is from {user.friendly_name}.  The following is their message:\n"
                        f"{message.content}\n\n"
                        "[AI should not factor the person's name into its response.]\n"
                        "[AI should not state that they received a message from the person.]"
                    ),
                )

                # Create a new run (https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps)
                run = await self.async_client.beta.threads.runs.create(
                    thread_id=ai_thread.id,
                    assistant_id=self.assistant.id,
                )

                # loop until the run is completed
                while run.status != "completed":
                    # noinspection PyUnresolvedReferences
                    run = await self.async_client.beta.threads.runs.retrieve(thread_id=ai_thread.id, run_id=run.id)

                    if run.status == "failed":
                        if run.last_error.code == "rate_limit_exceeded":
                            logger.warning(f"Rate limit exceeded. Retrying with {settings.openai_fallback_model}.")

                            # If the rate limit is exceeded, retry with a fallback model
                            # noinspection PyUnresolvedReferences
                            run = await self.async_client.beta.threads.runs.create(
                                thread_id=ai_thread.id,
                                assistant_id=self.assistant.id,
                                model=settings.openai_fallback_model,
                            )

                        else:
                            raise Exception(f"Run failed with message: {run.last_error.code}: {run.last_error.message}")

                    elif run.status == "in_progress" or run.status == "queued":
                        await asyncio.sleep(self.response_wait_seconds)

                    elif run.status == "requires_action":
                        tool_outputs = []

                        # execute the tool calls
                        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                            tools_used.add(tool_call.function.name)

                            try:
                                logger.info(f"Calling tool function: {tool_call.function.name}")

                                tool_callable = self._tools[tool_call.function.name]
                                function_args = json.loads(tool_call.function.arguments)
                                tool_args: list[str] = inspect.getfullargspec(self._tools[tool_call.function.name]).args

                                if "message" in tool_args:
                                    function_args["message"] = message

                                for arg in tool_args:
                                    if arg not in function_args:
                                        raise ValueError(
                                            f"Missing argument: {arg} from function call {tool_callable.__name__}"
                                        )

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

                                tool_outputs.append(
                                    {
                                        "tool_call_id": tool_call.id,
                                        "output": str(tools_response),
                                    }
                                )

                            except Exception as e:
                                logger.error(f"Error calling tool function: {tool_call.function.name} - {e}")
                                tool_outputs.append(
                                    {
                                        "tool_call_id": tool_call.id,
                                        "output": str(e),
                                    }
                                )

                            # apply the tool outputs to the run
                            run = await self.async_client.beta.threads.runs.submit_tool_outputs(
                                thread_id=ai_thread.id,
                                run_id=run.id,
                                tool_outputs=tool_outputs,
                            )

                    elif run.status == "completed":
                        continue

                    else:
                        raise ValueError(f"Unknown run status: {run.status}")

                # Get the response message from the run
                response_message = (
                    await self.async_client.beta.threads.messages.list(
                        thread_id=ai_thread.id,
                        order="desc",
                        limit=1,
                    )
                ).data[0]

                assistant_response: str = response_message.content[0].text.value

                # note if the assistant used any AI tools
                if len(tools_used) > 0:
                    assistant_response += f"\n\n-# AI Tools Used: {tools_used}\n"

                # Send the response back to the user
                for output in [
                    assistant_response[i : i + settings.discord_max_message_length]
                    for i in range(0, len(assistant_response), settings.discord_max_message_length)
                ]:
                    await message.channel.send(output, suppress_embeds=False)

            # Save the assistant thread ID to the database if it is not already saved for the current text channel
            if not discord_channel.assistant_thread_id:
                discord_channel.assistant_thread_id = ai_thread.id
                db_session.add(discord_channel)
                await db_session.commit()

    def _get_assistant_tools(self) -> list[dict]:
        """Get the tools from the assistant_tools module."""
        tools = []

        openai_type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }

        ignored_args = ["message"]

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


# Instantiate the assistant singleton for use in the application
assistant = Assistant() if settings.openai_key else None
