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
        toolsets=toolsets,
    )

    @agent.system_prompt(dynamic=True)
    def _system_prompt(_ctx: RunContext[GrugDeps]) -> str:  # noqa: ARG001
        """Re-evaluate on every run (dynamic=True) so `now` is always current."""
        return SYSTEM_PROMPT.format(now=datetime.now(timezone.utc).isoformat())

    # Register tool groups — each follows the register_*_tools(agent) pattern.
    from grug.agent.tools.character_tools import register_character_tools
    from grug.agent.tools.glossary_tools import register_glossary_tools
    from grug.agent.tools.rag_tools import register_rag_tools
    from grug.agent.tools.scheduling_tools import register_scheduling_tools

    register_rag_tools(agent)
    register_scheduling_tools(agent)
    register_glossary_tools(agent)
    register_character_tools(agent)

    @agent.tool
    async def get_current_time(ctx: RunContext[GrugDeps]) -> str:
        """Return the current time as a timezone-aware ISO-8601 string.

        The time is in the guild's configured local timezone (e.g. US/Eastern),
        falling back to the server default timezone.  Use this whenever you need
        to compute a future datetime from a relative expression like "in 5 minutes"
        or "in two hours", and when telling the user what time something will happen.
        The returned value includes the UTC offset so it is safe to pass directly
        to scheduling tools.
        """
        import zoneinfo

        from grug.config.settings import get_settings
        from grug.db.models import GuildConfig
        from grug.db.session import get_session_factory
        from sqlalchemy import select

        tz_name: str = get_settings().default_timezone
        try:
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(GuildConfig.timezone).where(
                        GuildConfig.guild_id == ctx.deps.guild_id
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    tz_name = row
        except Exception:
            logger.exception(
                "get_current_time: failed to load guild timezone, using default"
            )

        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            logger.warning(
                "get_current_time: unknown timezone %r, falling back to UTC", tz_name
            )
            tz = zoneinfo.ZoneInfo("UTC")

        return datetime.now(tz).isoformat()

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
        self,
        guild_id: int,
        channel_id: int,
        context_cutoff: datetime | None = None,
    ) -> list[ModelRequest | ModelResponse]:
        """Load recent messages, archiving overflow to RAG when the window fills.

        If *context_cutoff* is set, messages older than that timestamp are
        excluded from the context window entirely (they still exist in the DB
        but Grug won't see them).
        """
        settings = get_settings()
        factory = get_session_factory()

        # Base filter shared by all queries in this method.
        base_filters = [
            ConversationMessage.guild_id == guild_id,
            ConversationMessage.channel_id == channel_id,
            ConversationMessage.archived.is_(False),
        ]
        if context_cutoff is not None:
            base_filters.append(ConversationMessage.created_at >= context_cutoff)

        async with factory() as session:
            count_result = await session.execute(
                select(func.count(ConversationMessage.id)).where(*base_filters)
            )
            total = count_result.scalar() or 0

            overflow = total - self._context_window
            if overflow >= settings.agent_history_archive_batch:
                overflow_result = await session.execute(
                    select(ConversationMessage)
                    .where(*base_filters)
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
                .where(*base_filters)
                .order_by(ConversationMessage.created_at.desc())
                .limit(self._context_window)
            )
            rows = list(reversed(recent_result.scalars().all()))

        messages: list[ModelRequest | ModelResponse] = []

        # Inject a voice reminder at the top of history so the model sees
        # the correct style even when stale history contains bad examples.
        messages.append(
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content=(
                            "[SYSTEM REMINDER] You are Grug. Speak like an orc. "
                            "No emoji. No markdown. No contractions. No 'I' or 'me'. "
                            "Say 'Grug' instead. Keep it short and punchy. "
                            "Never use a person name, display name, or username. "
                            "Always say 'you' or 'friend' instead. No exceptions."
                        )
                    )
                ]
            )
        )
        messages.append(
            ModelResponse(
                parts=[
                    TextPart(
                        content="Grug understand! Grug always talk like Grug. No fancy stuff!"
                    )
                ]
            )
        )

        for row in rows:
            if row.role == "user":
                messages.append(
                    ModelRequest(parts=[UserPromptPart(content=row.content)])
                )
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
        is_passive: bool = False,
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
                    is_passive=is_passive,
                )
            )
            await session.commit()

    async def save_passive_message(
        self,
        guild_id: int,
        channel_id: int,
        content: str,
        author_id: int | None = None,
        author_name: str | None = None,
    ) -> None:
        """Persist a message that Grug observed but did not respond to.

        These passive messages are included in the context window so Grug
        remains aware of the conversation even when not directly addressed.
        """
        try:
            await self._save_message(
                guild_id,
                channel_id,
                "user",
                content,
                author_id,
                author_name,
                is_passive=True,
            )
        except Exception:
            logger.exception(
                "Failed to save passive message guild=%s channel=%s",
                guild_id,
                channel_id,
            )

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
        context_cutoff: datetime | None = None,
    ) -> str:
        """Process a user message and return Grug's response."""
        try:
            # Load history BEFORE saving the current message so the incoming
            # message isn't included in message_history AND the run() call.
            history = await self._load_history(guild_id, channel_id, context_cutoff)
            await self._save_message(
                guild_id, channel_id, "user", message, user_id, username
            )
        except Exception as exc:
            logger.exception("Failed to load/save conversation history: %s", exc)
            history = []

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

        try:
            await self._save_message(guild_id, channel_id, "assistant", response_text)
        except Exception as exc:
            logger.exception("Failed to save assistant message: %s", exc)

        return response_text
