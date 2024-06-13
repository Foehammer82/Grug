"""Scheduler for the Grug bot."""

import asyncio
from datetime import datetime, timedelta

from apscheduler import AsyncScheduler, ConflictPolicy, Schedule
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


def handle_event_model_upsert(mapper: Mapper, connection: Connection, event_model: Event):
    from grug.utils.attendance import send_attendance_reminder
    from grug.utils.food import send_food_reminder

    # Upsert the food reminder schedule for the given event
    asyncio.create_task(
        scheduler.add_schedule(
            func_or_task_id=send_food_reminder,
            trigger=event_model.get_food_reminder_calendar_interval_trigger(),
            id=f"event_{event_model.id}_food_reminder",
            conflict_policy=ConflictPolicy.replace,
            kwargs={"event_id": event_model.id},
            paused=(not event_model.track_food),
            misfire_grace_time=timedelta(minutes=5),
        )
    )
    logger.info(f"Upserted food reminder job for event {event_model.id} [paused={not event_model.track_food}]")

    # Upsert the attendance reminder schedule for the given event
    asyncio.create_task(
        scheduler.add_schedule(
            func_or_task_id=send_attendance_reminder,
            trigger=event_model.get_attendance_reminder_calendar_interval_trigger(),
            id=f"event_{event_model.id}_attendance_reminder",
            conflict_policy=ConflictPolicy.replace,
            kwargs={"event_id": event_model.id},
            paused=(not event_model.track_attendance),
            misfire_grace_time=timedelta(minutes=5),
        )
    )
    logger.info(
        f"Upserted attendance reminder job for event {event_model.id} [paused={not event_model.track_attendance}]"
    )


event.listen(Event, "after_insert", handle_event_model_upsert)
event.listen(Event, "after_update", handle_event_model_upsert)


@event.listens_for(Event, "after_delete")
def handle_event_model_deleted(mapper: Mapper, connection: Connection, event_model: Event):
    """Remove food and attendance reminder jobs from the scheduler when an event is deleted."""
    asyncio.create_task(scheduler.remove_schedule(id=f"event_{event_model.id}_food_reminder"))
    asyncio.create_task(scheduler.remove_schedule(id=f"event_{event_model.id}_attendance_reminder"))
    logger.info(f"Removed food and attendance reminder jobs for event {event_model.id}")
