"""Core agent — builds the pydantic-ai Agent and manages conversation history.

Tools are registered via ``register_*_tools()`` functions in the
``grug.agent.tools`` sub-package; this module is kept focused on agent
construction and the ``GrugAgent`` orchestration wrapper.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from sqlalchemy import func, select

from grug.agent.prompt import SYSTEM_PROMPT
from grug.config.settings import get_settings
from grug.db.models import ConversationMessage
from grug.db.session import get_session_factory
from grug.rag.history_archiver import ConversationArchiver

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------


@dataclass
class GrugDeps:
    """Per-request dependencies injected into every agent tool."""

    guild_id: int
    channel_id: int
    user_id: int
    username: str
    campaign_id: int | None = None
    active_character_id: int | None = None
    is_dm_session: bool = False


# ------------------------------------------------------------------
# Agent construction
# ------------------------------------------------------------------


def _build_agent() -> Agent[GrugDeps, str]:
    """Construct the pydantic-ai Agent with all tools registered."""
    settings = get_settings()
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = AnthropicModel(settings.anthropic_model, provider=provider)

    from grug.agent.tools.mcp_tools import build_mcp_servers

    toolsets = build_mcp_servers() or None

    agent: Agent[GrugDeps, str] = Agent(
        model,
        deps_type=GrugDeps,
        output_type=str,
        system_prompt=SYSTEM_PROMPT.format(now=datetime.now(timezone.utc).isoformat()),
        toolsets=toolsets,
    )

    # Register tool groups — each follows the register_*_tools(agent) pattern.
    from grug.agent.tools.character_tools import register_character_tools
    from grug.agent.tools.glossary_tools import register_glossary_tools
    from grug.agent.tools.rag_tools import register_rag_tools
    from grug.agent.tools.scheduling_tools import register_scheduling_tools

    register_rag_tools(agent)
    register_scheduling_tools(agent)
    register_glossary_tools(agent)
    register_character_tools(agent)

    # Conversation history search (standalone — too small to extract).
    @agent.tool
    async def search_conversation_history(
        ctx: RunContext[GrugDeps], query: str, k: int = 3
    ) -> str:
        """Search archived conversation history for past events, decisions, and lore.

        Use when the user asks about something that may have happened in a previous
        session or earlier in the campaign.
        """
        archiver = ConversationArchiver()
        results = await archiver.search(
            ctx.deps.guild_id, ctx.deps.channel_id, query, k=k
        )
        if not results:
            return "No relevant conversation history found in the chronicles."
        parts = [
            f"[{i}] ({r['start_time']} → {r['end_time']}, {r['message_count']} messages):\n{r['summary']}"
            for i, r in enumerate(results, 1)
        ]
        return "📜 From the chronicles:\n\n" + "\n\n---\n\n".join(parts)

    return agent


_agent: Agent[GrugDeps, str] | None = None


def get_agent() -> Agent[GrugDeps, str]:
    """Return the shared pydantic-ai agent (created once, reused across requests)."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


# ------------------------------------------------------------------
# GrugAgent — thin wrapper with history persistence
# ------------------------------------------------------------------


class GrugAgent:
    """Manages conversation history and delegates to the pydantic-ai Agent."""

    def __init__(self) -> None:
        settings = get_settings()
        self._context_window: int = settings.agent_context_window

    async def _load_history(
        self, guild_id: int, channel_id: int
    ) -> list[ModelRequest | ModelResponse]:
        """Load recent messages, archiving overflow to RAG when the window fills."""
        settings = get_settings()
        factory = get_session_factory()

        async with factory() as session:
            count_result = await session.execute(
                select(func.count(ConversationMessage.id)).where(
                    ConversationMessage.guild_id == guild_id,
                    ConversationMessage.channel_id == channel_id,
                    ConversationMessage.archived.is_(False),
                )
            )
            total = count_result.scalar() or 0

            overflow = total - self._context_window
            if overflow >= settings.agent_history_archive_batch:
                overflow_result = await session.execute(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.guild_id == guild_id,
                        ConversationMessage.channel_id == channel_id,
                        ConversationMessage.archived.is_(False),
                    )
                    .order_by(ConversationMessage.created_at.asc())
                    .limit(overflow)
                )
                to_archive = overflow_result.scalars().all()
                if to_archive:
                    archive_dicts = [
                        {
                            "role": m.role,
                            "content": m.content,
                            "author_name": m.author_name,
                            "created_at": m.created_at.isoformat()
                            if m.created_at
                            else "",
                        }
                        for m in to_archive
                    ]
                    try:
                        archiver = ConversationArchiver()
                        await archiver.archive(guild_id, channel_id, archive_dicts)
                    except Exception:
                        logger.exception(
                            "Failed to archive conversation history — skipping"
                        )

                    for msg in to_archive:
                        msg.archived = True
                    await session.commit()

            recent_result = await session.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.guild_id == guild_id,
                    ConversationMessage.channel_id == channel_id,
                    ConversationMessage.archived.is_(False),
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(self._context_window)
            )
            rows = list(reversed(recent_result.scalars().all()))

        messages: list[ModelRequest | ModelResponse] = []
        for row in rows:
            if row.role == "user":
                content = (
                    f"{row.author_name}: {row.content}"
                    if row.author_name
                    else row.content
                )
                messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
            elif row.role == "assistant":
                messages.append(ModelResponse(parts=[TextPart(content=row.content)]))
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
        """Persist a single conversation message."""
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                ConversationMessage(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    role=role,
                    content=content,
                    author_id=author_id,
                    author_name=author_name,
                )
            )
            await session.commit()

    async def respond(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        username: str,
        message: str,
        campaign_id: int | None = None,
        active_character_id: int | None = None,
        is_dm_session: bool = False,
    ) -> str:
        """Process a user message and return Grug's response."""
        await self._save_message(
            guild_id, channel_id, "user", message, user_id, username
        )

        history = await self._load_history(guild_id, channel_id)
        deps = GrugDeps(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            username=username,
            campaign_id=campaign_id,
            active_character_id=active_character_id,
            is_dm_session=is_dm_session,
        )

        try:
            result = await get_agent().run(
                message,
                message_history=history,
                deps=deps,
            )
            response_text = result.output
        except Exception as exc:
            logger.exception("Agent run failed: %s", exc)
            response_text = "Grug brain confused... something go wrong. Try again?"

        await self._save_message(guild_id, channel_id, "assistant", response_text)
        return response_text
