"""Scheduler for the Grug bot."""

import asyncio
from contextlib import suppress
from datetime import datetime

from apscheduler import AsyncScheduler, ConflictPolicy, Schedule, ScheduleLookupError
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from pydantic import BaseModel, computed_field
from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from grug.assistant_functions.food import send_discord_food_reminder
from grug.db import async_engine
from grug.models import Event
from grug.settings import settings
from grug.utils.attendance import send_attendance_reminder
from grug.utils.food import send_food_reminder

scheduler = AsyncScheduler(
    data_store=SQLAlchemyDataStore(engine_or_url=async_engine),
    event_broker=AsyncpgEventBroker.from_async_sqla_engine(engine=async_engine),
)


def init_scheduler():
    """Initialize the scheduler."""

    async def start_scheduler():
        async with scheduler:
            # TODO: remove this schedule once the new system is online
            await scheduler.add_schedule(
                func_or_task_id=send_discord_food_reminder,
                trigger=CronTrigger.from_crontab(settings.dnd_session_food_reminder_cron),
                id="food-reminder",
                conflict_policy=ConflictPolicy.replace,
            )

            await scheduler.run_until_stopped()

    scheduler_task = asyncio.create_task(start_scheduler())
    logger.info(f"Scheduler started with task ID {scheduler_task.get_name()}")


class ScheduleModel(BaseModel):
    id: str
    paused: bool
    last_fire_time: datetime | None = None
    next_fire_time: datetime | None = None
    task_id: str | None = None

    @computed_field
    @property
    def scheduler_state(self) -> str:
        return scheduler.state.name

    @classmethod
    def _from_schedule(cls, schedule: Schedule):
        return cls(
            id=schedule.id,
            paused=schedule.paused,
            last_fire_time=schedule.last_fire_time,
            next_fire_time=schedule.next_fire_time,
            task_id=schedule.task_id,
        )

    @classmethod
    async def get_all(cls):
        schedules = await scheduler.get_schedules()

        return [cls._from_schedule(schedule) for schedule in schedules]

    @classmethod
    async def get(cls, schedule_id: str):
        schedule = await scheduler.get_schedule(id=schedule_id)

        return cls._from_schedule(schedule)


@event.listens_for(Event, "after_insert")
def handle_event_model_created(mapper: Mapper, connection: Connection, event_model: Event):
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
def handle_event_model_updated(mapper: Mapper, connection: Connection, event_model: Event):
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
def handle_event_model_deleted(mapper: Mapper, connection: Connection, event_model: Event):
    """Remove food and attendance reminder jobs from the scheduler when an event is deleted."""
    asyncio.run(scheduler.remove_schedule(id=f"event_{event_model.id}_food_reminder"))
    asyncio.run(scheduler.remove_schedule(id=f"event_{event_model.id}_attendance_reminder"))
    logger.info(f"Removed food and attendance reminder jobs for event {event_model.id}")
