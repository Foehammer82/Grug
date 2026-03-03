"""Scheduling, calendar, and reminder tools for the Grug agent.

Registers ``create_calendar_event``, ``list_calendar_events``, and
``create_scheduled_task`` on the pydantic-ai Agent.
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
    async def create_scheduled_task(
        ctx: RunContext[GrugDeps],
        prompt: str,
        name: str | None = None,
        fire_at: str | None = None,
        cron_expression: str | None = None,
        user_id: int | None = None,
    ) -> str:
        """Create a scheduled task — either a one-shot reminder or a recurring automated prompt.

        Exactly one of ``fire_at`` or ``cron_expression`` must be provided:

        * **One-shot** (``fire_at``): fires once at the given ISO-8601 datetime and is
          then disabled.  Always use UTC (add ``+00:00``).  If no timezone info is
          present, UTC is assumed.  Example: "remind the group to pick a session date"
          → ``fire_at="2026-03-15T18:00:00+00:00"``.

        * **Recurring** (``cron_expression``): fires on a 5-field UTC cron schedule and
          keeps running until disabled.  Example: ``"0 9 * * 5"`` = every Friday at
          9 AM UTC.

        ``prompt`` is the text Grug will respond to at execution time — describe what
        you actually want done (e.g. "roll initiative for the party", "post the weekly
        recap", "remind me to check my spell slots").

        ``name`` is an optional human-readable label.  For one-shot tasks it defaults
        to the first 80 characters of the prompt if omitted.

        ``user_id`` is the Discord user to attribute the task to (defaults to the
        calling user).  Mainly useful for one-shot reminders set on behalf of someone.
        """
        from datetime import datetime, timezone

        from grug.db.models import ScheduledTask
        from grug.db.session import get_session_factory
        from grug.scheduler.manager import add_cron_job, add_date_job
        from grug.scheduler.tasks import execute_scheduled_task
        from grug.utils import ensure_guild

        if (fire_at is None) == (cron_expression is None):
            return "Error: provide exactly one of fire_at or cron_expression."

        await ensure_guild(ctx.deps.guild_id)
        target_user = user_id if user_id is not None else ctx.deps.user_id
        factory = get_session_factory()

        if fire_at is not None:
            run_dt = datetime.fromisoformat(fire_at)
            if run_dt.tzinfo is None:
                run_dt = run_dt.replace(tzinfo=timezone.utc)
            task_name = name or prompt[:80]
            async with factory() as session:
                task = ScheduledTask(
                    guild_id=ctx.deps.guild_id,
                    channel_id=ctx.deps.channel_id,
                    type="once",
                    name=task_name,
                    prompt=prompt,
                    fire_at=run_dt,
                    user_id=target_user,
                    created_by=ctx.deps.user_id,
                )
                session.add(task)
                await session.commit()
                await session.refresh(task)
                task_id = task.id

            add_date_job(
                execute_scheduled_task,
                run_date=run_dt,
                job_id=f"task_{task_id}",
                args=[task_id],
            )
            return f"One-shot task scheduled for {run_dt.isoformat()} (ID: {task_id})."

        else:
            if not name:
                return "Error: name is required for recurring tasks."
            async with factory() as session:
                task = ScheduledTask(
                    guild_id=ctx.deps.guild_id,
                    channel_id=ctx.deps.channel_id,
                    type="recurring",
                    name=name,
                    prompt=prompt,
                    cron_expression=cron_expression,
                    user_id=target_user,
                    created_by=ctx.deps.user_id,
                )
                session.add(task)
                await session.commit()
                await session.refresh(task)
                task_id = task.id

            add_cron_job(
                execute_scheduled_task,
                cron_expression=cron_expression,
                job_id=f"task_{task_id}",
                args=[task_id],
            )
            return f"Recurring task '{name}' scheduled ({cron_expression}) — ID: {task_id}."

    @agent.tool
    async def list_scheduled_tasks(ctx: RunContext[GrugDeps]) -> str:
        """List all active scheduled tasks for this guild channel.

        Use this when the user asks what tasks or reminders are scheduled, or when
        they want to cancel something and need to find the task ID first.
        """
        from grug.db.models import ScheduledTask
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask)
                .where(
                    ScheduledTask.guild_id == ctx.deps.guild_id,
                    ScheduledTask.channel_id == ctx.deps.channel_id,
                    ScheduledTask.enabled.is_(True),
                )
                .order_by(ScheduledTask.created_at.desc())
                .limit(20)
            )
            tasks = result.scalars().all()

        if not tasks:
            return "No active scheduled tasks for this channel."

        lines = []
        for t in tasks:
            label = t.name or t.prompt[:60]
            if t.type == "once":
                schedule = (
                    f"fires at {t.fire_at.isoformat()}" if t.fire_at else "one-shot"
                )
            else:
                schedule = f"cron: {t.cron_expression}"
            lines.append(f"ID {t.id} [{t.type}] — {label} ({schedule})")
        return "Active tasks:\n" + "\n".join(lines)

    @agent.tool
    async def cancel_scheduled_task(ctx: RunContext[GrugDeps], task_id: int) -> str:
        """Cancel and delete a scheduled task by its ID.

        Use this when the user asks to cancel, delete, stop, or remove a scheduled
        task or reminder. If the user does not know the ID, call list_scheduled_tasks
        first to find it, then cancel it.
        """
        from grug.db.models import ScheduledTask
        from grug.db.session import get_session_factory
        from grug.scheduler.manager import remove_job

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask).where(
                    ScheduledTask.id == task_id,
                    ScheduledTask.guild_id == ctx.deps.guild_id,
                )
            )
            task = result.scalar_one_or_none()
            if task is None:
                return f"No task with ID {task_id} found for this guild."
            label = task.name or task.prompt[:60]
            await session.delete(task)
            await session.commit()

        remove_job(f"task_{task_id}")
        return f"Task {task_id} ('{label}') cancelled and removed."
