"""Startup and periodic sync for Grug.

Ensures that the bot's in-memory scheduler, Discord slash-command tree, and
database state are all consistent.  Call ``run_sync`` once at startup and
schedule it to run periodically so any drift is automatically corrected.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from grug.db.models import ScheduledTask
from grug.db.session import get_session_factory
from grug.scheduler.manager import add_cron_job, add_date_job, get_scheduler
from grug.scheduler.tasks import execute_scheduled_task
from grug.utils import ensure_guild

if TYPE_CHECKING:
    from discord.ext import commands

logger = logging.getLogger(__name__)

# How often (in minutes) the periodic sync runs.
SYNC_INTERVAL_MINUTES = 30


async def run_sync(bot: "commands.Bot", *, sync_commands: bool = False) -> None:
    """Perform a full sync pass.

    Steps:
      1. Ensure every guild Grug is in has a ``GuildConfig`` DB row.
      2. Reconcile APScheduler jobs with enabled ``ScheduledTask`` DB rows —
         add missing jobs and remove orphaned ones.  Both ``once`` and
         ``recurring`` task types are handled.
      3. Optionally sync the Discord slash-command tree (only on startup to
         avoid Discord's rate limits on repeated tree syncs).

    Args:
        bot: The running Discord bot instance.
        sync_commands: When ``True``, also sync slash commands with Discord.
    """
    logger.info("Running sync pass (sync_commands=%s)…", sync_commands)

    # ------------------------------------------------------------------
    # 1. Guild configs
    # ------------------------------------------------------------------
    guilds_seeded = 0
    for guild in bot.guilds:
        try:
            await ensure_guild(guild.id)
            guilds_seeded += 1
        except Exception:
            logger.exception(
                "Failed to ensure guild config for guild %d (%s)", guild.id, guild.name
            )

    logger.info("Guild config sync: %d guild(s) verified.", guilds_seeded)

    # ------------------------------------------------------------------
    # 1b. Ensure the grug-admin role exists in every guild
    # ------------------------------------------------------------------
    from grug.bot.cogs.admin import ensure_grug_admin_role

    roles_synced = 0
    for guild in bot.guilds:
        try:
            await ensure_grug_admin_role(guild)
            roles_synced += 1
        except Exception:
            logger.exception(
                "Failed to ensure grug-admin role for guild %d (%s)",
                guild.id,
                guild.name,
            )

    logger.info("grug-admin role sync: %d guild(s) processed.", roles_synced)

    # ------------------------------------------------------------------
    # 2. Scheduled tasks — reconcile DB ↔ APScheduler
    # ------------------------------------------------------------------
    try:
        factory = get_session_factory()
        now = datetime.now(timezone.utc)
        async with factory() as session:
            result = await session.execute(
                select(ScheduledTask).where(
                    ScheduledTask.enabled.is_(True),
                    # Personal DM tasks (guild_id=0) are registered immediately
                    # by the API process; skip them here to avoid double execution.
                    ScheduledTask.guild_id != 0,
                )
            )
            db_tasks = result.scalars().all()

        scheduler = get_scheduler()
        existing_job_ids = {j.id for j in scheduler.get_jobs()}
        expected_job_ids: set[str] = set()
        tasks_added = 0
        tasks_removed = 0

        for task in db_tasks:
            job_id = f"task_{task.id}"

            if task.type == "once":
                # Skip one-shot tasks that have already fired or have no fire time.
                if task.fire_at is None or task.last_run is not None:
                    continue
                # Skip if the fire time is already in the past (missed entirely).
                if task.fire_at <= now:
                    logger.warning(
                        "Sync: one-shot task %d fire_at is in the past (%s); skipping re-register",
                        task.id,
                        task.fire_at.isoformat(),
                    )
                    continue
                expected_job_ids.add(job_id)
                if job_id not in existing_job_ids:
                    try:
                        add_date_job(
                            execute_scheduled_task,
                            run_date=task.fire_at,
                            job_id=job_id,
                            args=[task.id],
                        )
                        tasks_added += 1
                        logger.info(
                            "Sync: registered missing one-shot task %d", task.id
                        )
                    except Exception:
                        logger.exception(
                            "Sync: failed to register one-shot task %d", task.id
                        )

            else:  # 'recurring'
                if not task.cron_expression:
                    logger.warning(
                        "Sync: recurring task %d has no cron_expression; skipping",
                        task.id,
                    )
                    continue
                expected_job_ids.add(job_id)
                if job_id not in existing_job_ids:
                    try:
                        add_cron_job(
                            execute_scheduled_task,
                            cron_expression=task.cron_expression,
                            job_id=job_id,
                            args=[task.id],
                        )
                        tasks_added += 1
                        logger.info(
                            "Sync: registered missing recurring task %d (%s)",
                            task.id,
                            task.name,
                        )
                    except Exception:
                        logger.exception(
                            "Sync: failed to register recurring task %d (%s)",
                            task.id,
                            task.name,
                        )

        # Remove APScheduler jobs whose DB task no longer exists or is disabled.
        for job_id in existing_job_ids:
            if job_id.startswith("task_") and job_id not in expected_job_ids:
                try:
                    scheduler.remove_job(job_id)
                    tasks_removed += 1
                    logger.info("Sync: removed orphaned scheduler job %s", job_id)
                except Exception:
                    logger.exception("Sync: failed to remove orphaned job %s", job_id)

        logger.info(
            "Scheduled task sync: %d added, %d removed, %d total active.",
            tasks_added,
            tasks_removed,
            len(expected_job_ids),
        )
    except Exception:
        logger.exception("Scheduled task sync failed — scheduler state may be stale")

    # ------------------------------------------------------------------
    # 3. Slash command tree (startup only)
    # ------------------------------------------------------------------
    if sync_commands:
        try:
            synced = await bot.tree.sync()
            logger.info(
                "Slash command sync: %d command(s) registered with Discord.",
                len(synced),
            )
        except Exception:
            logger.exception("Slash command sync failed")

    logger.info("Sync pass complete.")


async def periodic_sync(bot: "commands.Bot") -> None:
    """Wrapper called by APScheduler — runs a sync without command tree sync."""
    await run_sync(bot, sync_commands=False)


def schedule_periodic_sync(bot: "commands.Bot") -> None:
    """Register a recurring APScheduler job to sync every ``SYNC_INTERVAL_MINUTES`` minutes."""
    scheduler = get_scheduler()
    job_id = "grug_periodic_sync"

    # Replace any previously registered sync job (safe on reconnect).
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler.add_job(
        periodic_sync,
        trigger=IntervalTrigger(minutes=SYNC_INTERVAL_MINUTES),
        id=job_id,
        args=[bot],
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "Periodic sync scheduled every %d minutes (job id: %s).",
        SYNC_INTERVAL_MINUTES,
        job_id,
    )
