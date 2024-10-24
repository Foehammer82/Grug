"""Discord bot interface for the Grug assistant server."""

import discord
import discord.utils
from discord import app_commands
from loguru import logger

from grug.ai import assistant
from grug.db import async_session
from grug.discord_views.attendance import DiscordAttendanceCheckView
from grug.discord_views.food import DiscordFoodBringerSelectionView
from grug.models_crud import get_or_create_discord_server_group, get_or_create_discord_user
from grug.utils import InterceptLogHandler, get_interaction_response

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


class Client(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


discord_client = Client()
discord.utils.setup_logging(handler=InterceptLogHandler())


# Command Error Handling
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    return await get_interaction_response(interaction).send_message(
        content=str(error),
        ephemeral=True,
    )


discord_client.tree.on_error = on_tree_error


def get_bot_invite_url() -> str | None:
    return (
        f"https://discord.com/api/oauth2/authorize?client_id={discord_client.user.id}&permissions=8&scope=bot"
        if discord_client.user
        else None
    )


@discord_client.event
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
        for guild in discord_client.guilds:
            logger.info(f"Initializing guild {guild.name} (ID: {guild.id})")
            group = await get_or_create_discord_server_group(guild=guild, db_session=session)

            # Create Discord accounts for all members in the guild
            for member in guild.members:
                if not member.bot and member.id not in [user.discord_member_id for user in group.users]:
                    logger.info(f"Initializing guild member {member.name} (ID: {member.id})")
                    await get_or_create_discord_user(discord_member=member, group=group, db_session=session)

    # Add persistent views to the discord bot
    discord_client.add_view(view=DiscordAttendanceCheckView())
    discord_client.add_view(view=DiscordFoodBringerSelectionView(group))

    logger.info(f"Logged in as {discord_client.user} (ID: {discord_client.user.id})")


@discord_client.event
async def on_message(message: discord.Message):
    """on_message event handler for the Discord bot."""

    # ignore messages from self and all bots
    if message.author == discord_client.user or message.author.bot:
        return

    # If the assistant is not initialized, send a message and raise an error
    if not assistant:
        await message.channel.send("I'm sorry, I'm not able to respond right now. Please try again later.")
        raise ValueError("Assistant not initialized")

    await assistant.respond_to_discord_message(message, discord_client)
