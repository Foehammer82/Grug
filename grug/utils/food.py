from venv import logger

from grug.models import Event


async def send_food_reminder(event: Event):
    # TODO: get or create the next food even, and send the reminder for it
    logger.info(f"Sending food reminder for {event.name}")
