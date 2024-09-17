"""Scheduler for the Grug bot."""

import asyncio
from datetime import timezone

from apscheduler import AsyncScheduler, ConflictPolicy, Schedule, ScheduleLookupError
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from pydantic import PostgresDsn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select

from grug.db import async_engine, async_session
from grug.models import Group
from grug.models_crud import get_or_create_next_game_session_event
from grug.reminders import game_session_reminder
from grug.settings import settings

# TODO: deprecated! as soon as ApScheduler releases next we can switch to psycopg for the event broker.
scheduler = AsyncScheduler(
    data_store=SQLAlchemyDataStore(
        engine_or_url=async_engine,
        schema="apscheduler",
    ),
    event_broker=AsyncpgEventBroker.from_async_sqla_engine(
        engine=create_async_engine(
            url=str(
                PostgresDsn.build(
                    scheme="postgresql+asyncpg",
                    host=settings.postgres_host,
                    port=settings.postgres_port,
                    username=settings.postgres_user,
                    password=settings.postgres_password.get_secret_value(),
                    path=settings.postgres_db,
                )
            ),
            echo=False,
            future=True,
        ),
    ),
)


async def start_scheduler(discord_bot_startup_timeout: int = 15):
    from grug.bot_discord import client

    # Create the db schema for the scheduler
    async with async_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS apscheduler"))

    # wait for the discord bot to be ready
    timed_out = True
    for _ in range(discord_bot_startup_timeout):
        if client.is_ready():
            timed_out = False
            break
        await asyncio.sleep(1)
    if timed_out:
        raise TimeoutError(
            f"Timeout reached in {discord_bot_startup_timeout} seconds. Discord bot did not achieve ready state in "
            "the allowed time."
        )

    # start the scheduler
    async with scheduler:
        await scheduler.run_until_stopped()


async def update_group_schedules(group_id: int | None = None, group: Group | None = None):
    """
    Update the game session schedules for a group or all groups.

    :param group_id: The group ID to update the game session schedules for. If None, all groups will be updated.
    :param group: The group to update the game session schedules for. If None, all groups will be updated.
    """
    if group is not None and group_id is not None:
        raise ValueError("Only one of `group_id` or `group` can be provided, not both.")

    # Lookup the group(s) to update game session schedules for
    async with async_session() as session:
        if group_id:
            # noinspection Pydantic
            groups = list((await session.execute(select(Group).where(Group.id == group_id))).scalars().all())
        elif group:
            groups = [group]
        else:
            groups = (await session.execute(select(Group))).scalars().all()

        # Update the game session schedules for each group
        for group in groups:
            game_session_schedule_id = f"group_{group.id}_game_session_schedule"
            game_session_reminder_schedule_id = f"group_{group.id}_game_session_reminder_schedule"

            # Get the game session schedule
            replace_session_schedule = False
            try:
                game_session_schedule: Schedule | None = await scheduler.get_schedule(game_session_schedule_id)

                # Check if the trigger is a cron trigger
                if isinstance(game_session_schedule.trigger, CronTrigger):
                    # Check if the group schedule has changed
                    t1 = game_session_schedule.next_fire_time.astimezone(timezone.utc)
                    t2 = group.game_session_cron_trigger.next().astimezone(timezone.utc)
                    if t1 != t2:
                        replace_session_schedule = True

                # If the trigger is not a cron trigger, replace the schedule
                else:
                    await scheduler.remove_schedule(game_session_schedule_id)
                    replace_session_schedule = True

            # If the schedule does not exist, mark it for replacement
            except ScheduleLookupError:
                game_session_schedule = None
                replace_session_schedule = True

            # Update the game session schedule if needed
            if replace_session_schedule:
                # Pause the schedule if it exists and the group schedule is null
                if not group.game_session_cron_schedule:
                    if game_session_schedule:
                        await scheduler.pause_schedule(game_session_schedule_id)
                        logger.info(f"Paused group game session schedule for group: {group.id}")

                # otherwise, update the schedule
                else:
                    await scheduler.add_schedule(
                        id=game_session_schedule_id,
                        func_or_task_id=update_group_schedules,
                        trigger=group.game_session_cron_trigger,
                        conflict_policy=ConflictPolicy.replace,
                        kwargs={"group_id": group.id},
                    )
                    logger.info(f"Updated group game session schedule for group: {group.id}")

            # Update the game session reminder schedule
            try:
                game_session_reminder_schedule: Schedule | None = await scheduler.get_schedule(
                    game_session_reminder_schedule_id
                )
            except ScheduleLookupError:
                game_session_reminder_schedule = None

            # Get the next game session event
            next_game_session_event = await get_or_create_next_game_session_event(group.id, session)

            # Update the game session reminder schedule if needed, based on the next game session event, not
            # necessarily the group defined schedule
            if (
                (game_session_reminder_schedule is None and group.game_session_cron_schedule is not None)
                or game_session_schedule is not None
                and next_game_session_event is not None
                and game_session_schedule.next_fire_time != next_game_session_event.reminder_datetime
            ):
                await scheduler.add_schedule(
                    id=game_session_reminder_schedule_id,
                    func_or_task_id=game_session_reminder,
                    trigger=DateTrigger(next_game_session_event.reminder_datetime),
                    conflict_policy=ConflictPolicy.replace,
                    kwargs={"group_id": group.id},
                )
                logger.info(f"Updated group game session reminder schedule for group: {group.id}")
