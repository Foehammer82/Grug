"""Entry point for Grug Discord bot."""

import asyncio
import logging
import sys

import discord

from grug.bot.client import create_bot, set_bot
from grug.config.settings import get_settings
from grug.db.session import get_session_factory, init_db
from grug.db.models import ScheduledTask
from grug.scheduler.manager import add_cron_job, start_scheduler
from grug.scheduler.tasks import run_scheduled_prompt


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


async def load_scheduled_tasks(bot) -> None:
    """Re-register all enabled scheduled tasks from the database on startup."""
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.enabled.is_(True))  # noqa: E712
        )
        tasks = result.scalars().all()

    for task in tasks:
        job_id = f"task_{task.id}"
        try:
            add_cron_job(
                run_scheduled_prompt,
                cron_expression=task.cron_expression,
                job_id=job_id,
                args=[task.id, task.guild_id, task.channel_id, task.prompt],
            )
            logging.getLogger(__name__).info(
                "Restored scheduled task %d: %s", task.id, task.name
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to restore task %d: %s", task.id, exc
            )


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting Grug...")

    # Initialise database
    await init_db()

    # Create bot
    bot = create_bot()
    set_bot(bot)

    @bot.event
    async def on_ready():
        logger.info("Grug online as %s (ID: %s)", bot.user, bot.user.id)
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for adventures 🗡️",
            )
        )
        start_scheduler()
        await load_scheduled_tasks(bot)

    # Load cogs
    await bot.load_extension("grug.bot.cogs.ai_chat")
    await bot.load_extension("grug.bot.cogs.documents")
    await bot.load_extension("grug.bot.cogs.admin")

    logger.info("Starting Discord bot...")
    try:
        await bot.start(settings.discord_token)
    finally:
        from grug.scheduler.manager import stop_scheduler
        stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
