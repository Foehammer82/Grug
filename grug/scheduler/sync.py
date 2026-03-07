"""Startup and periodic sync for Grug.

Ensures that the bot's in-memory scheduler, Discord slash-command tree, and
database state are all consistent.  Call ``run_sync`` once at startup and
schedule it to run periodically so any drift is automatically corrected.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from grug.db.models import Character, ScheduledTask
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
                            timezone=task.timezone,
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


async def daily_pathbuilder_sync() -> None:
    """Re-sync all Pathbuilder-linked characters that haven't been synced today.

    Skips any character whose ``pathbuilder_synced_at`` is within the last
    5 minutes (respects the global cooldown set by manual/campaign syncs).
    Runs silently and logs per-character errors rather than aborting the batch.
    """
    from grug.character.pathbuilder import PathbuilderError, fetch_pathbuilder_character

    factory = get_session_factory()
    cooldown = timedelta(minutes=5)
    now = datetime.now(timezone.utc)
    synced = 0
    skipped = 0
    errors = 0

    async with factory() as session:
        result = await session.execute(
            select(Character).where(Character.pathbuilder_id.is_not(None))
        )
        characters = result.scalars().all()

        for character in characters:
            if (
                character.pathbuilder_synced_at is not None
                and (now - character.pathbuilder_synced_at) < cooldown
            ):
                skipped += 1
                continue
            try:
                structured_data = await fetch_pathbuilder_character(
                    character.pathbuilder_id
                )  # type: ignore[arg-type]
                character.structured_data = structured_data
                new_name = structured_data.get("name")
                if new_name:
                    character.name = new_name
                character.system = "pf2e"
                character.pathbuilder_synced_at = now
                synced += 1
            except PathbuilderError:
                logger.warning(
                    "Daily Pathbuilder sync: character %d (id=%d) not found or fetch failed",
                    character.id,
                    character.pathbuilder_id or 0,
                )
                errors += 1
            except Exception:
                logger.exception(
                    "Daily Pathbuilder sync: unexpected error for character %d",
                    character.id,
                )
                errors += 1

        if synced:
            await session.commit()

    logger.info(
        "Daily Pathbuilder sync complete: %d synced, %d skipped (cooldown), %d errors.",
        synced,
        skipped,
        errors,
    )


def schedule_daily_pathbuilder_sync() -> None:
    """Register a daily APScheduler cron job to sync all Pathbuilder-linked characters at 03:00 UTC."""
    from apscheduler.triggers.cron import CronTrigger

    scheduler = get_scheduler()
    job_id = "pathbuilder_daily_sync"
    scheduler.add_job(
        daily_pathbuilder_sync,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Daily Pathbuilder sync scheduled at 03:00 UTC (job id: %s).", job_id)


async def hourly_llm_usage_rollup() -> None:
    """Re-aggregate raw LLM usage records into the daily aggregate table.

    Runs every hour to ensure :class:`~grug.db.models.LLMUsageDailyAggregate`
    stays current and consistent.  The job deletes existing aggregate rows for
    the last two calendar days (UTC) and rebuilds them from the raw
    :class:`~grug.db.models.LLMUsageRecord` table.

    Using DELETE + INSERT avoids the PostgreSQL NULL-uniqueness quirk where
    ``NULL != NULL`` in UNIQUE constraints, which would cause per-call upserts
    to insert duplicate rows for background tasks that carry no ``guild_id`` or
    ``user_id``.

    Errors are caught and logged so a transient DB failure never crashes the
    scheduler loop.
    """
    from sqlalchemy import cast, delete, func, select
    from sqlalchemy.types import Date

    from grug.db.models import LLMUsageDailyAggregate, LLMUsageRecord

    now = datetime.now(timezone.utc)
    # Refresh yesterday and today (two calendar days).  Using yesterday as the
    # lower bound means the WHERE clause ``date >= since_date`` covers both days,
    # handling timezone edge-cases that fall near midnight UTC.
    since_date = (now - timedelta(days=1)).date()
    since_dt = datetime(
        since_date.year, since_date.month, since_date.day, tzinfo=timezone.utc
    )

    try:
        factory = get_session_factory()
        async with factory() as session:
            # Remove stale aggregates for the refresh window.
            await session.execute(
                delete(LLMUsageDailyAggregate).where(
                    LLMUsageDailyAggregate.date >= since_date
                )
            )

            # Re-aggregate from raw records.
            date_col = cast(LLMUsageRecord.created_at, Date)
            result = await session.execute(
                select(
                    date_col.label("date"),
                    LLMUsageRecord.guild_id,
                    LLMUsageRecord.user_id,
                    LLMUsageRecord.model,
                    LLMUsageRecord.call_type,
                    func.count().label("request_count"),
                    func.sum(LLMUsageRecord.input_tokens).label("input_tokens"),
                    func.sum(LLMUsageRecord.output_tokens).label("output_tokens"),
                )
                .where(LLMUsageRecord.created_at >= since_dt)
                .group_by(
                    date_col,
                    LLMUsageRecord.guild_id,
                    LLMUsageRecord.user_id,
                    LLMUsageRecord.model,
                    LLMUsageRecord.call_type,
                )
            )
            rows = result.all()

            for row in rows:
                session.add(
                    LLMUsageDailyAggregate(
                        date=row.date,
                        guild_id=row.guild_id,
                        user_id=row.user_id,
                        model=row.model,
                        call_type=row.call_type,
                        request_count=int(row.request_count),
                        input_tokens=int(row.input_tokens),
                        output_tokens=int(row.output_tokens),
                    )
                )

            await session.commit()
            logger.info(
                "LLM usage hourly rollup complete: %d aggregate row(s) refreshed.",
                len(rows),
            )
    except Exception:
        logger.exception("LLM usage hourly rollup failed")


def schedule_hourly_llm_usage_rollup() -> None:
    """Register an hourly APScheduler job to roll up LLM usage into daily aggregates."""
    from apscheduler.triggers.cron import CronTrigger

    scheduler = get_scheduler()
    job_id = "llm_usage_hourly_rollup"
    scheduler.add_job(
        hourly_llm_usage_rollup,
        trigger=CronTrigger(minute=0, timezone="UTC"),  # fires at the top of every hour
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(
        "LLM usage hourly rollup scheduled at :00 each hour (job id: %s).", job_id
    )


# ---------------------------------------------------------------------------
# Manager agent periodic review
# ---------------------------------------------------------------------------


async def _run_manager_reviews() -> None:
    """Run a manager review for every guild that has the feature enabled.

    Iterates over all GuildConfig rows and runs a review for each.
    Errors for individual guilds are logged and do not block other guilds.
    """
    from grug.config.settings import get_settings
    from grug.db.models import GuildConfig

    settings = get_settings()
    if not settings.manager_review_enabled:
        return

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(GuildConfig.guild_id))
        guild_ids = list(result.scalars().all())

    if not guild_ids:
        logger.info("Manager review: no guilds to review.")
        return

    from grug.manager.reviewer import run_review

    for gid in guild_ids:
        try:
            await run_review(gid)
            logger.info("Manager review completed for guild %d", gid)
        except Exception:
            logger.exception("Manager review failed for guild %d", gid)


def schedule_manager_reviews() -> None:
    """Register a periodic APScheduler job for manager reviews.

    The cron schedule is read from ``Settings.manager_review_cron``.
    Only registers the job if ``Settings.manager_review_enabled`` is True.
    """
    from grug.config.settings import get_settings
    from grug.scheduler.manager import unix_cron_to_trigger

    settings = get_settings()
    if not settings.manager_review_enabled:
        logger.info("Manager reviews disabled — skipping scheduler registration.")
        return

    scheduler = get_scheduler()
    job_id = "manager_review"
    trigger = unix_cron_to_trigger(settings.manager_review_cron, timezone="UTC")
    scheduler.add_job(
        _run_manager_reviews,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info(
        "Manager review scheduled with cron '%s' (job id: %s).",
        settings.manager_review_cron,
        job_id,
    )
