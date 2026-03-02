"""Scheduling, calendar, and reminder tools for the Grug agent.

Registers ``create_calendar_event``, ``list_calendar_events``,
``create_reminder``, and ``create_scheduled_task`` on the pydantic-ai Agent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import select

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_scheduling_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register all scheduling-related tools on *agent*."""

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

        from grug.db.models import CalendarEvent
        from grug.db.session import get_session_factory
        from grug.utils import ensure_guild

        await ensure_guild(ctx.deps.guild_id)
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
        return (
            f"Calendar event '{title}' created (ID: {event_id}, starts {start_time})."
        )

    @agent.tool
    async def list_calendar_events(ctx: RunContext[GrugDeps], limit: int = 10) -> str:
        """List upcoming calendar events for this guild."""
        from datetime import datetime, timezone

        from grug.db.models import CalendarEvent
        from grug.db.session import get_session_factory

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
        """Schedule a one-time action for the user at the specified time (ISO-8601).

        ``message`` is the prompt that will be sent to Grug at the scheduled time —
        it should capture what the user actually wants done (e.g. "tell me a joke",
        "roll initiative for the party", "post the session recap").  Grug will
        execute that prompt in the channel where the reminder was created.

        Always use UTC for ``remind_at`` (e.g. add the ``+00:00`` suffix).  If the
        caller omits timezone info, UTC is assumed.
        """
        from datetime import datetime, timezone

        from grug.db.models import Reminder
        from grug.db.session import get_session_factory
        from grug.scheduler.manager import add_date_job
        from grug.scheduler.tasks import send_reminder
        from grug.utils import ensure_guild

        await ensure_guild(ctx.deps.guild_id)
        target_user = user_id if user_id is not None else ctx.deps.user_id
        run_dt = datetime.fromisoformat(remind_at)
        # Ensure the datetime is timezone-aware; treat naive datetimes as UTC.
        if run_dt.tzinfo is None:
            run_dt = run_dt.replace(tzinfo=timezone.utc)
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
            args=[
                reminder_id,
                ctx.deps.guild_id,
                ctx.deps.channel_id,
                target_user,
                message,
            ],
        )
        return f"Reminder set for {run_dt.isoformat()} (ID: {reminder_id})."

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
        from grug.db.session import get_session_factory
        from grug.scheduler.manager import add_cron_job
        from grug.scheduler.tasks import run_scheduled_prompt
        from grug.utils import ensure_guild

        await ensure_guild(ctx.deps.guild_id)
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
        return f"Recurring task '{name}' scheduled ({cron_expression}) — ID: {task_id}."
