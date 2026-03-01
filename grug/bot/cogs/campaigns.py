"""Campaign management cog — links Discord channels to TTRPG campaigns."""

import logging

import discord
from discord.ext import commands
from sqlalchemy import select

from grug.db.models import Campaign
from grug.db.session import get_session_factory

logger = logging.getLogger(__name__)

_KNOWN_SYSTEMS = {
    "dnd5e": "D&D 5e",
    "pf2e": "Pathfinder 2e",
    "unknown": "Unknown / Homebrew",
}


class CampaignsCog(commands.Cog, name="Campaigns"):
    """Manage campaign-to-channel associations."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="campaign", invoke_without_command=True)
    async def campaign_group(self, ctx: commands.Context) -> None:
        """Campaign management commands. Use !campaign <subcommand>."""
        await ctx.send_help(ctx.command)

    @campaign_group.command(name="create")
    @commands.has_permissions(manage_guild=True)
    async def create_campaign(self, ctx: commands.Context, *, name: str) -> None:
        """Link this channel to a new campaign.

        Usage: !campaign create <name>
        One channel can only host one campaign.
        """
        factory = get_session_factory()
        async with factory() as session:
            existing = await session.execute(
                select(Campaign).where(Campaign.channel_id == ctx.channel.id)
            )
            if existing.scalar_one_or_none() is not None:
                await ctx.send(
                    "This channel is already linked to a campaign. "
                    "Use `!campaign info` to see details, or use a different channel."
                )
                return

            campaign = Campaign(
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                name=name,
                system="unknown",
                is_active=True,
                created_by=ctx.author.id,
            )
            session.add(campaign)
            await session.commit()
            await session.refresh(campaign)
            campaign_id = campaign.id

        await ctx.send(
            f"⚔️ Campaign **{name}** created (ID: {campaign_id})!\n"
            "Documents uploaded here will be scoped to this campaign.\n"
            f"Set the game system: `!campaign set_system <system>`  "
            f"(options: {', '.join(_KNOWN_SYSTEMS.keys())})"
        )

    @campaign_group.command(name="info")
    async def campaign_info(self, ctx: commands.Context) -> None:
        """Show the campaign linked to this channel."""
        campaign = await _get_campaign_for_channel(ctx.channel.id)
        if campaign is None:
            await ctx.send(
                "No campaign is linked to this channel. "
                "An admin can create one with `!campaign create <name>`."
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

        system_label = _KNOWN_SYSTEMS.get(campaign.system, campaign.system)
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
        await ctx.send(embed=embed)

    @campaign_group.command(name="set_system")
    @commands.has_permissions(manage_guild=True)
    async def set_system(self, ctx: commands.Context, system: str) -> None:
        """Set the game system for this channel's campaign.

        Usage: !campaign set_system <system>
        Systems: dnd5e, pf2e, unknown
        """
        system = system.lower().strip()
        campaign = await _get_campaign_for_channel(ctx.channel.id)
        if campaign is None:
            await ctx.send(
                "No campaign linked to this channel. Create one with `!campaign create`."
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
        label = _KNOWN_SYSTEMS.get(system, system)
        await ctx.send(f"🎲 Campaign system updated to **{label}**.")

    @campaign_group.command(name="list")
    async def list_campaigns(self, ctx: commands.Context) -> None:
        """List all campaigns in this server."""
        factory = get_session_factory()
        async with factory() as session:
            campaigns = (
                (
                    await session.execute(
                        select(Campaign).where(Campaign.guild_id == ctx.guild.id)
                    )
                )
                .scalars()
                .all()
            )
        if not campaigns:
            await ctx.send("No campaigns yet. Use `!campaign create` in any channel.")
            return
        embed = discord.Embed(title="⚔️ Campaigns", color=discord.Color.gold())
        for c in campaigns:
            system_label = _KNOWN_SYSTEMS.get(c.system, c.system)
            value = f"System: {system_label}\nChannel: <#{c.channel_id}>"
            if not c.is_active:
                value += "\n*(inactive)*"
            embed.add_field(name=c.name, value=value, inline=False)
        await ctx.send(embed=embed)


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
