"""Main entry point for the grug package."""

import asyncio

from loguru import logger

from grug.bot_discord import discord_bot
from grug.db import init_db
from grug.scheduler import grug_scheduler, update_default_schedules
from grug.settings import settings


async def main():
    """Main entry point for the grug package."""
    logger.info({"settings": settings.dict()})

    init_db()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(grug_scheduler.run_until_stopped())
        tg.create_task(update_default_schedules())
        tg.create_task(
            discord_bot.start(token=settings.discord_bot_token.get_secret_value())
        )


if __name__ == "__main__":
    asyncio.run(main())
