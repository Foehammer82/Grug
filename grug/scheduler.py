"""Scheduler for the Grug bot."""

import asyncio
from datetime import datetime, timezone
from typing import Callable

from apscheduler import AsyncScheduler, ConflictPolicy, ScheduleLookupError
from apscheduler.abc import Trigger
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from loguru import logger
from sqlalchemy import event

from grug.bg_task_manager import track_background_task
from grug.db import async_engine
from grug.models import Event, EventOccurrence
from grug.models_crud import sync_next_event_occurrence_to_event
from grug.settings import settings
from grug.utils.attendance import send_attendance_reminder
from grug.utils.food import send_food_reminder

_scheduler_data_store = SQLAlchemyDataStore(engine_or_url=async_engine, schema=settings.postgres_apscheduler_schema)
scheduler = AsyncScheduler(
    data_store=_scheduler_data_store,
    event_broker=AsyncpgEventBroker.from_async_sqla_engine(engine=async_engine),
)


def init_scheduler():
    """Initialize the scheduler."""

    async def start_scheduler():
        async with scheduler:
            await scheduler.run_until_stopped()

    scheduler_task = asyncio.create_task(start_scheduler())
    track_background_task(task=scheduler_task, on_error_callback=init_scheduler)
    logger.info(f"Scheduler started with task ID {scheduler_task.get_name()}")


def handle_event_model_upsert(mapper, connection, event_model: Event):
    if event_model.cron_schedule is None:
        # Do not schedule the event if it does not have a cron schedule
        return

    else:
        # Upsert the event occurrence manager job
        track_background_task(
            asyncio.create_task(
                scheduler.add_schedule(
                    id=f"event_{event_model.id}_occurrence_manager",
                    func_or_task_id=sync_next_event_occurrence_to_event,
                    trigger=event_model.schedule_trigger,
                    conflict_policy=ConflictPolicy.replace,
                    kwargs={"event_id": event_model.id},
                )
            )
        )

        logger.info(f"Added event occurrence manager job for event_id: {event_model.id}")

    # Always trigger the event occurrence manager job after an event is updated
    if event_model.id is None:
        raise ValueError("Event model must have an ID to trigger the event occurrence manager job")
    track_background_task(asyncio.create_task(sync_next_event_occurrence_to_event(event_model.id)))


event.listen(Event, "after_insert", handle_event_model_upsert)
event.listen(Event, "after_update", handle_event_model_upsert)


@event.listens_for(Event, "after_delete")
def handle_event_model_delete(mapper, connection, event_model: Event):
    # Remove the occurrence manager job for the given event
    track_background_task(
        asyncio.create_task(scheduler.remove_schedule(id=f"event_{event_model.id}_occurrence_manager"))
    )
    logger.info(f"Removed event occurrence manager job for event_id: {event_model.id}")


async def _upsert_reminder_scheduled_task(
    schedule_id: str,
    event_occurrence: EventOccurrence,
    reminder_func: Callable,
    reminder_trigger: Trigger | None,
):
    if event_occurrence.id is None:
        raise ValueError("Event occurrence ID is required to schedule a reminder.")

    try:
        existing_schedule = await scheduler.get_schedule(schedule_id)
    except ScheduleLookupError:
        existing_schedule = None

    if reminder_trigger:
        # Schedule the reminder job for the given event occurrence, only if the trigger is in the future
        if reminder_trigger.next() > datetime.now(timezone.utc):
            if existing_schedule is not None and existing_schedule.paused:
                await scheduler.unpause_schedule(id=schedule_id, resume_from="now")
                logger.info(
                    f"Reminder {schedule_id} for event: {event_occurrence.event_id} [{event_occurrence.timestamp}] "
                    f"was paused, resuming."
                )
            else:
                await scheduler.add_schedule(
                    id=schedule_id,
                    func_or_task_id=reminder_func,
                    trigger=reminder_trigger,
                    conflict_policy=ConflictPolicy.replace,
                    kwargs={"event_occurrence_id": event_occurrence.id},
                )
                logger.info(
                    f"Added {schedule_id} job for event: {event_occurrence.event_id} [{event_occurrence.timestamp}]"
                )

    elif existing_schedule is not None:
        await scheduler.pause_schedule(id=schedule_id)
        logger.info(f"Paused scheduled task {schedule_id}")


def handle_event_occurrence_model_upsert(mapper, connection, event_occurrence: EventOccurrence):
    # Schedule the food reminder job for the given event occurrence
    track_background_task(
        asyncio.create_task(
            _upsert_reminder_scheduled_task(
                schedule_id=event_occurrence.food_reminder_schedule_id,
                event_occurrence=event_occurrence,
                reminder_func=send_food_reminder,
                reminder_trigger=event_occurrence.food_reminder_trigger,
            )
        )
    )

    # Schedule the attendance reminder job for the given event occurrence
    track_background_task(
        asyncio.create_task(
            _upsert_reminder_scheduled_task(
                schedule_id=event_occurrence.attendance_reminder_schedule_id,
                event_occurrence=event_occurrence,
                reminder_func=send_attendance_reminder,
                reminder_trigger=event_occurrence.attendance_reminder_trigger,
            )
        )
    )


event.listen(EventOccurrence, "after_insert", handle_event_occurrence_model_upsert)
event.listen(EventOccurrence, "after_update", handle_event_occurrence_model_upsert)


@event.listens_for(EventOccurrence, "after_delete")
def handle_event_occurrence_model_delete(mapper, connection, event_model: EventOccurrence):
    # Remove the food reminder job for the given event occurrence
    track_background_task(asyncio.create_task(scheduler.remove_schedule(id=event_model.food_reminder_schedule_id)))
    logger.info(
        f"Removed event occurrence food reminder job for event: {event_model.event_id} "
        f"[{event_model.timestamp.isoformat()}]"
    )

    # Remove the attendance reminder job for the given event occurrence
    track_background_task(
        asyncio.create_task(scheduler.remove_schedule(id=event_model.attendance_reminder_schedule_id))
    )
    logger.info(
        f"Removed event occurrence attendance reminder job for event: {event_model.event_id} "
        f"[{event_model.timestamp.isoformat()}]"
    )
