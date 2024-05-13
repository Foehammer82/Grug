"""Scheduler for the Grug bot."""

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from grug.assistant_functions.food import send_discord_food_reminder
from grug.db import async_engine
from grug.models import Event
from grug.settings import settings

# TODO: would be cool if users could ask grug to schedule actions where they can say something like "grug, ask
#       everyone every week on Friday at 11AM if they will be attending the next session" and grug will do it.
# TODO: create function to add jobs to the scheduler
# TODO: create function to show all jobs in the scheduler
# TODO: create function to edit or replace jobs in the scheduler
# TODO: create function to delete jobs in the scheduler


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


# TODO: setup listening on the Event model to update the scheduler when events are created or updated
@event.listens_for(Event, "after_insert")
def handle_job_created(mapper: Mapper, connection: Connection, target: Event) -> Event:
    pass


@event.listens_for(Event, "after_update")
def handle_job_updated(mapper: Mapper, connection: Connection, target: Event) -> Event:
    pass


@event.listens_for(Event, "after_delete")
def handle_job_deleted(mapper: Mapper, connection: Connection, target: Event) -> Event:
    pass
