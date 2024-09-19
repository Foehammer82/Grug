"""Main entry point for the grug package."""

import asyncio

import anyio
import discord
import typer
from loguru import logger

from grug.bot_discord import discord_client
from grug.db import init_db
from grug.scheduler import start_scheduler
from grug.settings import settings

# TODO: ability to back up to a dedicated directory that a user could map to a volume to handle backups and recovery
# TODO: start having grug follow up with users and ask them what food they brought, or if they brought food and let
#       them change it to someone else for the last event.
# TODO: using twilio, add in text message reminders and if possible tooling to allow users to respond to the text
#       message to update the food and/or attendance status. (maybe just attendance to start)
# TODO: create the ability for grug to load in documents from google drives and parse them for information
# TODO: get unit test coverage up to 80%
# TODO: alternative attendance tracking (by user poll)
#       - as a user I expect to see a notification in discord that asks what day in the next n days work, I select all
#         the ones that work. later, after other users have done the same I expect to get a poll with the days that
#         work for everyone, I vote for 1, the winning date is picked and announced to everyone. or could possibly
#         save a step if everyone picks a day that is the same, it just auto-selects the first day that everyone votes
#         for Or just start with a discord poll tagging everyone with an option for every tuesday that month.
# TODO: have specific instructions and results for when users are rude or inappropriate towards grug

app = typer.Typer(no_args_is_help=True)

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
            tg.start_soon(discord_client.start, settings.discord_bot_token.get_secret_value())
            tg.start_soon(start_scheduler)
    except KeyboardInterrupt:
        pass
    logger.info("Grug has shut down...")


@app.command()
def start():
    # noinspection PyTypeChecker
    anyio.run(main)


@app.command()
def health():
    # TODO: using shelf or some other method, setup a health monitoring system that can be checked while the app is
    #       running.  raise an exception to indicate the app is unhealthy.
    print("OK")


# noinspection PyTypeChecker
@app.command()
def copy_discord_commands(guild_id: int):
    """
    Copy global commands to a specific guild.

    Args:
        guild_id: The ID of the guild to copy the commands to.
    """

    async def copy_commands():
        await discord_client.wait_until_ready()

        guild = discord.Object(id=guild_id)
        discord_client.tree.copy_global_to(guild=guild)
        await discord_client.tree.sync(guild=guild)

        logger.info(f"Copied global commands to guild ID: {guild_id}")

        # raise an exception to cancel the task
        raise asyncio.CancelledError("Commands copied successfully.")

    async def async_function():
        async with anyio.create_task_group() as tg:
            tg.start_soon(discord_client.start, settings.discord_bot_token.get_secret_value())
            tg.start_soon(copy_commands)

    # noinspection PyTypeChecker
    anyio.run(async_function)


@app.command()
def load_fake_data():
    if settings.environment == "prd":
        raise ValueError("Fake data can only be loaded in the non-prod environments.")

    # TODO: create fake data for dev and testing (should ony be able to be run in dev environment)
    raise NotImplementedError("This feature is not yet implemented.")


if __name__ == "__main__":
    app()
