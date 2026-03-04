"""Core agent — builds the pydantic-ai Agent and manages conversation history.

Tools are registered via ``register_*_tools()`` functions in the
``grug.agent.tools`` sub-package; this module is kept focused on agent
construction and the ``GrugAgent`` orchestration wrapper.
"""

import logging
from dataclasses import dataclass, field
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
from grug.llm_usage import CallType, record_llm_usage
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
    default_ttrpg_system: str | None = None
    # Pre-loaded campaign summary injected into the system prompt.
    campaign_context: str | None = None
    # Files to DM to the user after the response is sent.
    # Populated by agent tools (e.g. export_character_pdf_tool).
    # Each entry is (filename, pdf_bytes).
    _pending_dm_files: list[tuple[str, bytes]] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Result returned by :meth:`GrugAgent.respond`."""

    text: str
    #: Files the bot should DM to the requesting user.
    dm_files: list[tuple[str, bytes]] = field(default_factory=list)


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
    def _system_prompt(ctx: RunContext[GrugDeps]) -> str:
        """Re-evaluate on every run (dynamic=True) so `now` is always current."""
        default_system = ctx.deps.default_ttrpg_system
        if default_system:
            default_system_line = (
                f"This server default game system: {default_system}. "
                "Grug know this. Grug use this for all rule lookups unless "
                "friend ask about different game."
            )
        else:
            default_system_line = ""
        campaign_ctx = ctx.deps.campaign_context
        if campaign_ctx:
            campaign_context_line = (
                f"\nCAMPAIGN CONTEXT (this channel):\n{campaign_ctx}\n"
            )
        else:
            campaign_context_line = ""
        return SYSTEM_PROMPT.format(
            now=datetime.now(timezone.utc).isoformat(),
            default_ttrpg_system_line=default_system_line,
            campaign_context_line=campaign_context_line,
        )

    # Register tool groups — each follows the register_*_tools(agent) pattern.
    from grug.agent.tools.banking_tools import register_banking_tools
    from grug.agent.tools.campaign_tools import register_campaign_tools
    from grug.agent.tools.character_tools import register_character_tools
    from grug.agent.tools.glossary_tools import register_glossary_tools
    from grug.agent.tools.rag_tools import register_rag_tools
    from grug.agent.tools.rules_tools import register_rules_tools
    from grug.agent.tools.scheduling_tools import register_scheduling_tools

    from grug.agent.tools.notes_tools import register_notes_tools
    from grug.agent.tools.session_notes_tools import register_session_notes_tools

    register_rag_tools(agent)
    register_scheduling_tools(agent)
    register_glossary_tools(agent)
    register_character_tools(agent)
    register_campaign_tools(agent)
    register_banking_tools(agent)
    register_rules_tools(agent)
    register_notes_tools(agent)
    register_session_notes_tools(agent)

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

    async def _fetch_notes(
        self, guild_id: int, user_id: int, is_dm_session: bool
    ) -> str | None:
        """Fetch the relevant notes content for this session, or None if empty."""
        from grug.db.models import GrugNote

        factory = get_session_factory()
        try:
            async with factory() as session:
                if is_dm_session:
                    result = await session.execute(
                        select(GrugNote).where(
                            GrugNote.user_id == user_id,
                            GrugNote.guild_id.is_(None),
                        )
                    )
                else:
                    result = await session.execute(
                        select(GrugNote).where(
                            GrugNote.guild_id == guild_id,
                            GrugNote.user_id.is_(None),
                        )
                    )
                note = result.scalar_one_or_none()
        except Exception:
            logger.exception(
                "Failed to fetch notes for guild=%s user=%s", guild_id, user_id
            )
            return None

        if note is None or not note.content.strip():
            return None
        return note.content

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
                # Prefix with the speaker's name so Grug knows who said what
                # in multi-user channels.
                prefix = f"{row.author_name}: " if row.author_name else ""
                messages.append(
                    ModelRequest(
                        parts=[UserPromptPart(content=f"{prefix}{row.content}")]
                    )
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
    ) -> AgentResponse:
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

        # Inject notes (guild-scoped or personal) into the history so Grug
        # always has them visible at the top of his context window.
        notes_content = await self._fetch_notes(guild_id, user_id, is_dm_session)
        if notes_content:
            notes_messages: list[ModelRequest | ModelResponse] = [
                ModelRequest(
                    parts=[
                        UserPromptPart(
                            content=(
                                f"[GRUG NOTES — read before responding]\n"
                                f"{notes_content}\n"
                                "[END NOTES]"
                            )
                        )
                    ]
                ),
                ModelResponse(
                    parts=[TextPart(content="Grug read notes. Grug remember.")]
                ),
            ]
            # Insert after the voice-reminder exchange (first two items) so
            # notes appear before the actual conversation history.
            history = history[:2] + notes_messages + history[2:]

        # Pre-load the guild's default TTRPG system so the agent can act on
        # it immediately without asking the user which game they play.
        default_ttrpg_system: str | None = None
        try:
            from grug.db.models import GuildConfig as _GuildConfig
            from grug.db.session import get_session_factory as _get_session_factory
            from sqlalchemy import select as _select

            _factory = _get_session_factory()
            async with _factory() as _session:
                _result = await _session.execute(
                    _select(_GuildConfig.default_ttrpg_system).where(
                        _GuildConfig.guild_id == guild_id
                    )
                )
                default_ttrpg_system = _result.scalar_one_or_none()
        except Exception:
            logger.warning("Failed to load default_ttrpg_system for guild %d", guild_id)

        # Pre-load campaign details so the agent knows what campaign and
        # characters are active in this channel without needing a tool call.
        campaign_context: str | None = None
        if campaign_id is not None:
            try:
                from grug.db.models import Campaign as _Campaign
                from grug.db.models import Character as _Character

                _factory2 = get_session_factory()
                async with _factory2() as _session2:
                    _campaign = (
                        await _session2.execute(
                            select(_Campaign).where(_Campaign.id == campaign_id)
                        )
                    ).scalar_one_or_none()
                    if _campaign is not None:
                        _chars = (
                            (
                                await _session2.execute(
                                    select(_Character).where(
                                        _Character.campaign_id == campaign_id
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        char_lines: list[str] = []
                        for _c in _chars:
                            _sd = _c.structured_data or {}
                            _level = _sd.get("level", "?")
                            _ancestry = _sd.get("ancestry") or _sd.get("race") or ""
                            _cls = _sd.get("class") or _sd.get("classes") or ""
                            if isinstance(_cls, list):
                                _cls = "/".join(str(x) for x in _cls)
                            _detail = f"Lvl {_level}"
                            if _cls:
                                _detail += f" {_cls}"
                            if _ancestry:
                                _detail += f" {_ancestry}"
                            char_lines.append(f"  - {_c.name} ({_detail})")
                        _chars_text = (
                            "\n".join(char_lines) if char_lines else "  (none yet)"
                        )
                        _status = "active" if _campaign.is_active else "inactive"
                        campaign_context = (
                            f"Campaign name: {_campaign.name}\n"
                            f"Game system: {_campaign.system}\n"
                            f"Status: {_status}\n"
                            f"Characters:\n{_chars_text}"
                        )
            except Exception:
                logger.warning(
                    "Failed to load campaign context for campaign %d", campaign_id
                )

        deps = GrugDeps(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            username=username,
            campaign_id=campaign_id,
            active_character_id=active_character_id,
            is_dm_session=is_dm_session,
            default_ttrpg_system=default_ttrpg_system,
            campaign_context=campaign_context,
        )

        try:
            result = await get_agent().run(
                message,
                message_history=history,
                deps=deps,
            )
            response_text = result.output
            _usage = result.usage()
            await record_llm_usage(
                model=get_settings().anthropic_model,
                call_type=CallType.CHAT,
                input_tokens=_usage.request_tokens or 0,
                output_tokens=_usage.response_tokens or 0,
                guild_id=guild_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.exception("Agent run failed: %s", exc)
            response_text = "Grug brain confused... something go wrong. Try again?"

        try:
            await self._save_message(guild_id, channel_id, "assistant", response_text)
        except Exception as exc:
            logger.exception("Failed to save assistant message: %s", exc)

        return AgentResponse(
            text=response_text,
            dm_files=list(deps._pending_dm_files),
        )
