"""Scheduling and calendar tools for the Grug agent."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from grug.agent.tools.base import BaseTool
from grug.db.models import CalendarEvent, GuildConfig, Reminder, ScheduledTask
from grug.db.session import get_session_factory
from grug.scheduler.manager import add_cron_job, add_date_job, get_scheduler
from grug.scheduler.tasks import run_scheduled_prompt, send_reminder

logger = logging.getLogger(__name__)


async def _ensure_guild(guild_id: int) -> None:
    """Ensure a GuildConfig row exists for this guild."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        if result.scalar_one_or_none() is None:
            session.add(GuildConfig(guild_id=guild_id))
            await session.commit()


class CreateCalendarEventTool(BaseTool):
    """Create a calendar event for the guild."""

    def __init__(self, guild_id: int, user_id: int) -> None:
        self._guild_id = guild_id
        self._user_id = user_id

    @property
    def name(self) -> str:
        return "create_calendar_event"

    @property
    def description(self) -> str:
        return "Create a calendar event for the guild. Times should be in ISO-8601 format."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "description": {"type": "string", "description": "Event description"},
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO-8601 format (e.g. 2025-03-15T19:00:00)",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO-8601 format (optional)",
                },
                "channel_id": {
                    "type": "integer",
                    "description": "Discord channel ID where the event should be announced (optional)",
                },
            },
            "required": ["title", "start_time"],
        }

    async def run(
        self,
        title: str,
        start_time: str,
        description: str | None = None,
        end_time: str | None = None,
        channel_id: int | None = None,
        **_: Any,
    ) -> str:
        await _ensure_guild(self._guild_id)
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time) if end_time else None
        factory = get_session_factory()
        async with factory() as session:
            event = CalendarEvent(
                guild_id=self._guild_id,
                title=title,
                description=description,
                start_time=start,
                end_time=end,
                channel_id=channel_id,
                created_by=self._user_id,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            event_id = event.id
        return f"✅ Calendar event **{title}** created (ID: {event_id}, starts {start_time})."


class ListCalendarEventsTool(BaseTool):
    """List upcoming calendar events for the guild."""

    def __init__(self, guild_id: int) -> None:
        self._guild_id = guild_id

    @property
    def name(self) -> str:
        return "list_calendar_events"

    @property
    def description(self) -> str:
        return "List upcoming calendar events for this guild."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of events to return (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        }

    async def run(self, limit: int = 10, **_: Any) -> str:
        factory = get_session_factory()
        now = datetime.now(timezone.utc)
        async with factory() as session:
            result = await session.execute(
                select(CalendarEvent)
                .where(
                    CalendarEvent.guild_id == self._guild_id,
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


class CreateReminderTool(BaseTool):
    """Create a reminder for a user."""

    def __init__(self, guild_id: int, user_id: int, channel_id: int) -> None:
        self._guild_id = guild_id
        self._user_id = user_id
        self._channel_id = channel_id

    @property
    def name(self) -> str:
        return "create_reminder"

    @property
    def description(self) -> str:
        return "Create a reminder that will be sent to the user at the specified time."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The reminder message"},
                "remind_at": {
                    "type": "string",
                    "description": "When to send the reminder in ISO-8601 format",
                },
                "user_id": {
                    "type": "integer",
                    "description": "Discord user ID to remind (defaults to the requesting user)",
                },
            },
            "required": ["message", "remind_at"],
        }

    async def run(
        self,
        message: str,
        remind_at: str,
        user_id: int | None = None,
        **_: Any,
    ) -> str:
        await _ensure_guild(self._guild_id)
        target_user = user_id if user_id is not None else self._user_id
        run_dt = datetime.fromisoformat(remind_at)
        factory = get_session_factory()
        async with factory() as session:
            reminder = Reminder(
                guild_id=self._guild_id,
                user_id=target_user,
                channel_id=self._channel_id,
                message=message,
                remind_at=run_dt,
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            reminder_id = reminder.id

        job_id = f"reminder_{reminder_id}"
        add_date_job(
            send_reminder,
            run_date=run_dt,
            job_id=job_id,
            args=[reminder_id, self._channel_id, target_user, message],
        )
        return f"⏰ Reminder set for {remind_at} (ID: {reminder_id})."


class CreateScheduledTaskTool(BaseTool):
    """Create a recurring agent task with a cron schedule."""

    def __init__(self, guild_id: int, channel_id: int, user_id: int) -> None:
        self._guild_id = guild_id
        self._channel_id = channel_id
        self._user_id = user_id

    @property
    def name(self) -> str:
        return "create_scheduled_task"

    @property
    def description(self) -> str:
        return (
            "Create a recurring task where Grug will respond to a prompt on a cron schedule. "
            "Cron format: 'minute hour day month day_of_week' (5 fields, UTC). "
            "Example: '0 9 * * 5' = every Friday at 9:00 AM UTC."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short name for this task"},
                "prompt": {
                    "type": "string",
                    "description": "The prompt Grug will respond to on each run",
                },
                "cron_expression": {
                    "type": "string",
                    "description": "5-field cron expression (e.g. '0 9 * * 5')",
                },
            },
            "required": ["name", "prompt", "cron_expression"],
        }

    async def run(
        self, name: str, prompt: str, cron_expression: str, **_: Any
    ) -> str:
        await _ensure_guild(self._guild_id)
        factory = get_session_factory()
        async with factory() as session:
            task = ScheduledTask(
                guild_id=self._guild_id,
                channel_id=self._channel_id,
                name=name,
                prompt=prompt,
                cron_expression=cron_expression,
                created_by=self._user_id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        job_id = f"task_{task_id}"
        add_cron_job(
            run_scheduled_prompt,
            cron_expression=cron_expression,
            job_id=job_id,
            args=[task_id, self._guild_id, self._channel_id, prompt],
        )
        return f"🔁 Recurring task **{name}** scheduled ({cron_expression}) — ID: {task_id}."
