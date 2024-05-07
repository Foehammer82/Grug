"""Scheduler for the Grug bot."""

import asyncio

from apscheduler import AsyncScheduler, ConflictPolicy, RunState
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.cron import CronTrigger

from grug.db import async_engine
from grug.settings import settings
from grug.utils.food import send_discord_food_reminder

# TODO: would be cool if users could ask grug to schedule actions where they can say something like "grug, ask
#       everyone every week on Friday at 11AM if they will be attending the next session" and grug will do it.
# TODO: create function to add jobs to the scheduler
# TODO: create function to show all jobs in the scheduler
# TODO: create function to edit or replace jobs in the scheduler
# TODO: create function to delete jobs in the scheduler


grug_scheduler = AsyncScheduler(
    data_store=SQLAlchemyDataStore(async_engine),
    event_broker=AsyncpgEventBroker.from_async_sqla_engine(async_engine),
)


async def update_default_schedules():
    """
    Adds default schedules to the scheduler.
    """
    while grug_scheduler.state is not RunState.started:
        await asyncio.sleep(1)

    await grug_scheduler.add_schedule(
        func_or_task_id=send_discord_food_reminder,
        trigger=CronTrigger.from_crontab(settings.dnd_session_food_reminder_cron),
        id="food-reminder",
        conflict_policy=ConflictPolicy.replace,
    )
