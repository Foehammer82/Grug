"""Concrete scheduled-task callbacks for Grug."""

import logging

import discord
from sqlalchemy import select

from grug.db.models import CalendarEvent
from grug.db.session import get_session_factory as _get_factory

logger = logging.getLogger(__name__)

# Sentinel guild_id used for personal (DM) tasks created outside a Discord guild.
_DM_GUILD_ID = 0


async def _build_event_reminder_embed(
    event_id: int, prompt: str
) -> tuple[discord.Embed | None, discord.ui.View]:
    """Build a reminder embed + RSVP view for an event-linked task.

    Returns ``(None, ...)`` if the event no longer exists.
    """
    from grug.bot.views.event_rsvp import build_event_embed, create_rsvp_view

    factory = _get_factory()
    async with factory() as session:
        result = await session.execute(
            select(CalendarEvent).where(CalendarEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event is None:
            return None, discord.ui.View()
        await session.refresh(event, ["rsvps"])

        # Derive a friendly label from the prompt — e.g. "starts in 1 hour"
        reminder_label = None
        prompt_lower = prompt.lower()
        if "1 h" in prompt_lower or "1 hour" in prompt_lower:
            reminder_label = "Starts in 1 hour!"
        elif "24 h" in prompt_lower or "24 hour" in prompt_lower:
            reminder_label = "Starts in 24 hours"

        embed = await build_event_embed(event, reminder_label=reminder_label)
        view = create_rsvp_view(event_id)
        return embed, view


async def _send_channel_rest(channel_id: int, content: str) -> None:
    """Send a message to a Discord channel using the bot token via REST API.

    Works in any process (bot or API) as long as a bot token is configured.
    Long messages are truncated to Discord's 2000-character limit.
    """
    import httpx

    from grug.config.settings import get_settings

    settings = get_settings()
    bot_token = settings.discord_bot_token or settings.discord_token
    if not bot_token:
        logger.error(
            "No bot token configured; cannot send message to channel %d", channel_id
        )
        return

    headers = {"Authorization": f"Bot {bot_token}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            truncated = content[:2000] if len(content) > 2000 else content
            r = await http.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                json={"content": truncated},
            )
            r.raise_for_status()
    except Exception:
        logger.exception(
            "Failed to send message to channel %d via REST API", channel_id
        )


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


async def execute_scheduled_task(task_id: int, triggered_by: str = "scheduled") -> None:
    """Execute a ScheduledTask by ID and update its state.

    Loads the task from the database, runs its prompt through the agent, then
    delivers the response:

    * Personal tasks (``guild_id == 0``): delivered as a Discord DM to the
      owning user via the REST API.  Works in both the bot and API processes.
    * Guild tasks: posted to the target channel via the Discord bot instance
      if available, otherwise via the Discord REST API.

    Task state is updated after delivery:

    * ``type='once'``:      deleted after firing to keep the DB tidy.
    * ``type='recurring'``: sets ``last_run=now()`` only.

    A ``ScheduledTaskRun`` record is always created so guild admins have an
    audit trail of when each task fired and what Grug responded.

    Args:
        task_id: Primary key of the ``ScheduledTask`` to execute.
        triggered_by: ``'scheduled'`` (APScheduler) or ``'manual'`` (web UI).
    """
    from datetime import datetime, timezone

    from grug.agent.core import GrugAgent
    from grug.db.models import ScheduledTask, ScheduledTaskRun

    factory = _get_factory()

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
        linked_event_id = task.event_id

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
        # Guild task — post to the target channel via the Discord bot if
        # available, otherwise fall back to the REST API (e.g. web-triggered).
        from grug.bot.client import get_bot

        bot = get_bot()
        if bot is None:
            await _send_channel_rest(channel_id, response)
        else:
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
                    # Still record the run even if delivery failed.
                    channel = None
            if channel is not None:
                await channel.send(response)

        # For event-linked reminders, also send a rich embed with RSVP buttons.
        if linked_event_id:
            try:
                embed, view = await _build_event_reminder_embed(linked_event_id, prompt)
                if embed is not None:
                    from grug.bot.client import get_bot as _get_bot

                    _bot = _get_bot()
                    if _bot is not None:
                        _chan = _bot.get_channel(channel_id)
                        if _chan is not None:
                            await _chan.send(embed=embed, view=view)
            except Exception:
                logger.exception(
                    "Failed to send RSVP embed for event %d", linked_event_id
                )

    # Update task state and record the run.
    now = datetime.now(timezone.utc)
    async with factory() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        # Always record the run for audit / history purposes.
        run = ScheduledTaskRun(
            task_id=task_id if task is not None else None,
            guild_id=guild_id,
            ran_at=now,
            triggered_by=triggered_by,
            response=response,
            success=True,
        )
        session.add(run)

        if task:
            if task_type == "once":
                # One-shot tasks are deleted after firing to keep history clean.
                await session.delete(task)
            else:
                task.last_run = now
        await session.commit()

    # If this was an event-linked reminder, refresh reminders for
    # the next occurrence of the recurring event.
    if linked_event_id and task_type == "once":
        try:
            from grug.event_reminders import refresh_event_reminders

            await refresh_event_reminders(linked_event_id)
        except Exception:
            logger.exception(
                "Failed to refresh reminders for event %d after task %d fired",
                linked_event_id,
                task_id,
            )
        # Auto-create an availability poll if the campaign uses poll
        # scheduling (non-blocking — failures are logged, not raised).
        try:
            from grug.event_reminders import maybe_create_schedule_poll

            await maybe_create_schedule_poll(linked_event_id)
        except Exception:
            logger.exception(
                "Failed to create schedule poll for event %d",
                linked_event_id,
            )
