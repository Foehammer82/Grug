"""Core agent using pydantic-ai with Anthropic Claude."""

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

from grug.config.settings import get_settings
from grug.db.models import ConversationMessage
from grug.db.session import get_session_factory
from grug.rag.history_archiver import ConversationArchiver

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
- Look up server-specific TTRPG terminology and campaign lore from this guild's \
glossary using the lookup_glossary_term tool.
- Add or update glossary terms (AI-owned entries only) when players define new terms \
or correct an existing definition, using the upsert_glossary_term tool.

When asked about rules, lore, or campaign information always search documents first, \
then check the glossary for any server-specific overrides on terminology.
When scheduling, confirm times clearly and always use ISO-8601 format internally.
If a player corrects you on what a term means in their campaign, call \
upsert_glossary_term to record it — but never overwrite a human-edited entry.
Be enthusiastic, warm, and helpful. Keep responses concise unless detail is needed.
"""


@dataclass
class GrugDeps:
    """Per-request dependencies injected into every agent tool."""

    guild_id: int
    channel_id: int
    user_id: int
    username: str


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

    # ------------------------------------------------------------------ tools
    @agent.tool
    async def search_documents(ctx: RunContext[GrugDeps], query: str, k: int = 5) -> str:
        """Search the guild's indexed documents using semantic similarity.

        Use when the user asks about rules, lore, or content from uploaded documents.
        """
        from grug.rag.retriever import DocumentRetriever

        retriever = DocumentRetriever()
        chunks = await retriever.search(ctx.deps.guild_id, query, k=k)
        if not chunks:
            return "No relevant documents found."
        parts = [
            f"[{i}] From **{c['filename']}** (chunk {c['chunk_index']}):\n{c['text']}"
            for i, c in enumerate(chunks, 1)
        ]
        return "\n\n---\n\n".join(parts)

    @agent.tool
    async def list_documents(ctx: RunContext[GrugDeps]) -> str:
        """List all documents that have been indexed for this server."""
        from grug.db.models import Document

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Document).where(Document.guild_id == ctx.deps.guild_id)
            )
            docs = result.scalars().all()
        if not docs:
            return "No documents have been indexed for this server yet."
        lines = ["Indexed documents:"]
        for doc in docs:
            desc = f" — {doc.description}" if doc.description else ""
            lines.append(f"• **{doc.filename}** ({doc.chunk_count} chunks){desc}")
        return "\n".join(lines)

    @agent.tool
    async def create_calendar_event(
        ctx: RunContext[GrugDeps],
        title: str,
        start_time: str,
        description: str | None = None,
        end_time: str | None = None,
        channel_id: int | None = None,
    ) -> str:
        """Create a calendar event for the guild. Times must be in ISO-8601 format."""
        from datetime import datetime

        from grug.db.models import CalendarEvent, GuildConfig

        await _ensure_guild(ctx.deps.guild_id)
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time) if end_time else None
        factory = get_session_factory()
        async with factory() as session:
            event = CalendarEvent(
                guild_id=ctx.deps.guild_id,
                title=title,
                description=description,
                start_time=start,
                end_time=end,
                channel_id=channel_id,
                created_by=ctx.deps.user_id,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            event_id = event.id
        return f"✅ Calendar event **{title}** created (ID: {event_id}, starts {start_time})."

    @agent.tool
    async def list_calendar_events(ctx: RunContext[GrugDeps], limit: int = 10) -> str:
        """List upcoming calendar events for this guild."""
        from datetime import datetime, timezone

        from grug.db.models import CalendarEvent

        factory = get_session_factory()
        now = datetime.now(timezone.utc)
        async with factory() as session:
            result = await session.execute(
                select(CalendarEvent)
                .where(
                    CalendarEvent.guild_id == ctx.deps.guild_id,
                    CalendarEvent.start_time >= now,
                )
                .order_by(CalendarEvent.start_time)
                .limit(limit)
            )
            events = result.scalars().all()
        if not events:
            return "No upcoming calendar events."
        lines = ["📅 Upcoming events:"]
        for ev in events:
            end_str = f" → {ev.end_time.isoformat()}" if ev.end_time else ""
            lines.append(f"• **{ev.title}** — {ev.start_time.isoformat()}{end_str}")
        return "\n".join(lines)

    @agent.tool
    async def create_reminder(
        ctx: RunContext[GrugDeps],
        message: str,
        remind_at: str,
        user_id: int | None = None,
    ) -> str:
        """Create a reminder that will be sent to the user at the specified time (ISO-8601)."""
        from datetime import datetime

        from grug.db.models import Reminder
        from grug.scheduler.manager import add_date_job
        from grug.scheduler.tasks import send_reminder

        await _ensure_guild(ctx.deps.guild_id)
        target_user = user_id if user_id is not None else ctx.deps.user_id
        run_dt = datetime.fromisoformat(remind_at)
        factory = get_session_factory()
        async with factory() as session:
            reminder = Reminder(
                guild_id=ctx.deps.guild_id,
                user_id=target_user,
                channel_id=ctx.deps.channel_id,
                message=message,
                remind_at=run_dt,
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            reminder_id = reminder.id

        add_date_job(
            send_reminder,
            run_date=run_dt,
            job_id=f"reminder_{reminder_id}",
            args=[reminder_id, ctx.deps.channel_id, target_user, message],
        )
        return f"⏰ Reminder set for {remind_at} (ID: {reminder_id})."

    @agent.tool
    async def create_scheduled_task(
        ctx: RunContext[GrugDeps],
        name: str,
        prompt: str,
        cron_expression: str,
    ) -> str:
        """Create a recurring task where Grug responds to a prompt on a cron schedule.

        Cron format: 'minute hour day month day_of_week' (5 fields, UTC).
        Example: '0 9 * * 5' = every Friday at 9:00 AM UTC.
        """
        from grug.db.models import ScheduledTask
        from grug.scheduler.manager import add_cron_job
        from grug.scheduler.tasks import run_scheduled_prompt

        await _ensure_guild(ctx.deps.guild_id)
        factory = get_session_factory()
        async with factory() as session:
            task = ScheduledTask(
                guild_id=ctx.deps.guild_id,
                channel_id=ctx.deps.channel_id,
                name=name,
                prompt=prompt,
                cron_expression=cron_expression,
                created_by=ctx.deps.user_id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        add_cron_job(
            run_scheduled_prompt,
            cron_expression=cron_expression,
            job_id=f"task_{task_id}",
            args=[task_id, ctx.deps.guild_id, ctx.deps.channel_id, prompt],
        )
        return f"🔁 Recurring task **{name}** scheduled ({cron_expression}) — ID: {task_id}."

    @agent.tool
    async def search_conversation_history(ctx: RunContext[GrugDeps], query: str, k: int = 3) -> str:
        """Search the archived conversation history for past events, decisions, and lore.

        Use when the user asks about something that may have happened in a previous
        session or earlier in the campaign (e.g. 'what did we decide about the dragon?',
        'what happened last time we visited the city?').
        """
        archiver = ConversationArchiver()
        results = await archiver.search(ctx.deps.guild_id, ctx.deps.channel_id, query, k=k)
        if not results:
            return "No relevant conversation history found in the chronicles."
        parts = [
            f"[{i}] ({r['start_time']} → {r['end_time']}, {r['message_count']} messages):\n{r['summary']}"
            for i, r in enumerate(results, 1)
        ]
        return "📜 From the chronicles:\n\n" + "\n\n---\n\n".join(parts)
    # ----------------------------------------------------------------- glossary
    from grug.agent.tools.glossary_tools import register_glossary_tools
    register_glossary_tools(agent)
    return agent


async def _ensure_guild(guild_id: int) -> None:
    """Ensure a GuildConfig row exists for this guild."""
    from grug.db.models import GuildConfig

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        if result.scalar_one_or_none() is None:
            session.add(GuildConfig(guild_id=guild_id))
            await session.commit()


_agent: Agent[GrugDeps, str] | None = None


def get_agent() -> Agent[GrugDeps, str]:
    """Return the shared pydantic-ai agent (created once, reused across requests)."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


