"""Dice rolling agent tools — let Grug roll dice for the party.

Registers tools that enable natural-language dice rolling, with results
stored in the database for GM audit and session recaps.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_dice_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register dice rolling tools on *agent*."""

    @agent.tool
    async def roll_dice(
        ctx: RunContext[GrugDeps],
        expression: str,
        roll_type: str = "general",
        private: bool = False,
        context_note: str | None = None,
    ) -> str:
        """Roll dice using standard notation and record the result.

        Use this whenever someone asks you to roll dice, make an attack roll,
        roll a saving throw, roll for damage, or roll initiative.

        Args:
            expression: Standard dice notation like "1d20+5", "2d6+3",
                "4d6kh3" (keep highest 3), "d100", "2d8+1d6+2".
            roll_type: What kind of roll this is.  One of: general, attack,
                damage, saving_throw, ability_check, initiative, death_save,
                skill_check.
            private: If True, only the roller and GM can see this roll.
                Use for secret GM rolls or private player checks.
            context_note: Optional description like "STR save vs Fireball DC 15"
                or "Greatsword attack".

        Returns:
            A formatted string with the dice expression, individual results,
            and total — plus natural 1/20 callouts for d20 rolls.
        """
        from grug.db.models import Character, DiceRoll
        from grug.db.session import get_session_factory
        from grug.dice import DiceError, RollType, format_roll, roll

        # Validate expression
        try:
            result = roll(expression)
        except DiceError as exc:
            return f"Grug no understand dice: {exc}"

        # Validate roll_type
        valid_types = {rt.value for rt in RollType}
        validated_type = roll_type if roll_type in valid_types else "general"

        # Serialise components for DB
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

        # Look up character name if we have an active character
        character_name = None
        factory = get_session_factory()
        async with factory() as session:
            if ctx.deps.active_character_id:
                from sqlalchemy import select

                char = (
                    await session.execute(
                        select(Character).where(
                            Character.id == ctx.deps.active_character_id
                        )
                    )
                ).scalar_one_or_none()
                if char:
                    character_name = char.name

            db_roll = DiceRoll(
                guild_id=ctx.deps.guild_id,
                campaign_id=ctx.deps.campaign_id,
                roller_discord_user_id=ctx.deps.user_id,
                roller_display_name=ctx.deps.username,
                character_name=character_name,
                expression=expression,
                individual_rolls=individual_rolls,
                total=result.grand_total,
                roll_type=validated_type,
                is_private=private,
                context_note=context_note,
            )
            session.add(db_roll)
            await session.commit()

        formatted = format_roll(result)

        # Build response
        parts = []
        if character_name:
            parts.append(f"🎲 **{character_name}** rolls: {formatted}")
        else:
            parts.append(f"🎲 {formatted}")

        if context_note:
            parts.append(f"*({context_note})*")

        if private:
            parts.append("*(private roll — only you and the GM can see this)*")

        return "\n".join(parts)

    @agent.tool
    async def roll_multiple(
        ctx: RunContext[GrugDeps],
        expression: str,
        count: int,
        roll_type: str = "general",
        context_note: str | None = None,
    ) -> str:
        """Roll the same dice expression multiple times and report all results.

        Use this for batch rolls like "roll 5 saving throws" or "roll initiative
        for all the goblins".

        Args:
            expression: Standard dice notation like "1d20+3".
            count: How many times to roll (1-20).
            roll_type: Purpose of the roll (general, saving_throw, initiative, etc.).
            context_note: Optional description like "DEX save DC 15 for goblins".

        Returns:
            A formatted list of all roll results with individual totals.
        """
        from grug.db.models import DiceRoll
        from grug.db.session import get_session_factory
        from grug.dice import DiceError, RollType, format_roll, roll

        if count < 1 or count > 20:
            return "Grug can roll between 1 and 20 times at once."

        try:
            results = [roll(expression) for _ in range(count)]
        except DiceError as exc:
            return f"Grug no understand dice: {exc}"

        valid_types = {rt.value for rt in RollType}
        validated_type = roll_type if roll_type in valid_types else "general"

        factory = get_session_factory()
        async with factory() as session:
            for result in results:
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

                db_roll = DiceRoll(
                    guild_id=ctx.deps.guild_id,
                    campaign_id=ctx.deps.campaign_id,
                    roller_discord_user_id=ctx.deps.user_id,
                    roller_display_name=ctx.deps.username,
                    expression=expression,
                    individual_rolls=individual_rolls,
                    total=result.grand_total,
                    roll_type=validated_type,
                    is_private=False,
                    context_note=context_note,
                )
                session.add(db_roll)
            await session.commit()

        # Format output
        lines = []
        if context_note:
            lines.append(f"🎲 **{context_note}**")
        else:
            lines.append(f"🎲 Rolling {expression} × {count}:")

        for i, result in enumerate(results, 1):
            formatted = format_roll(result, show_individual=True)
            lines.append(f"  {i}. {formatted}")

        return "\n".join(lines)
