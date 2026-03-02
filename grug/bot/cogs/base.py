"""Base cog class providing shared error handling for all Grug cogs."""

import discord
from discord import app_commands
from discord.ext import commands


class GrugCogBase(commands.Cog):
    """Base class for Grug cogs — provides a shared error handler."""

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You not have permission for that!", ephemeral=True
            )
        else:
            raise error
