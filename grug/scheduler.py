"""Scheduler for the Grug bot."""

import asyncio
from contextlib import suppress

from apscheduler import AsyncScheduler, ConflictPolicy, ScheduleLookupError
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from grug.assistant_functions.food import send_discord_food_reminder
from grug.db import async_engine
from grug.models import Event
from grug.settings import settings
from grug.utils.attendance import send_attendance_reminder
from grug.utils.food import send_food_reminder

scheduler = AsyncScheduler(
    data_store=SQLAlchemyDataStore(engine=async_engine),
    event_broker=AsyncpgEventBroker.from_async_sqla_engine(engine=async_engine),
)


async def start_scheduler():
    """Start the scheduler."""
    async with scheduler:
        await scheduler.add_schedule(
            func_or_task_id=send_discord_food_reminder,
            trigger=CronTrigger.from_crontab(settings.dnd_session_food_reminder_cron),
            id="food-reminder",
            conflict_policy=ConflictPolicy.replace,
        )

    await scheduler.run_until_stopped()


@event.listens_for(Event, "after_insert")
def handle_event_model_created(mapper: Mapper, connection: Connection, event_model: Event) -> Event:
    if event_model.track_food:
        asyncio.run(
            scheduler.add_schedule(
                func_or_task_id=send_food_reminder,
                trigger=CronTrigger.from_crontab(event_model.food_reminder_cron),
                id=f"event_{event_model.id}_food_reminder",
                conflict_policy=ConflictPolicy.replace,
                kwargs={"event": event_model},
            )
        )
        logger.info(f"Created food reminder job for event {event_model.id}")
    if event_model.track_attendance:
        asyncio.run(
            scheduler.add_schedule(
                func_or_task_id=send_attendance_reminder,
                trigger=CronTrigger.from_crontab(event_model.attendance_reminder_cron),
                id=f"event_{event_model.id}_attendance_reminder",
                conflict_policy=ConflictPolicy.replace,
                kwargs={"event": event_model},
            )
        )
        logger.info(f"Created attendance reminder job for event {event_model.id}")


@event.listens_for(Event, "after_update")
def handle_event_model_updated(mapper: Mapper, connection: Connection, event_model: Event) -> Event:
    with suppress(ScheduleLookupError):
        # Update the food reminder job
        if event_model.track_food:
            asyncio.run(
                scheduler.add_schedule(
                    func_or_task_id=send_food_reminder,
                    trigger=CronTrigger.from_crontab(event_model.food_reminder_cron),
                    id=f"event_{event_model.id}_food_reminder",
                    conflict_policy=ConflictPolicy.replace,
                    kwargs={"event": event_model},
                )
            )
            logger.info(f"Updated/Created food reminder job for event {event_model.id}")
        else:
            asyncio.run(scheduler.remove_schedule(id=f"event_{event_model.id}_food_reminder"))
            logger.info(f"Removed food reminder job for event {event_model.id}")

        # Update the attendance reminder job
        if event_model.track_attendance:
            asyncio.run(
                scheduler.add_schedule(
                    func_or_task_id=send_attendance_reminder,
                    trigger=CronTrigger.from_crontab(event_model.attendance_reminder_cron),
                    id=f"event_{event_model.id}_attendance_reminder",
                    conflict_policy=ConflictPolicy.replace,
                    kwargs={"event": event_model},
                )
            )
            logger.info(f"Updated/Created attendance reminder job for event {event_model.id}")
        else:
            asyncio.run(scheduler.remove_schedule(id=f"event_{event_model.id}_attendance_reminder"))
            logger.info(f"Removed attendance reminder job for event {event_model.id}")


@event.listens_for(Event, "after_delete")
def handle_event_model_deleted(mapper: Mapper, connection: Connection, event_model: Event) -> Event:
    """Remove food and attendance reminder jobs from the scheduler when an event is deleted."""
    asyncio.run(scheduler.remove_schedule(id=f"event_{event_model.id}_food_reminder"))
    asyncio.run(scheduler.remove_schedule(id=f"event_{event_model.id}_attendance_reminder"))
    logger.info(f"Removed food and attendance reminder jobs for event {event_model.id}")
