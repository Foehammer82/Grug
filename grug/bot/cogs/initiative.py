"""Initiative tracker cog — /initiative command group for Discord encounter management."""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.bot.cogs.base import GrugCogBase
from grug.db.models import Campaign, Character, Encounter
from grug.db.session import get_session_factory
from grug.encounter import (
    EncounterError,
    add_combatant,
    advance_turn,
    create_encounter,
    end_encounter,
    get_active_encounter,
    get_encounter_by_id,
    sorted_combatants,
    start_encounter,
)

logger = logging.getLogger(__name__)


def _initiative_embed(enc: Encounter) -> discord.Embed:
    """Build a rich embed showing the current initiative order."""
    order = sorted_combatants(enc)
    status_color = {
        "preparing": 0xFFA500,  # orange
        "active": 0x58A6FF,  # blue
        "ended": 0x666666,  # grey
    }

    embed = discord.Embed(
        title=f"⚔️ {enc.name}",
        color=status_color.get(enc.status, 0x58A6FF),
    )

    if not order:
        embed.description = (
            "No combatants yet. Use `/initiative add` to add combatants."
        )
        embed.set_footer(text=f"Status: {enc.status}")
        return embed

    lines: list[str] = []
    for idx, c in enumerate(order):
        marker = (
            "▶ " if idx == enc.current_turn_index and enc.status == "active" else "   "
        )
        roll_str = str(c.initiative_roll) if c.initiative_roll is not None else "—"
        enemy_tag = " 👹" if c.is_enemy else ""
        line = f"{marker}`{roll_str:>3}`  {c.name}{enemy_tag}"
        if idx == enc.current_turn_index and enc.status == "active":
            line = f"**{line}**"
        lines.append(line)

    embed.description = "\n".join(lines)
    embed.set_footer(
        text=f"Round {enc.round_number} · {enc.status.capitalize()} · {len(order)} combatants"
    )
    return embed


class InitiativeCog(GrugCogBase, name="Initiative"):
    """Track initiative and encounters in your campaign."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    initiative = app_commands.Group(
        name="initiative",
        description="Initiative tracker commands",
        guild_only=True,
    )

    # ── /initiative start ────────────────────────────────────────────

    @initiative.command(name="start", description="Start a new encounter")
    @app_commands.describe(name="Name for the encounter, e.g. 'Goblin Ambush'")
    async def initiative_start(
        self,
        interaction: discord.Interaction,
        name: str,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await create_encounter(
                session,
                campaign_id=campaign.id,
                guild_id=interaction.guild_id,
                name=name,
                created_by=interaction.user.id,
                channel_id=interaction.channel_id,
            )
            await session.commit()
            await session.refresh(enc, attribute_names=["combatants"])

            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative add ──────────────────────────────────────────────

    @initiative.command(name="add", description="Add a combatant to the encounter")
    @app_commands.describe(
        name="Combatant name",
        modifier="Initiative modifier (e.g. 3 for +3 DEX)",
        enemy="Is this an enemy/monster?",
    )
    async def initiative_add(
        self,
        interaction: discord.Interaction,
        name: str,
        modifier: int = 0,
        enemy: bool = False,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "⚠️ No active encounter. Start one with `/initiative start`.",
                    ephemeral=True,
                )
                return

            # Check if this user has a character in the campaign (for PC auto-linking)
            character_id = None
            if not enemy:
                char = (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == campaign.id,
                            Character.owner_discord_user_id == interaction.user.id,
                        )
                    )
                ).scalar_one_or_none()
                if char and char.name.lower() == name.lower():
                    character_id = char.id
                    # Pull initiative modifier from character sheet if available
                    if modifier == 0 and char.structured_data:
                        sheet_init = char.structured_data.get("initiative")
                        if isinstance(sheet_init, (int, float)):
                            modifier = int(sheet_init)

            await add_combatant(
                session,
                encounter_id=enc.id,
                name=name,
                initiative_modifier=modifier,
                is_enemy=enemy,
                character_id=character_id,
            )
            await session.commit()

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative roll ─────────────────────────────────────────────

    @initiative.command(
        name="roll",
        description="Roll initiative for all combatants and start the encounter",
    )
    async def initiative_roll(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "⚠️ No active encounter.", ephemeral=True
                )
                return

            try:
                enc = await start_encounter(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative next ─────────────────────────────────────────────

    @initiative.command(name="next", description="Advance to the next combatant's turn")
    async def initiative_next(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "⚠️ No active encounter.", ephemeral=True
                )
                return

            try:
                enc, next_combatant = await advance_turn(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            embed.add_field(
                name="Up Next",
                value=f"**{next_combatant.name}** — it's your turn!",
                inline=False,
            )
            await interaction.response.send_message(embed=embed)

    # ── /initiative show ─────────────────────────────────────────────

    @initiative.command(name="show", description="Show the current initiative order")
    async def initiative_show(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "No active encounter in this campaign.", ephemeral=True
                )
                return

            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative end ──────────────────────────────────────────────

    @initiative.command(name="end", description="End the current encounter")
    async def initiative_end(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "No active encounter to end.", ephemeral=True
                )
                return

            try:
                enc = await end_encounter(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"⚔️ {enc.name} — Ended",
                description="The encounter has ended. Good fight!",
                color=0x666666,
            )
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InitiativeCog(bot))
