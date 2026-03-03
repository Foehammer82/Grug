"""Concrete scheduled-task callbacks for Grug."""

import logging

logger = logging.getLogger(__name__)

# Sentinel guild_id used for personal (DM) tasks created outside a Discord guild.
_DM_GUILD_ID = 0


async def _send_dm_rest(user_id: int, content: str) -> None:
    """Send a Discord DM to *user_id* using the bot token via REST API.

    This works in any process (bot or API) as long as a bot token is configured.
    Long messages are truncated to Discord's 2000-character limit.
    """
    import httpx

    from grug.config.settings import get_settings

    settings = get_settings()
    bot_token = settings.discord_bot_token or settings.discord_token
    if not bot_token:
        logger.error("No bot token configured; cannot send DM to user %d", user_id)
        return

    headers = {"Authorization": f"Bot {bot_token}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            # Open (or re-use) the DM channel for this user.
            r = await http.post(
                "https://discord.com/api/v10/users/@me/channels",
                headers=headers,
                json={"recipient_id": str(user_id)},
            )
            r.raise_for_status()
            dm_channel_id = r.json()["id"]

            # Discord messages are capped at 2000 characters.
            truncated = content[:2000] if len(content) > 2000 else content
            r = await http.post(
                f"https://discord.com/api/v10/channels/{dm_channel_id}/messages",
                headers=headers,
                json={"content": truncated},
            )
            r.raise_for_status()
    except Exception:
        logger.exception("Failed to send DM to user %d via REST API", user_id)


async def execute_scheduled_task(task_id: int) -> None:
    """Execute a ScheduledTask by ID and update its state.

    Loads the task from the database, runs its prompt through the agent, then
    delivers the response:

    * Personal tasks (``guild_id == 0``): delivered as a Discord DM to the
      owning user via the REST API.  Works in both the bot and API processes.
    * Guild tasks: posted to the target channel via the Discord bot instance.

    Task state is updated after delivery:

    * ``type='once'``:      deleted after firing to keep the DB tidy.
    * ``type='recurring'``: sets ``last_run=now()`` only.
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from grug.agent.core import GrugAgent
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

    if guild_id == _DM_GUILD_ID:
        # Personal task — deliver as a DM via the Discord REST API.
        if user_id == 0:
            logger.warning(
                "Personal task %d has no user_id; cannot deliver DM", task_id
            )
        else:
            await _send_dm_rest(user_id, response)
    else:
        # Guild task — post to the target channel via the Discord bot.
        from grug.bot.client import get_bot

        bot = get_bot()
        if bot is None:
            logger.warning("Bot not initialised; skipping guild task %d", task_id)
            return

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                logger.warning(
                    "Channel %d not found for scheduled task %d",
                    channel_id,
                    task_id,
                )
                return
        await channel.send(response)

    # Update task state
    now = datetime.now(timezone.utc)
    async with factory() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            if task_type == "once":
                # One-shot tasks are deleted after firing to keep history clean.
                await session.delete(task)
            else:
                task.last_run = now
            await session.commit()
