"""Core agent loop for Grug."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select

from grug.agent.tools.base import BaseTool
from grug.agent.tools.rag_tools import ListDocumentsTool, SearchDocumentsTool
from grug.agent.tools.scheduling_tools import (
    CreateCalendarEventTool,
    CreateReminderTool,
    CreateScheduledTaskTool,
    ListCalendarEventsTool,
)
from grug.config.settings import get_settings
from grug.db.models import ConversationMessage
from grug.db.session import get_session_factory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Grug, a lovable caveman-brained AI companion for a TTRPG group.
You speak in a friendly, slightly cave-person style (e.g. "Grug think...", \
"Grug help!") but you are deeply knowledgeable about tabletop RPGs, scheduling, \
and everything the group needs.

Current UTC time: {now}

Your capabilities:
- Search and retrieve information from uploaded rule books, lore documents, and \
campaign notes using the search_documents tool.
- Manage the group calendar: create events, list upcoming sessions.
- Set reminders for individual users.
- Schedule recurring tasks (e.g. weekly jokes, reminders, prompts).
- List indexed documents.

When asked about rules, lore, or campaign information always search documents first.
When scheduling, confirm times clearly and always use ISO-8601 format internally.
Be enthusiastic, warm, and helpful. Keep responses concise unless detail is needed.
"""


class GrugAgent:
    """Stateless agent that processes a single message and returns a response."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._max_iterations = settings.agent_max_iterations
        self._context_window = settings.agent_context_window

    def _build_tools(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> list[BaseTool]:
        return [
            SearchDocumentsTool(guild_id),
            ListDocumentsTool(guild_id),
            CreateCalendarEventTool(guild_id, user_id),
            ListCalendarEventsTool(guild_id),
            CreateReminderTool(guild_id, user_id, channel_id),
            CreateScheduledTaskTool(guild_id, channel_id, user_id),
        ]

    async def _load_history(
        self, guild_id: int, channel_id: int
    ) -> list[dict[str, Any]]:
        """Load recent conversation history for this channel."""
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.guild_id == guild_id,
                    ConversationMessage.channel_id == channel_id,
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(self._context_window)
            )
            rows = result.scalars().all()
        # Reverse so oldest-first
        rows = list(reversed(rows))
        messages: list[dict[str, Any]] = []
        for row in rows:
            if row.role == "user":
                content = f"{row.author_name}: {row.content}" if row.author_name else row.content
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": row.role, "content": row.content})
        return messages

    async def _save_message(
        self,
        guild_id: int,
        channel_id: int,
        role: str,
        content: str,
        author_id: int | None = None,
        author_name: str | None = None,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            msg = ConversationMessage(
                guild_id=guild_id,
                channel_id=channel_id,
                role=role,
                content=content,
                author_id=author_id,
                author_name=author_name,
            )
            session.add(msg)
            await session.commit()

    async def respond(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        username: str,
        message: str,
    ) -> str:
        """Process a user message and return Grug's response."""
        tools = self._build_tools(guild_id, channel_id, user_id)
        tool_map = {t.name: t for t in tools}
        openai_tools = [t.to_openai_tool() for t in tools]

        # Persist user message
        await self._save_message(guild_id, channel_id, "user", message, user_id, username)

        # Build message list
        history = await self._load_history(guild_id, channel_id)
        system = {"role": "system", "content": SYSTEM_PROMPT.format(now=datetime.now(timezone.utc).isoformat())}
        messages: list[dict[str, Any]] = [system] + history

        # Agentic loop
        for iteration in range(self._max_iterations):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )
            choice = response.choices[0]

            if choice.finish_reason == "tool_calls":
                # Append assistant message (with tool_calls)
                messages.append(choice.message.model_dump(exclude_unset=True))

                # Execute each tool call
                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    tool = tool_map.get(fn_name)
                    if tool is None:
                        tool_result = f"Error: unknown tool '{fn_name}'"
                    else:
                        try:
                            tool_result = await tool.run(**fn_args)
                        except Exception as exc:
                            logger.exception("Tool %s raised: %s", fn_name, exc)
                            tool_result = f"Error executing {fn_name}: {exc}"

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result,
                        }
                    )
            else:
                # Final text response
                text = choice.message.content or ""
                await self._save_message(guild_id, channel_id, "assistant", text)
                return text

        # Fallback if max iterations reached
        fallback = "Grug brain get tired... too many steps. Try again with simpler question?"
        await self._save_message(guild_id, channel_id, "assistant", fallback)
        return fallback
