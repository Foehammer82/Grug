from venv import logger

from sqlmodel import select

from grug.assistant_interfaces import discord_interface
from grug.db import async_session
from grug.models import Event


async def send_food_reminder(event_id: int, session: async_session = None):
    logger.info(f"Sending food reminder for {event_id}")

    # If a session is not provided, create one and close it at the end
    close_session_at_end = False
    if session is None:
        close_session_at_end = True
        session = async_session()

    event = (await session.execute(select(Event).where(Event.id == event_id))).scalars().one_or_none()
    if event is None:
        logger.error(f"Event {event_id} not found.")
        return

    await discord_interface.send_discord_food_reminder(event, session)

    # Close the session if it was created in this function
    if close_session_at_end:
        await session.close()
