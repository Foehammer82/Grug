"""Discord bot interface for the Grug assistant server."""

import asyncio

import discord
import discord.utils
from apscheduler import RunState
from discord import app_commands
from loguru import logger

from grug.ai import assistant
from grug.db import async_session
from grug.discord_views.attendance import DiscordAttendanceCheckView
from grug.discord_views.food import DiscordFoodBringerSelectionView
from grug.models_crud import (
    get_or_create_discord_server_group,
    get_or_create_discord_text_channel,
    get_or_create_discord_user,
)
from grug.reminders import game_session_reminder
from grug.scheduler import scheduler, update_group_schedules
from grug.settings import settings
from grug.utils import InterceptLogHandler

# Why the `members` intent is necessary for the Grug Discord bot:
#
# The `members` intent in a Discord bot is used to receive events and information about guild members. This includes
# receiving updates about members joining, leaving, or updating their presence or profile in the guilds (servers) the
# bot is part of. Specifically, for the Grug app, the `members` intent is necessary for several reasons:
#
# 1. **Initializing Guild Members**: When the bot starts and loads guilds, it initializes guild members by creating
# Discord accounts for them in the Grug database. This process requires access to the list of members in each guild.
# 2. **Attendance Tracking**: The bot tracks attendance for events. To do this effectively, it needs to know about all
# members in the guild, especially to send reminders or updates about events.
# 3. **Food Scheduling**: Similar to attendance tracking, food scheduling involves assigning and reminding members about
# their responsibilities. The bot needs to know who the members are to manage this feature.
# 4. **User Account Management**: The bot manages user accounts, including adding new users when they join the guild and
# updating user information. The `members` intent allows the bot to receive events related to these activities.
#
# Without the `members` intent, the bot would not be able to access detailed information about guild members, which
# would significantly limit its functionality related to user and event management.


_max_discord_message_length = 2000


