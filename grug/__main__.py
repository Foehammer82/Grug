"""Main entry point for the grug package."""

import anyio
from loguru import logger

from grug import bot_discord
from grug.db import init_db
from grug.scheduler import start_scheduler
from grug.settings import settings

# TODO: stand-alone CLI tool to accomplish admin tasks such as:
#       - export/import db data

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
    )


# noinspection PyTypeChecker
async def main():
    """Main application entrypoint."""
    if not settings.discord_bot_token:
        raise ValueError("`DISCORD_BOT_TOKEN` env variable is required to run the Grug bot.")
    if not settings.openai_key:
        raise ValueError("`OPENAI_KEY` env variable is required to run the Grug bot.")

    init_db()

    logger.info("Starting Grug...")
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(bot_discord.client.start, settings.discord_bot_token.get_secret_value())
            tg.start_soon(start_scheduler)
    except KeyboardInterrupt:
        pass
    logger.info("Grug has shut down...")


if __name__ == "__main__":
    anyio.run(main)
