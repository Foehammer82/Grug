"""Main entry point for the grug package."""

import asyncio

from loguru import logger

from grug.bot_discord import discord_bot
from grug.db import init_db
from grug.scheduler import grug_scheduler, update_default_schedules
from grug.settings import settings

# TODO:
#  - have grug be able to provide dalle images
#  - store group chats in postgres and create a search function for them as a tool for grug to lookup conversation
#    history.
#  - have grug be able to listen to a dnd session and take notes / summarize the session
#  - setup unit tests and functional tests and have the test reports show up in CI/CD
#  - create a frontend web app for grug to have a place to put tooling and stuff (for like file uploads, find grained
#    food scheduled controls, attendance tracking, etc)
#  - the food scheduler needs some TLC around making the reminder smarter so that it reminds for the current
#    session until the current session is complete.  and for it to check if the current session already has someone
#    assigned.  if someone is already assigned the default operation should be to send no reminder, though we will want
#    that function to have an override so that it would send who is currently scheduled and ask if it should be changed.
#    All in all, review the current food reminder workflow and make sure it's clean and intuitive.  and see if it can
#    be made more generic so that it can be an engine for more types of reminders that may or may not get feedback
#    when the reminder is sent.
#  - integrate sms capabilities so that grug can send sms reminders for food and dnd sessions
#  - create an attendance tracker for dnd sessions that sends a reminder a certain amount of time before a session to
#    get attendance


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
