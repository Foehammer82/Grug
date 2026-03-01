"""Concrete scheduled-task callbacks for Grug."""

import logging

logger = logging.getLogger(__name__)


async def run_scheduled_prompt(
    task_id: int,
    guild_id: int,
    channel_id: int,
    prompt: str,
) -> None:
    """Execute a stored prompt as if a user typed it, then post the response."""
    # Import here to avoid circular imports at module load time
    from grug.bot.client import get_bot
    from grug.agent.core import GrugAgent

    bot = get_bot()
    if bot is None:
        logger.warning("Bot not initialised; skipping scheduled task %d", task_id)
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning(
            "Channel %d not found for scheduled task %d", channel_id, task_id
        )
        return

    agent = GrugAgent()
    response = await agent.respond(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=0,
        username="Grug Scheduler",
        message=prompt,
    )
    await channel.send(response)

    # Update last_run
    from grug.db.session import get_session_factory
    from grug.db.models import ScheduledTask
    from sqlalchemy import select
    from datetime import datetime, timezone

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            task.last_run = datetime.now(timezone.utc)
            await session.commit()


async def send_reminder(
    reminder_id: int, channel_id: int, user_id: int, message: str
) -> None:
    """Send a reminder to a channel and mark it sent."""
    from grug.bot.client import get_bot
    from grug.db.session import get_session_factory
    from grug.db.models import Reminder
    from sqlalchemy import select

    bot = get_bot()
    if bot is None:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    await channel.send(f"<@{user_id}> ⏰ **Reminder:** {message}")

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.sent = True
            await session.commit()
