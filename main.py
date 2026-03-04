"""Entry point for Grug Discord bot."""

import asyncio
import logging
import sys
from pathlib import Path

import discord

from grug.bot.client import create_bot, set_bot
from grug.config.settings import get_settings
from grug.db.session import init_db
from grug.scheduler.manager import start_scheduler
from grug.scheduler.sync import (
    run_sync,
    schedule_daily_pathbuilder_sync,
    schedule_periodic_sync,
)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting Grug...")

    # Initialise database
    logger.info("Initialising database...")
    await init_db()
    logger.info("Database ready.")

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
        # Write a sentinel file so the Docker HEALTHCHECK can confirm the bot
        # successfully connected to Discord and reached the ready state.
        Path("/tmp/healthy").touch()
        start_scheduler()
        await run_sync(bot, sync_commands=True)
        schedule_periodic_sync(bot)
        schedule_daily_pathbuilder_sync()

    # Load cogs
    await bot.load_extension("grug.bot.cogs.ai_chat")
    await bot.load_extension("grug.bot.cogs.documents")
    await bot.load_extension("grug.bot.cogs.admin")
    await bot.load_extension("grug.bot.cogs.glossary")
    await bot.load_extension("grug.bot.cogs.campaigns")
    await bot.load_extension("grug.bot.cogs.characters")

    # Pre-warm the agent so any init errors surface at startup, not on first message.
    logger.info("Pre-warming agent...")
    try:
        from grug.agent.core import get_agent

        get_agent()
        logger.info("Agent ready.")
    except Exception:
        logger.exception(
            "Agent failed to initialise — bot will start but responses may fail."
        )

    logger.info("Starting Discord bot...")
    try:
        await bot.start(settings.discord_token)
    finally:
        from grug.scheduler.manager import stop_scheduler

        stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