class Client(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # copy the global commands over to your guild.
        if settings.environment != "prd":
            if settings.dev_guild_id:
                dev_guild = discord.Object(id=settings.dev_guild_id)
                self.tree.copy_global_to(guild=dev_guild)
                await self.tree.sync(guild=dev_guild)
            else:
                logger.warning("No dev guild set in settings. Cannot copy global commands.")
        else:
            await self.tree.sync()


client = Client()
discord.utils.setup_logging(handler=InterceptLogHandler())


# Command Error Handling
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # noinspection PyTypeChecker
    response: discord.InteractionResponse = interaction.response

    return await response.send_message(
        content=str(error),
        ephemeral=True,
    )


client.tree.on_error = on_tree_error


def get_bot_invite_url() -> str | None:
    return (
        f"https://discord.com/api/oauth2/authorize?client_id={client.user.id}&permissions=8&scope=bot"
        if client.user
        else None
    )


@client.event
async def on_ready():
    """
    Event handler for when the bot is ready.

    Documentation: https://discordpy.readthedocs.io/en/stable/api.html#discord.on_ready
    """

    # log the bot invite URL
    logger.info(f"Discord bot invite URL: {get_bot_invite_url()}")

    # Make sure all the guilds are loaded in the server
    logger.info("Loading guilds...")
    async with async_session() as session:
        for guild in client.guilds:
            logger.info(f"Initializing guild {guild.name} (ID: {guild.id})")
            group = await get_or_create_discord_server_group(guild=guild, db_session=session)

            # Create Discord accounts for all members in the guild
            for member in guild.members:
                if not member.bot and member.id not in [user.discord_member_id for user in group.users]:
                    logger.info(f"Initializing guild member {member.name} (ID: {member.id})")
                    await get_or_create_discord_user(discord_member=member, group=group, db_session=session)

    # Add persistent views to the discord bot
    client.add_view(view=DiscordAttendanceCheckView())
    client.add_view(view=DiscordFoodBringerSelectionView(group))

    logger.info(f"Logged in as {client.user} (ID: {client.user.id})")

    # wait for the scheduler to start and update the group schedules
    for second in range(10):
        if scheduler.state is RunState.started:
            break
        else:
            logger.info("Waiting for the scheduler to start...")
            await asyncio.sleep(1)
    if scheduler.state is not RunState.started:
        raise TimeoutError("Scheduler did not start in time.")
    await update_group_schedules()


@client.event
async def on_message(message: discord.Message):
    """on_message event handler for the Discord bot."""

    async with async_session() as session:
        # ignore messages from self and all bots
        if message.author == client.user or message.author.bot:
            return

        # If the assistant is not initialized, send a message and raise an error
        if not assistant:
            await message.channel.send("I'm sorry, I'm not able to respond right now. Please try again later.")
            raise ValueError("Assistant not initialized")

        # get the user and group
        group = (
            await get_or_create_discord_server_group(guild=message.guild, db_session=session) if message.guild else None
        )

        user = await get_or_create_discord_user(
            discord_member=message.author,
            group=group,
            db_session=session,
        )

        # respond to DMs
        if isinstance(message.channel, discord.DMChannel):
            async with message.channel.typing():
                # Send the message to the assistant and get the response
                assistant_response = await assistant.send_direct_message(
                    message=message.content,
                    user=user,
                    session=session,
                )

        # respond to @mentions in channels
        elif (
            isinstance(message.channel, discord.TextChannel) or isinstance(message.channel, discord.Thread)
        ) and client.user in message.mentions:
            async with message.channel.typing():
                # noinspection PyTypeChecker
                discord_text_channel = await get_or_create_discord_text_channel(
                    channel=message.channel,
                    session=session,
                )

                # Send the message to the assistant and get the response
                if discord_text_channel.assistant_thread_id:
                    assistant_response = await assistant.send_group_message(
                        message=message.content,
                        thread_id=discord_text_channel.assistant_thread_id,
                        user=user,
                        group=discord_text_channel.group,
                    )
                else:
                    assistant_response = await assistant.send_group_message(
                        message=message.content,
                        user=user,
                        group=discord_text_channel.group,
                    )

                    # Save the assistant thread ID to the database
                    discord_text_channel.assistant_thread_id = assistant_response.thread_id
                    session.add(discord_text_channel)
                    await session.commit()

        # if the message is not a DM or a mention, ignore it
        else:
            return

        # Send the response back to the user
        for output in [
            assistant_response.response[i : i + _max_discord_message_length]
            for i in range(0, len(assistant_response.response), _max_discord_message_length)
        ]:
            await message.channel.send(output, suppress_embeds=False)
        await message.channel.send(f"-# AI Tools Used: {assistant_response.tools_used}")


@client.tree.command()
@app_commands.checks.has_permissions(manage_guild=True)
async def update_game_session_schedule(interaction: discord.Interaction, cron: str):
    """
    Update the game session event schedule for the group.

    Args:
        interaction (discord.Interaction): The interaction object.
        cron (str): The cron schedule string. (hint: https://crontab.guru/#0_17_*_*_0)
    """
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)

        group.game_session_cron_schedule = cron
        session.add(group)
        await session.commit()

    await get_interaction_response(interaction).send_message(
        content=f"Updated event schedule to: {cron}",
        ephemeral=True,
    )


@client.tree.command()
@app_commands.checks.has_permissions(manage_guild=True)
async def trigger_game_session_reminder(interaction: discord.Interaction):
    """Trigger a game session reminder for the group."""
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)
        await game_session_reminder(group.id, session)

    await get_interaction_response(interaction).send_message(
        content="Game session reminder triggered",
        ephemeral=True,
    )


def get_interaction_response(interaction: discord.Interaction) -> discord.InteractionResponse:
    """
    Get the interaction response object from the interaction object.
    """
    # noinspection PyTypeChecker
    return interaction.response
