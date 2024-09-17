"""Main entry point for the grug package."""

import anyio
from loguru import logger

from grug import bot_discord
from grug.db import init_db
from grug.scheduler import start_scheduler
from grug.settings import settings

# TODO: stand-alone CLI tool to accomplish admin tasks such as:
#       - export/import db data
#       - create fake data for dev and testing (should ony be able to be run in dev environment)

# TODO: grug discord commands to consider:
#       - add/remove a food bringer user option (i.e. ability to create and remove non discord users with
#         slash commands)
#       - enable/disable food and attendance tracking for the group
#       - set the bot channel id for the current group
#       - adjust the number of days prior to the event to send the reminder
#       - adjust what time of day the reminder should be sent
#       - display a current list of group settings to know what is currently set
#       - adjust user first/last name
#       - add a user phone number (for text reminders)
# TODO: start having grug follow up with users and ask them what food they brough, or if they brought food and let
#       them change it to someone else for the last event.
# TODO: using twilio, add in text message reminders and if possible tooling to allow users to respond to the text
#       message to update the food and/or attendance status. (maybe just attendance to start)
# TODO: start enabling document loading for the ai assistant (there should be another TODO on this somewhere)


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
