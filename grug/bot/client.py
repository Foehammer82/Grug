"""Discord client setup for Grug."""

import logging

import discord
from discord.ext import commands

from grug.config.settings import get_settings

logger = logging.getLogger(__name__)

_bot: commands.Bot | None = None


def create_bot() -> commands.Bot:
    """Create and configure the Discord bot instance."""
    settings = get_settings()
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(
        command_prefix=settings.discord_prefix,
        intents=intents,
        help_command=commands.DefaultHelpCommand(),
        description="Grug — your friendly TTRPG AI companion!",
    )
    return bot


def get_bot() -> commands.Bot | None:
    """Return the running bot instance."""
    return _bot


def set_bot(bot: commands.Bot) -> None:
    """Store the global bot reference."""
    global _bot
    _bot = bot
