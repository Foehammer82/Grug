"""Campaign management cog — links Discord channels to TTRPG campaigns."""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.db.models import Campaign
from grug.db.session import get_session_factory
from grug.utils import GAME_SYSTEM_LABELS

logger = logging.getLogger(__name__)


class CampaignsCog(commands.Cog, name="Campaigns"):
    """Manage campaign-to-channel associations."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    campaign = app_commands.Group(
        name="campaign",
        description="Manage campaign-to-channel associations.",
        guild_only=True,
    )

    @campaign.command(name="create", description="Link this channel to a new campaign.")
    @app_commands.describe(name="The name of the new campaign.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_campaign(
        self, interaction: discord.Interaction, name: str
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            existing = await session.execute(
                select(Campaign).where(Campaign.channel_id == interaction.channel_id)
            )
            if existing.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    "This channel is already linked to a campaign. "
                    "Use `/campaign info` to see details, or use a different channel.",
                    ephemeral=True,
                )
                return

            campaign = Campaign(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                name=name,
                system="unknown",
                is_active=True,
                created_by=interaction.user.id,
            )
            session.add(campaign)
            await session.commit()
            await session.refresh(campaign)
            campaign_id = campaign.id

        await interaction.response.send_message(
            f"⚔️ Campaign **{name}** created (ID: {campaign_id})!\n"
            "Documents uploaded here will be scoped to this campaign.\n"
            f"Set the game system with `/campaign set_system`  "
            f"(options: {', '.join(GAME_SYSTEM_LABELS.keys())})"
        )

    @campaign.command(
        name="info", description="Show the campaign linked to this channel."
    )
    async def campaign_info(self, interaction: discord.Interaction) -> None:
        campaign = await _get_campaign_for_channel(interaction.channel_id)
        if campaign is None:
            await interaction.response.send_message(
                "No campaign is linked to this channel. "
                "An admin can create one with `/campaign create`."
            )
            return

        from grug.db.models import Character, Document

        factory = get_session_factory()
        async with factory() as session:
            char_rows = (
                (
                    await session.execute(
                        select(Character).where(Character.campaign_id == campaign.id)
                    )
                )
                .scalars()
                .all()
            )
            doc_rows = (
                (
                    await session.execute(
                        select(Document).where(Document.campaign_id == campaign.id)
                    )
                )
                .scalars()
                .all()
            )

        system_label = GAME_SYSTEM_LABELS.get(campaign.system, campaign.system)
        embed = discord.Embed(title=f"⚔️ {campaign.name}", color=discord.Color.gold())
        embed.add_field(name="System", value=system_label, inline=True)
        embed.add_field(
            name="Status",
            value="Active ✅" if campaign.is_active else "Inactive ⏸️",
            inline=True,
        )
        embed.add_field(name="ID", value=str(campaign.id), inline=True)
        embed.add_field(name="Characters", value=str(len(char_rows)), inline=True)
        embed.add_field(name="Documents", value=str(len(doc_rows)), inline=True)
        embed.add_field(name="Channel", value=f"<#{campaign.channel_id}>", inline=True)
        await interaction.response.send_message(embed=embed)

    @campaign.command(
        name="set_system",
        description="Set the game system for this channel's campaign.",
    )
    @app_commands.describe(system="The game system (e.g. dnd5e, pf2e, unknown).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_system(self, interaction: discord.Interaction, system: str) -> None:
        system = system.lower().strip()
        campaign = await _get_campaign_for_channel(interaction.channel_id)
        if campaign is None:
            await interaction.response.send_message(
                "No campaign linked to this channel. Create one with `/campaign create`.",
                ephemeral=True,
            )
            return
        factory = get_session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    select(Campaign).where(Campaign.id == campaign.id)
                )
            ).scalar_one()
            row.system = system
            await session.commit()
        label = GAME_SYSTEM_LABELS.get(system, system)
        await interaction.response.send_message(
            f"🎲 Campaign system updated to **{label}**."
        )

    @campaign.command(name="list", description="List all campaigns in this server.")
    async def list_campaigns(self, interaction: discord.Interaction) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaigns = (
                (
                    await session.execute(
                        select(Campaign).where(
                            Campaign.guild_id == interaction.guild_id
                        )
                    )
                )
                .scalars()
                .all()
            )
        if not campaigns:
            await interaction.response.send_message(
                "No campaigns yet. Use `/campaign create` in any channel."
            )
            return
        embed = discord.Embed(title="⚔️ Campaigns", color=discord.Color.gold())
        for c in campaigns:
            system_label = GAME_SYSTEM_LABELS.get(c.system, c.system)
            value = f"System: {system_label}\nChannel: <#{c.channel_id}>"
            if not c.is_active:
                value += "\n*(inactive)*"
            embed.add_field(name=c.name, value=value, inline=False)
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use that command.",
                ephemeral=True,
            )
        else:
            raise error


async def _get_campaign_for_channel(channel_id: int) -> Campaign | None:
    """Return the Campaign linked to a channel, or None."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.channel_id == channel_id)
        )
        return result.scalar_one_or_none()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CampaignsCog(bot))
