"""Discord bot interface for the Grug assistant server."""

import asyncio

import discord
import discord.utils
from discord import app_commands
from loguru import logger

from grug.assistant_interfaces.discord_interface.attendance import DiscordAttendanceCheckView
from grug.assistant_interfaces.discord_interface.food import DiscordFoodBringerSelectionView
from grug.bg_task_manager import track_background_task
from grug.db import async_session
from grug.log_config import InterceptHandler
from grug.models_crud import (
    get_or_create_discord_server,
    get_or_create_discord_text_channel,
    upsert_discord_user_account,
)
from grug.openai_assistant import assistant
from grug.settings import settings

_intents = discord.Intents.default()
_intents.members = True
_max_discord_message_length = 2000


discord_bot = discord.Client(intents=_intents)
discord.utils.setup_logging(handler=InterceptHandler())
tree = app_commands.CommandTree(discord_bot)

# TODO: add event listener to add users to grug when they are added to the discord server
# TODO: add event listener to remove the discord server from grug when the bot is removed from the server in discord
# TODO: make it so that when grug deletes a discord server model, the bot leaves the discord server too
# TODO: create a modal that allows users to adjust when the next scheduled event is.  in case something is different
#       for the next coming session.


def init_discord_bot():
    """Start the Discord bot."""
    if settings.discord:
        discord_bot_task = asyncio.create_task(discord_bot.start(settings.discord.bot_token.get_secret_value()))
        track_background_task(task=discord_bot_task, on_error_callback=init_discord_bot)
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
            discord_server = await get_or_create_discord_server(guild=guild, db_session=session)

            # Create Discord accounts for all members in the guild
            for member in guild.members:
                if not member.bot and member.id not in [user.discord_member_id for user in discord_server.group.users]:
                    logger.info(f"Initializing guild member {member.name} (ID: {member.id})")
                    await upsert_discord_user_account(member=member, discord_server=discord_server, db_session=session)

    # Add persistent views to the discord bot
    discord_bot.add_view(view=DiscordAttendanceCheckView())
    discord_bot.add_view(view=DiscordFoodBringerSelectionView(discord_server.group))

    logger.info(f"Logged in as {discord_bot.user} (ID: {discord_bot.user.id})")


@tree.command(
    name=f"about_{settings.openai_assistant_name.lower().replace(' ', '_')}",
    description=f"Get information about the {settings.openai_assistant_name} assistant.",
)
async def about_command(interaction: discord.Interaction):
    # noinspection PyUnresolvedReferences
    await interaction.response.send_message(settings.openai_assistant_about)


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
            await get_or_create_discord_server(guild=message.guild, db_session=session) if message.guild else None
        )
        user = await upsert_discord_user_account(
            member=message.author,
            discord_server=discord_server,
            db_session=session,
        )

        # Send the message to the assistant and get the response
        assistant_response = await assistant.send_direct_message(
            message=message.content,
            user=user,
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
        discord_text_channel = await get_or_create_discord_text_channel(channel=message.channel, session=session)
        user = await upsert_discord_user_account(
            member=message.author,
            discord_server=discord_text_channel.discord_server,
            db_session=session,
        )

        # Send the message to the assistant and get the response
        if discord_text_channel.assistant_thread_id:
            assistant_response = await assistant.send_group_message(
                message=message.content,
                thread_id=discord_text_channel.assistant_thread_id,
                user=user,
                group=discord_text_channel.discord_server.group,
            )
        else:
            assistant_response = await assistant.send_group_message(
                message=message.content,
                user=user,
                group=discord_text_channel.discord_server.group,
            )

            # Save the assistant thread ID to the database
            discord_text_channel.assistant_thread_id = assistant_response.thread_id
            session.add(discord_text_channel)
            await session.commit()

        # Send the response back to the channel
        await message.reply(assistant_response.response, suppress_embeds=False)
