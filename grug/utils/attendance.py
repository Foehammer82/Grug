# TODO: do food first, but then use that as a foundation for attendance.
from loguru import logger

from grug.models import Event


async def send_attendance_reminder(event: Event):
    logger.info(f"Sending attendance reminder for {event.name}")
