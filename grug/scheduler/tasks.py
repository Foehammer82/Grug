"""Concrete scheduled-task callbacks for Grug."""

import logging

logger = logging.getLogger(__name__)


async def execute_scheduled_task(task_id: int) -> None:
    """Execute a ScheduledTask by ID and update its state.

    Loads the task from the database, runs its prompt through the agent, posts
    the response to the target channel, then updates the task state:

    * ``type='once'``:      sets ``enabled=False`` and ``last_run=now()`` after firing.
    * ``type='recurring'``: sets ``last_run=now()`` only.
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from grug.agent.core import GrugAgent
    from grug.bot.client import get_bot
    from grug.db.models import ScheduledTask
    from grug.db.session import get_session_factory

    factory = get_session_factory()

    # Load the task
    async with factory() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            logger.warning("execute_scheduled_task: task %d not found", task_id)
            return
        # Snapshot fields before the session closes
        guild_id = task.guild_id
        channel_id = task.channel_id
        prompt = task.prompt
        user_id = task.user_id or 0
        task_type = task.type

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
    execution_message = (
        f"[SCHEDULED TASK — execute immediately, do NOT create a new reminder or "
        f"scheduled task]: {prompt}"
    )
    response = await agent.respond(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=user_id,
        username="Grug Scheduler",
        message=execution_message,
    )
    await channel.send(response)

    # Update task state
    now = datetime.now(timezone.utc)
    async with factory() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            task.last_run = now
            if task_type == "once":
                task.enabled = False
            await session.commit()
