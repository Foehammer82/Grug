"""Discord bot interface for the Grug assistant server."""

import asyncio

import discord
import discord.utils
from loguru import logger

from grug.assistant_interfaces.discord_interface.attendance import DiscordAttendanceCheckView
from grug.db import async_session
from grug.log_config import InterceptHandler
from grug.models import DiscordAccount, DiscordServer, DiscordTextChannel
from grug.openai_assistant import assistant
from grug.settings import settings

_intents = discord.Intents.default()
_intents.members = True
_max_discord_message_length = 2000


discord_bot = discord.Client(intents=_intents)
discord.utils.setup_logging(handler=InterceptHandler())


def init_discord_bot():
    """Start the Discord bot."""
    if settings.discord:
        discord_bot_task = asyncio.create_task(discord_bot.start(settings.discord.bot_token.get_secret_value()))
        logger.info(f"Discord Bot started with task ID {discord_bot_task}")


def get_bot_invite_url() -> str | None:
    return (
        f"https://discord.com/api/oauth2/authorize?client_id={discord_bot.user.id}&permissions=8&scope=bot"
        if discord_bot.user
        else None
    )


@discord_bot.event
async def on_ready():
    """
    Event handler for when the bot is ready.

    Documentation: https://discordpy.readthedocs.io/en/stable/api.html#discord.on_ready
    """

    # Make sure all the guilds are loaded in the server
    logger.info("Loading guilds...")
    async with async_session() as session:
        for guild in discord_bot.guilds:
            logger.info(f"Initializing guild {guild.name} (ID: {guild.id})")
            discord_server = await DiscordServer.get_or_create(guild=guild, db_session=session)

            # Create Discord accounts for all members in the guild
            # TODO: setup as a background task so it doesn't slow down startup
            if settings.discord.auto_create_users:
                for member in guild.members:
                    if not member.bot:
                        logger.info(f"Initializing guild member {member.name} (ID: {member.id})")
                        await DiscordAccount.get_or_create(
                            member=member, discord_server=discord_server, db_session=session
                        )

    discord_bot.add_view(view=DiscordAttendanceCheckView())
    logger.info(f"Persistent Views: {discord_bot.persistent_views}")

    logger.info(f"Logged in as {discord_bot.user} (ID: {discord_bot.user.id})")


@discord_bot.event
async def on_message(message: discord.Message):
    """on_message event handler for the Discord bot."""

    async with async_session() as session:
        # ignore messages from self and all bots
        if message.author == discord_bot.user or message.author.bot:
            pass

        # respond to DMs
        elif isinstance(message.channel, discord.DMChannel):
            await _respond_to_dm(message, session)

        # respond to @mentions in channels
        elif (
            isinstance(message.channel, discord.TextChannel) or isinstance(message.channel, discord.Thread)
        ) and discord_bot.user in message.mentions:
            await _respond_to_text_channel_mention(message, session)


async def _respond_to_dm(message: discord.Message, session: async_session):
    """
    Respond to a direct message from a user.

    Args:
        message (discord.Message): The message from the user.
    """
    async with message.channel.typing():
        # Get the Discord account for the user
        discord_server = (
            await DiscordServer.get_or_create(guild=message.guild, db_session=session) if message.guild else None
        )
        discord_account = await DiscordAccount.get_or_create(
            member=message.author,
            discord_server=discord_server,
            db_session=session,
        )

        # Send the message to the assistant and get the response
        assistant_response = await assistant.send_direct_message(
            message=message.content,
            user=discord_account.user,
            session=session,
        )

        # Send the response back to the user
        for output in [
            assistant_response.response[i : i + _max_discord_message_length]
            for i in range(0, len(assistant_response.response), _max_discord_message_length)
        ]:
            await message.channel.send(output, suppress_embeds=False)


async def _respond_to_text_channel_mention(message: discord.Message, session: async_session):
    """
    Respond to a message in a channel where the bot was mentioned.

    Args:
        message (discord.Message): The message from the user.
    """
    async with message.channel.typing():
        # Get the Discord account for the user
        discord_text_channel = await DiscordTextChannel.get_or_create(channel=message.channel, session=session)
        discord_account = await DiscordAccount.get_or_create(
            member=message.author,
            discord_server=discord_text_channel.discord_server,
            db_session=session,
        )

        # Send the message to the assistant and get the response
        if discord_text_channel.assistant_thread_id:
            assistant_response = await assistant.send_group_message(
                message=message.content,
                thread_id=discord_text_channel.assistant_thread_id,
                user=discord_account.user,
                group=discord_text_channel.discord_server.group,
            )
        else:
            assistant_response = await assistant.send_group_message(
                message=message.content,
                user=discord_account.user,
                group=discord_text_channel.discord_server.group,
            )

            # Save the assistant thread ID to the database
            discord_text_channel.assistant_thread_id = assistant_response.thread_id
            session.add(discord_text_channel)
            await session.commit()

        # Send the response back to the channel
        await message.reply(assistant_response.response, suppress_embeds=False)
