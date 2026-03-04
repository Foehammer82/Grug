"""Event reminder lifecycle helpers.

Auto-creates and manages ScheduledTask "reminder" rows linked to a
CalendarEvent via ``event_id``.  By default, two reminders are created:

  - **24 h before** the event start time
  - **1 h before** the event start time

All reminder tasks share ``source='system'`` so they are distinguishable
from user-created tasks.

Public API
----------
- ``create_event_reminders(event_id, guild_id, channel_id)`` — idempotent;
  safe to call on create *or* update.
- ``refresh_event_reminders(event_id)`` — re-computes fire times from the
  event's current ``start_time``.  Existing reminder tasks are deleted and
  re-created.
- ``delete_event_reminders(event_id)`` — removes all reminder tasks (and
  their APScheduler jobs) for the given event.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from grug.db.models import AvailabilityPoll, CalendarEvent, Campaign, ScheduledTask
from grug.db.session import get_session_factory
from grug.scheduler.manager import add_date_job, remove_job

logger = logging.getLogger(__name__)

# (offset before event, human label)
_REMINDER_OFFSETS: list[tuple[timedelta, str]] = [
    (timedelta(hours=24), "24 h"),
    (timedelta(hours=1), "1 h"),
]


async def create_event_reminders(
    event_id: int,
    guild_id: int,
    channel_id: int,
) -> list[int]:
    """Create reminder ScheduledTask rows for *event_id*.

    This is **idempotent** — it first deletes any existing reminders for
    this event, then creates fresh ones based on the event's start time.

    Returns the IDs of the created tasks.
    """
    factory = get_session_factory()

    async with factory() as session:
        event = (
            await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == event_id)
            )
        ).scalar_one_or_none()

        if event is None:
            logger.warning("create_event_reminders: event %d not found", event_id)
            return []

        # Purge stale reminders first.
        await _delete_reminders_in_session(session, event_id)

        now = datetime.now(timezone.utc)
        created_ids: list[int] = []

        for offset, label in _REMINDER_OFFSETS:
            fire_at = event.start_time - offset
            # Skip reminders that would fire in the past.
            if fire_at <= now:
                continue

            prompt = (
                f"Reminder: **{event.title}** starts in {label}!  "
                f"Send a friendly reminder about the upcoming event."
            )
            task = ScheduledTask(
                guild_id=guild_id,
                channel_id=channel_id,
                type="once",
                name=f"Reminder: {event.title} ({label} before)",
                prompt=prompt,
                fire_at=fire_at,
                source="system",
                event_id=event_id,
                user_id=None,
                created_by=0,  # system sentinel
            )
            session.add(task)
            await session.flush()  # populate task.id
            created_ids.append(task.id)

        await session.commit()

    # Register APScheduler jobs outside the DB session.
    from grug.scheduler.tasks import execute_scheduled_task

    for task_id in created_ids:
        # Re-load the fire_at for the scheduler.
        async with factory() as session:
            t = (
                await session.execute(
                    select(ScheduledTask).where(ScheduledTask.id == task_id)
                )
            ).scalar_one()
            add_date_job(
                execute_scheduled_task,
                run_date=t.fire_at,
                job_id=f"task_{task_id}",
                args=[task_id],
            )

    logger.info("Created %d reminder(s) for event %d", len(created_ids), event_id)
    return created_ids


async def refresh_event_reminders(event_id: int) -> list[int]:
    """Delete and re-create reminders after an event is updated.

    Returns the IDs of the newly created tasks.
    """
    factory = get_session_factory()
    async with factory() as session:
        event = (
            await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == event_id)
            )
        ).scalar_one_or_none()

        if event is None:
            logger.warning("refresh_event_reminders: event %d not found", event_id)
            return []

        guild_id = event.guild_id
        channel_id = event.channel_id or 0

    return await create_event_reminders(event_id, guild_id, channel_id)


async def delete_event_reminders(event_id: int) -> int:
    """Delete all reminder tasks linked to *event_id*.

    Returns the number of tasks deleted.
    """
    factory = get_session_factory()
    async with factory() as session:
        count = await _delete_reminders_in_session(session, event_id)
        await session.commit()
    logger.info("Deleted %d reminder(s) for event %d", count, event_id)
    return count


async def _delete_reminders_in_session(session, event_id: int) -> int:
    """Delete reminder tasks for *event_id* within an existing session.

    Also removes the corresponding APScheduler jobs.
    """
    result = await session.execute(
        select(ScheduledTask).where(ScheduledTask.event_id == event_id)
    )
    tasks = result.scalars().all()
    for task in tasks:
        remove_job(f"task_{task.id}")
        await session.delete(task)
    return len(tasks)


async def maybe_create_schedule_poll(event_id: int) -> int | None:
    """Auto-create an availability poll if the event's campaign uses poll scheduling.

    Called after a session event reminder fires and the next occurrence is
    computed.  Generates 3 date-option slots around the event's ``start_time``
    (same weekday, ±1 week) so players can vote on the best session date.

    Returns the poll ID if created, else ``None``.
    """
    factory = get_session_factory()
    async with factory() as session:
        event = (
            await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == event_id)
            )
        ).scalar_one_or_none()
        if event is None or event.campaign_id is None:
            return None

        campaign = (
            await session.execute(
                select(Campaign).where(Campaign.id == event.campaign_id)
            )
        ).scalar_one_or_none()
        if campaign is None or campaign.schedule_mode != "poll":
            return None

        # Don't create duplicate polls for the same event
        existing = (
            await session.execute(
                select(AvailabilityPoll).where(
                    AvailabilityPoll.event_id == event_id,
                    AvailabilityPoll.winner_option_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.info(
                "Poll already exists for event %d (poll %d), skipping",
                event_id,
                existing.id,
            )
            return existing.id

        # Generate 3 options: same time on -1 week / same day / +1 week
        base = event.start_time
        duration = (
            (event.end_time - event.start_time)
            if event.end_time
            else timedelta(hours=3)
        )
        options = []
        for i, delta_weeks in enumerate([-1, 0, 1]):
            start = base + timedelta(weeks=delta_weeks)
            end = start + duration
            options.append(
                {
                    "id": i,
                    "label": start.strftime("%A %b %d, %I:%M %p"),
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                }
            )

        poll = AvailabilityPoll(
            guild_id=event.guild_id,
            event_id=event_id,
            title=f"When should we play next? ({event.title})",
            options=options,
            closes_at=base - timedelta(days=2),  # close voting 2 days before earliest
            created_by=0,  # system sentinel
        )
        session.add(poll)
        await session.commit()
        await session.refresh(poll)

        logger.info(
            "Auto-created availability poll %d for event %d (campaign %d, poll mode)",
            poll.id,
            event_id,
            campaign.id,
        )
        return poll.id
