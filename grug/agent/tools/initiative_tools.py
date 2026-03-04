"""Initiative / encounter agent tools — let Grug manage combat encounters.

Registers tools that enable natural-language initiative tracking: creating
encounters, adding combatants, rolling initiative, advancing turns, and
ending encounters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_initiative_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register initiative / encounter tools on *agent*."""

    @agent.tool
    async def start_encounter(
        ctx: RunContext[GrugDeps],
        name: str,
    ) -> str:
        """Create a new initiative encounter for this campaign.

        Ends any existing active encounter first.  The encounter starts in
        "preparing" status — use roll_initiative and advance_turn to run it.

        Args:
            name: A short name for the encounter, e.g. "Goblin Ambush",
                "Boss Fight", "Bar Brawl".

        Returns:
            Confirmation with the encounter name and status.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import create_encounter

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            await create_encounter(
                session,
                campaign_id=ctx.deps.campaign_id,
                guild_id=ctx.deps.guild_id,
                name=name,
                created_by=ctx.deps.user_id,
                channel_id=ctx.deps.channel_id,
            )
            await session.commit()

        return f"Encounter '{name}' created! Status: preparing. Add combatants then roll initiative!"

    @agent.tool
    async def add_combatant(
        ctx: RunContext[GrugDeps],
        name: str,
        initiative_modifier: int = 0,
        is_enemy: bool = False,
    ) -> str:
        """Add a combatant to the current active encounter.

        Use this to add PCs, NPCs, or enemies to the initiative tracker.

        Args:
            name: The combatant's name (e.g. "Gronk", "Goblin 1", "Dragon").
            initiative_modifier: The modifier added to the d20 initiative roll
                (e.g. +3 for DEX 16).  Default 0.
            is_enemy: True if this is an enemy/monster, False for PCs/allies.

        Returns:
            Confirmation that the combatant was added.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            add_combatant as _add_combatant,
            get_active_encounter,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter! Start one first with start_encounter."

            try:
                await _add_combatant(
                    session,
                    encounter_id=enc.id,
                    name=name,
                    initiative_modifier=initiative_modifier,
                    is_enemy=is_enemy,
                )
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

        enemy_tag = " (enemy)" if is_enemy else ""
        mod_str = f" (mod {initiative_modifier:+d})" if initiative_modifier else ""
        return f"{name}{enemy_tag}{mod_str} added to encounter!"

    @agent.tool
    async def roll_initiative(ctx: RunContext[GrugDeps]) -> str:
        """Roll initiative for all combatants and start the encounter.

        Rolls 1d20 + modifier for each combatant that hasn't rolled yet,
        sorts the initiative order, and transitions the encounter to active status.

        Returns:
            The full initiative order with roll results.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            format_initiative_order,
            get_active_encounter,
            start_encounter as _start_encounter,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter! Start one first."

            try:
                enc = await _start_encounter(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            # Reload to get fresh combatant data
            from grug.encounter import get_encounter_by_id

            enc = await get_encounter_by_id(session, enc.id)
            return format_initiative_order(enc)

    @agent.tool
    async def advance_turn(ctx: RunContext[GrugDeps]) -> str:
        """Advance to the next combatant's turn in the active encounter.

        Returns:
            Who is up next along with the current round number.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            advance_turn as _advance_turn,
            format_initiative_order,
            get_active_encounter,
            get_encounter_by_id,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            try:
                enc, next_combatant = await _advance_turn(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            enc = await get_encounter_by_id(session, enc.id)
            order = format_initiative_order(enc)

        return f"{next_combatant.name} up next!\n\n{order}"

    @agent.tool
    async def end_encounter(ctx: RunContext[GrugDeps]) -> str:
        """End the current active encounter.

        Returns:
            Confirmation that the encounter has ended.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            end_encounter as _end_encounter,
            get_active_encounter,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter to end!"

            try:
                enc = await _end_encounter(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

        return f"Encounter '{enc.name}' ended! Battle over!"

    @agent.tool
    async def get_initiative_order(ctx: RunContext[GrugDeps]) -> str:
        """Show the current initiative order for the active encounter.

        Returns:
            A formatted list of all combatants in initiative order with
            the current turn highlighted.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import format_initiative_order, get_active_encounter

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter right now!"

            return format_initiative_order(enc)
