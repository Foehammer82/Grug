"""Dice rolling cog — /roll slash command for Discord dice rolling."""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.bot.cogs.base import GrugCogBase
from grug.db.models import Campaign, Character, DiceRoll
from grug.db.session import get_session_factory
from grug.dice import DiceError, format_roll, roll

logger = logging.getLogger(__name__)

# Choices for the roll_type parameter
_ROLL_TYPE_CHOICES = [
    app_commands.Choice(name="General", value="general"),
    app_commands.Choice(name="Attack", value="attack"),
    app_commands.Choice(name="Damage", value="damage"),
    app_commands.Choice(name="Saving Throw", value="saving_throw"),
    app_commands.Choice(name="Ability Check", value="ability_check"),
    app_commands.Choice(name="Initiative", value="initiative"),
    app_commands.Choice(name="Death Save", value="death_save"),
    app_commands.Choice(name="Skill Check", value="skill_check"),
]


class DiceCog(GrugCogBase, name="Dice"):
    """Roll dice with fair cryptographic randomness."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="roll", description="Roll dice using standard notation.")
    @app_commands.describe(
        expression="Dice expression, e.g. 1d20+5, 2d6+3, 4d6kh3",
        roll_type="What kind of roll this is",
        private="Only you and the GM can see this roll",
        note="Optional context, e.g. 'STR save vs Fireball DC 15'",
    )
    @app_commands.choices(roll_type=_ROLL_TYPE_CHOICES)
    @app_commands.guild_only()
    async def roll_command(
        self,
        interaction: discord.Interaction,
        expression: str,
        roll_type: app_commands.Choice[str] | None = None,
        private: bool = False,
        note: str | None = None,
    ) -> None:
        # Parse and roll
        try:
            result = roll(expression)
        except DiceError as exc:
            await interaction.response.send_message(
                f"⚠️ Grug no understand: {exc}", ephemeral=True
            )
            return

        rtype = roll_type.value if roll_type else "general"

        # Serialise for DB
        individual_rolls = []
        for sign, comp in result.components:
            if hasattr(comp, "sides"):
                individual_rolls.append(
                    {
                        "expression": comp.expression,
                        "sides": comp.sides,
                        "rolls": comp.rolls,
                        "kept": comp.kept,
                        "total": comp.total,
                        "sign": sign,
                    }
                )
            else:
                individual_rolls.append({"constant": comp, "sign": sign})

        # Look up campaign for this channel and character name
        character_name = None
        campaign_id = None
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
            if campaign:
                campaign_id = campaign.id

                # Try to find the user's character in this campaign
                char = (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == campaign.id,
                            Character.owner_discord_user_id == interaction.user.id,
                        )
                    )
                ).scalar_one_or_none()
                if char:
                    character_name = char.name

            db_roll = DiceRoll(
                guild_id=interaction.guild_id,
                campaign_id=campaign_id,
                roller_discord_user_id=interaction.user.id,
                roller_display_name=interaction.user.display_name,
                character_name=character_name,
                expression=expression,
                individual_rolls=individual_rolls,
                total=result.grand_total,
                roll_type=rtype,
                is_private=private,
                context_note=note,
            )
            session.add(db_roll)
            await session.commit()

        # Build embed
        formatted = format_roll(result)
        embed = discord.Embed(
            description=formatted,
            color=_roll_color(result),
        )

        # Header
        roller_name = character_name or interaction.user.display_name
        type_label = roll_type.name if roll_type else "Roll"
        embed.set_author(
            name=f"🎲 {roller_name} — {type_label}",
            icon_url=interaction.user.display_avatar.url,
        )

        if note:
            embed.set_footer(text=note)

        # Send
        if private:
            embed.set_footer(
                text=f"{'🔒 Private roll' + (' · ' + note if note else '')}"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)


def _roll_color(result) -> int:
    """Pick an embed colour based on the roll result."""
    if result.is_nat_20:
        return 0x00FF00  # Green — critical success
    elif result.is_nat_1:
        return 0xFF0000  # Red — critical fail
    return 0x58A6FF  # Accent blue — normal roll


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DiceCog(bot))
