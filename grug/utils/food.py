from datetime import datetime, timezone
from venv import logger

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.assistant_interfaces import discord_interface
from grug.db import async_session
from grug.models import Event, EventOccurrence


async def send_food_reminder(event_occurrence_id: int, session: AsyncSession = None):
    logger.info(f"Sending food reminder for Event_ID: {event_occurrence_id}")

    # If a session is not provided, create one and close it at the end
    close_session_at_end = False
    if session is None:
        close_session_at_end = True
        session = async_session()

    event_occurrence: EventOccurrence = (
        (await session.execute(select(EventOccurrence).where(EventOccurrence.id == event_occurrence_id)))
        .scalars()
        .one_or_none()
    )
    if event_occurrence is None:
        logger.error(f"Event {event_occurrence_id} not found.")
        return
    elif event_occurrence.timestamp < datetime.now(timezone.utc):
        logger.info(f"Event {event_occurrence_id} has already passed, skipping reminders")
        return

    if event_occurrence.event.enable_food_discord_reminders:
        await discord_interface.send_discord_food_reminder(
            event_occurrence=event_occurrence,
            session=session,
        )

    # Close the session if it was created in this function
    if close_session_at_end:
        await session.close()


async def get_distinct_event_occurrence_food_history(event_id: int, session: AsyncSession | None = None):
    close_session_at_end = False
    if session is None:
        close_session_at_end = True
        session = async_session()

    try:
        event: Event = (await session.execute(select(Event).where(Event.id == event_id))).scalars().one_or_none()
        if event is None:
            raise ValueError(f"Event {event_id} not found.")

        # get distinct set of people who last brought food
        distinct_food_bringers: dict[str, EventOccurrence] = {}
        for event_occurrence in event.event_occurrences:
            if event_occurrence.user_assigned_food:
                user_friendly_name = event_occurrence.user_assigned_food.friendly_name
                if (
                    user_friendly_name not in distinct_food_bringers
                    or event_occurrence.event_date > distinct_food_bringers[user_friendly_name].event_date
                ):
                    distinct_food_bringers[user_friendly_name] = event_occurrence

        distinct_food_bringers_sorted = dict(
            sorted(
                distinct_food_bringers.items(),
                key=lambda item: item[1].event_date,
                reverse=True,
            )
        )

        return list(distinct_food_bringers_sorted.values())

    finally:
        if close_session_at_end:
            await session.close()
