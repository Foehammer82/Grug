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
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            logger.warning(
                "Channel %d not found for scheduled task %d", channel_id, task_id
            )
            return

    agent = GrugAgent()
    # Prefix tells the agent this is a scheduled execution so it acts immediately
    # rather than interpreting the prompt as a new request to schedule something.
    execution_message = (
        f"[SCHEDULED TASK — execute immediately, do NOT create a new reminder or "
        f"scheduled task]: {prompt}"
    )
    response = await agent.respond(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=0,
        username="Grug Scheduler",
        message=execution_message,
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
    reminder_id: int,
    guild_id: int,
    channel_id: int,
    user_id: int,
    prompt: str,
) -> None:
    """Execute a reminder prompt through Grug and mark it sent.

    Rather than sending a static "Reminder: …" message, the original prompt is
    fed back to the agent so Grug *actually does the thing* the user asked for.
    """
    from grug.bot.client import get_bot
    from grug.agent.core import GrugAgent
    from grug.db.session import get_session_factory
    from grug.db.models import Reminder
    from sqlalchemy import select

    bot = get_bot()
    if bot is None:
        logger.warning("Bot not initialised; skipping reminder %d", reminder_id)
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            logger.warning(
                "Channel %d not found for reminder %d", channel_id, reminder_id
            )
            return

    agent = GrugAgent()
    # Prefix tells the agent this is a scheduled execution so it acts immediately
    # rather than interpreting the prompt as a new request to schedule something.
    execution_message = (
        f"[REMINDER — execute immediately, do NOT create a new reminder or "
        f"scheduled task]: {prompt}"
    )
    response = await agent.respond(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=user_id,
        username="Grug Reminder",
        message=execution_message,
    )
    await channel.send(response)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.sent = True
            await session.commit()
