"""Discord bot interface for the Grug assistant server."""

import logging
from collections.abc import Iterable

import discord
import discord.utils
from loguru import logger
from sqlmodel import select

from grug.db import async_session
from grug.models import DiscordTextChannel, Player
from grug.openai_assistant import assistant
from grug.settings import settings
from grug.utils.food import DiscordFoodBringerSelectionView

# Grug bot invite link:
# https://discord.com/api/oauth2/authorize?client_id=1059330324313690223&permissions=8&scope=bot]


_intents = discord.Intents.default()
_intents.members = True


class InterceptLogHandler(logging.Handler):
    """Intercepts log messages and sends them to the logger."""

    def emit(self, record):
        """Emit the log message to the logger."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


discord_bot = discord.Client(intents=_intents)
discord.utils.setup_logging(handler=InterceptLogHandler())

# TODO: add a check or something that won't let this bot connect to a server other than what is assigned in
#       the settings


@discord_bot.event
async def on_ready():
    """
    Event handler for when the bot is ready.

    Documentation: https://discordpy.readthedocs.io/en/stable/api.html#discord.on_ready
    """
    guild = discord_bot.get_guild(settings.discord_server_id)
    players = await _add_discord_members_to_db_as_players(discord_members=guild.members)

    # Register the persistent view for listening
    discord_bot.add_view(DiscordFoodBringerSelectionView(players))

    logger.info(f"Logged in as {discord_bot.user} (ID: {discord_bot.user.id})")


async def _respond_to_dm(message: discord.Message):
    """
    Respond to a direct message from a user.

    Args:
        message (discord.Message): The message from the user.
    """
    async with message.channel.typing():
        # Get the user
        async with async_session() as session:
            result = await session.execute(
                select(Player)
                .where(Player.discord_member_id == str(message.author.id))
                .where(Player.discord_guild_id == str(settings.discord_server_id))
            )
            db_user: Player | None = result.scalars().one_or_none()

        # Send the message to the assistant
        assistant_response = await assistant.send_direct_message(
            message=message.content, player=db_user
        )

        max_discord_message_length = 2000
        for output in [
            assistant_response.response[i : i + max_discord_message_length]
            for i in range(
                0, len(assistant_response.response), max_discord_message_length
            )
        ]:
            await message.channel.send(output)


async def _respond_to_channel_mention(message: discord.Message):
    """
    Respond to a message in a channel where the bot was mentioned.

    Args:
        message (discord.Message): The message from the user.
    """
    async with message.channel.typing():
        async with async_session() as session:
            # Check if the channel is already tied to a thread
            result = await session.execute(
                select(DiscordTextChannel).where(
                    DiscordTextChannel.discord_id == str(message.channel.id)
                )
            )
            discord_channel: DiscordTextChannel | None = result.scalars().one_or_none()

            # Get the user
            result = await session.execute(
                select(Player)
                .where(Player.discord_member_id == str(message.author.id))
                .where(Player.discord_guild_id == str(settings.discord_server_id))
            )
            player: Player | None = result.scalars().one_or_none()

            if discord_channel and discord_channel.assistant_thread_id:
                assistant_response = await assistant.send_group_message(
                    message=message.content,
                    thread_id=discord_channel.assistant_thread_id,
                    player=player,
                )

            else:
                assistant_response = await assistant.send_group_message(
                    message=message.content,
                    player=player,
                )

                if discord_channel:
                    discord_channel.assistant_thread_id = assistant_response.thread_id
                    session.add(discord_channel)
                else:
                    session.add(
                        DiscordTextChannel(
                            discord_id=str(message.channel.id),
                            assistant_thread_id=assistant_response.thread_id,
                        )
                    )

                await session.commit()

            # Send the response back to the channel
            await message.reply(assistant_response.response)


@discord_bot.event
async def on_message(message: discord.Message):
    """on_message event handler for the Discord bot."""

    # ignore messages from self and all bots
    if message.author == discord_bot.user or message.author.bot:
        pass

    # respond to DMs
    elif isinstance(message.channel, discord.DMChannel):
        await _respond_to_dm(message)

    # respond to @mentions in channels
    elif (
        isinstance(message.channel, discord.TextChannel)
        and discord_bot.user in message.mentions
    ):
        await _respond_to_channel_mention(message)


@discord_bot.event
async def on_guild_join(guild: discord.Guild):
    """https://discordpy.readthedocs.io/en/stable/api.html#discord.on_guild_join"""
    players = await _add_discord_members_to_db_as_players(discord_members=guild.members)

    # Update the food bringer selection view with the new players
    discord_bot.add_view(
        DiscordFoodBringerSelectionView(
            [p for p in players if p.is_active and p.brings_food]
        )
    )


@discord_bot.event
async def on_member_join(member: discord.Member):
    """https://discordpy.readthedocs.io/en/stable/api.html#discord.on_member_join"""

    async with async_session() as session:
        if not member.bot:
            result = await session.execute(
                select(Player)
                .where(Player.discord_member_id == str(member.id))
                .where(Player.discord_guild_id == str(member.guild.id))
            )
            existing_player: Player | None = result.scalars().one_or_none()

            if existing_player is None:
                session.add(
                    Player(
                        discord_member_id=str(member.id),
                        discord_guild_id=str(member.guild.id),
                        discord_username=member.name,
                    )
                )
                logger.info(f"Added player {member.name} to the database.")
            elif not existing_player.is_active:
                existing_player.is_active = True
                session.add(existing_player)
                logger.info(f"Set player {member.name} to active in the database.")

        await session.commit()


async def _add_discord_members_to_db_as_players(
    discord_members: Iterable[discord.Member],
):
    """
    Add Discord members to the database as Players if they do not already exist.

    Args:
        discord_members (Iterable[discord.Member]): An iterable of discord.Member objects.
    """

    players: list[Player] = []

    async with async_session() as session:
        for member in discord_members:
            if not member.bot:
                result = await session.execute(
                    select(Player)
                    .where(Player.discord_member_id == str(member.id))
                    .where(Player.discord_guild_id == str(member.guild.id))
                )
                player: Player | None = result.scalars().one_or_none()

                if player is None:
                    player = Player(
                        discord_member_id=str(member.id),
                        discord_guild_id=str(member.guild.id),
                        discord_username=member.name,
                    )

                    session.add(player)
                    await session.commit()
                    await session.refresh(player)

                players.append(player)

    return players