class GrugAgent:
    """Thin wrapper around the pydantic-ai Agent that handles history persistence."""

    def __init__(self) -> None:
        settings = get_settings()
        self._context_window: int = settings.agent_context_window

    async def _load_history(
        self, guild_id: int, channel_id: int
    ) -> list[ModelRequest | ModelResponse]:
        """Load recent messages, archiving overflow to RAG history when the window fills."""
        settings = get_settings()
        factory = get_session_factory()

        async with factory() as session:
            # Count total unarchived messages for this channel.
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
                # Fetch the oldest overflow messages for archival.
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
                            "created_at": m.created_at.isoformat() if m.created_at else "",
                        }
                        for m in to_archive
                    ]
                    try:
                        archiver = ConversationArchiver()
                        await archiver.archive(guild_id, channel_id, archive_dicts)
                    except Exception:
                        logger.exception("Failed to archive conversation history — skipping")

                    # Mark rows archived regardless of whether summary succeeded.
                    for msg in to_archive:
                        msg.archived = True
                    await session.commit()

            # Load the most recent context_window unarchived messages.
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
                content = f"{row.author_name}: {row.content}" if row.author_name else row.content
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
    ) -> str:
        """Process a user message and return Grug's response."""
        await self._save_message(guild_id, channel_id, "user", message, user_id, username)

        history = await self._load_history(guild_id, channel_id)
        deps = GrugDeps(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            username=username,
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
