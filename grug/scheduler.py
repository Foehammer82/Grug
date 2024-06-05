"""Scheduler for the Grug bot."""

import asyncio
from contextlib import suppress
from datetime import datetime

from apscheduler import AsyncScheduler, ConflictPolicy, Schedule, ScheduleLookupError
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from loguru import logger
from pydantic import BaseModel, computed_field
from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from grug.db import async_engine
from grug.models import Event
from grug.settings import settings

scheduler = AsyncScheduler(
    data_store=SQLAlchemyDataStore(engine_or_url=async_engine, schema=settings.scheduler_db_schema),
    event_broker=AsyncpgEventBroker.from_async_sqla_engine(engine=async_engine),
)


def init_scheduler():
    """Initialize the scheduler."""

    async def start_scheduler():
        async with scheduler:
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
    from grug.utils.attendance import send_attendance_reminder
    from grug.utils.food import send_food_reminder

    # Create the food reminder schedule for the given event
    asyncio.create_task(
        scheduler.add_schedule(
            func_or_task_id=send_food_reminder,
            trigger=event_model.get_food_reminder_calendar_interval_trigger(),
            id=f"event_{event_model.id}_food_reminder",
            conflict_policy=ConflictPolicy.replace,
            kwargs={"event_id": event_model.id},
            paused=(not event_model.track_food),
        )
    )
    logger.info(f"Created food reminder job for event {event_model.id} [paused={not event_model.track_food}]")

    # Create the attendance reminder schedule for the given event
    asyncio.create_task(
        scheduler.add_schedule(
            func_or_task_id=send_attendance_reminder,
            trigger=event_model.get_attendance_reminder_calendar_interval_trigger(),
            id=f"event_{event_model.id}_attendance_reminder",
            conflict_policy=ConflictPolicy.replace,
            kwargs={"event_id": event_model.id},
            paused=(not event_model.track_attendance),
        )
    )
    logger.info(
        f"Created attendance reminder job for event {event_model.id} [paused={not event_model.track_attendance}]"
    )


@event.listens_for(Event, "after_update")
def handle_event_model_updated(mapper: Mapper, connection: Connection, event_model: Event):
    with suppress(ScheduleLookupError):
        # Update the food reminder job
        if event_model.track_food:
            asyncio.create_task(scheduler.unpause_schedule(id=f"event_{event_model.id}_food_reminder"))
            logger.info(f"Un-paused food reminder job for event {event_model.id}")
        else:
            asyncio.create_task(scheduler.pause_schedule(id=f"event_{event_model.id}_food_reminder"))
            logger.info(f"Paused food reminder job for event {event_model.id}")

        # Update the attendance reminder job
        if event_model.track_attendance:
            asyncio.create_task(scheduler.unpause_schedule(id=f"event_{event_model.id}_attendance_reminder"))
            logger.info(f"Un-paused attendance reminder job for event {event_model.id}")
        else:
            asyncio.create_task(scheduler.pause_schedule(id=f"event_{event_model.id}_attendance_reminder"))
            logger.info(f"Paused attendance reminder job for event {event_model.id}")


@event.listens_for(Event, "after_delete")
def handle_event_model_deleted(mapper: Mapper, connection: Connection, event_model: Event):
    """Remove food and attendance reminder jobs from the scheduler when an event is deleted."""
    asyncio.create_task(scheduler.remove_schedule(id=f"event_{event_model.id}_food_reminder"))
    asyncio.create_task(scheduler.remove_schedule(id=f"event_{event_model.id}_attendance_reminder"))
    logger.info(f"Removed food and attendance reminder jobs for event {event_model.id}")
