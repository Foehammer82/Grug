from datetime import datetime, timezone

from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.assistant_interfaces import discord_interface
from grug.db import async_session
from grug.models import EventOccurrence


async def send_attendance_reminder(event_occurrence_id: int, session: AsyncSession = None):
    logger.info(f"Sending attendance reminder for Event_Occurrence_ID: {event_occurrence_id}")

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

    # Send the discord reminder
    if event_occurrence.event.enable_attendance_discord_reminders:
        await discord_interface.send_discord_attendance_reminder(
            event_occurrence=event_occurrence,
            session=session,
        )

    # Close the session if it was created in this function
    if close_session_at_end:
        await session.close()
