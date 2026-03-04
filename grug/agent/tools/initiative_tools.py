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

    # ── Combat tools (standard+ depth) ──────────────────────────────

    @agent.tool
    async def deal_damage(
        ctx: RunContext[GrugDeps],
        targets: str,
        amount: int,
        damage_type: str = "",
        source: str = "",
    ) -> str:
        """Deal damage to one or more combatants in the active encounter.

        Damage is absorbed by temp HP first, then reduces current HP.

        Args:
            targets: Comma-separated combatant names, e.g. "Goblin 1, Goblin 2".
            amount: How much damage to deal (positive integer).
            damage_type: Optional damage type, e.g. "fire", "slashing".
            source: Optional source of damage, e.g. "Fireball".

        Returns:
            Summary of damage dealt and remaining HP for each target.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            deal_damage as _deal_damage,
            format_damage_results,
            get_active_encounter,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            # Resolve names to IDs
            target_names = [t.strip().lower() for t in targets.split(",")]
            ids = [
                c.id
                for c in enc.combatants
                if c.name.lower() in target_names and c.is_active
            ]
            if not ids:
                return f"Grug not find any combatants named: {targets}"

            try:
                results = await _deal_damage(
                    session,
                    enc.id,
                    ids,
                    amount,
                    damage_type=damage_type or None,
                    source=source or None,
                )
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            return format_damage_results(results, amount, damage_type or None)

    @agent.tool
    async def heal(
        ctx: RunContext[GrugDeps],
        targets: str,
        amount: int,
        source: str = "",
    ) -> str:
        """Heal one or more combatants in the active encounter.

        Cannot exceed max HP. Resets death saves if healed from 0 HP.

        Args:
            targets: Comma-separated combatant names, e.g. "Gronk, Elara".
            amount: How much to heal (positive integer).
            source: Optional source, e.g. "Cure Wounds".

        Returns:
            Summary of healing and current HP for each target.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            format_heal_results,
            get_active_encounter,
            heal_combatant,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            target_names = [t.strip().lower() for t in targets.split(",")]
            ids = [
                c.id
                for c in enc.combatants
                if c.name.lower() in target_names and c.is_active
            ]
            if not ids:
                return f"Grug not find any combatants named: {targets}"

            try:
                results = await heal_combatant(
                    session,
                    enc.id,
                    ids,
                    amount,
                    source=source or None,
                )
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            return format_heal_results(results, amount)

    @agent.tool
    async def roll_saving_throws(
        ctx: RunContext[GrugDeps],
        targets: str,
        ability: str,
        dc: int,
    ) -> str:
        """Roll saving throws for one or more combatants.

        Args:
            targets: Comma-separated combatant names.
            ability: Ability abbreviation: STR, DEX, CON, INT, WIS, or CHA.
            dc: Difficulty class to beat.

        Returns:
            A formatted table of each combatant's roll, modifier, total,
            and pass/fail result.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            format_save_results,
            get_active_encounter,
            roll_saving_throws as _roll_saves,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            target_names = [t.strip().lower() for t in targets.split(",")]
            ids = [
                c.id
                for c in enc.combatants
                if c.name.lower() in target_names and c.is_active
            ]
            if not ids:
                return f"Grug not find any combatants named: {targets}"

            try:
                results = await _roll_saves(session, enc.id, ids, ability, dc)
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            return format_save_results(results, ability, dc)

    @agent.tool
    async def apply_condition(
        ctx: RunContext[GrugDeps],
        target: str,
        condition: str,
        remove: bool = False,
    ) -> str:
        """Add or remove a condition on a combatant.

        Args:
            target: The combatant's name.
            condition: Condition name, e.g. "Prone", "Frightened", "Stunned".
            remove: If True, remove the condition instead of adding it.

        Returns:
            Confirmation of the condition change.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            add_condition as _add_cond,
            get_active_encounter,
            remove_condition as _remove_cond,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            target_lower = target.strip().lower()
            match = [
                c
                for c in enc.combatants
                if c.name.lower() == target_lower and c.is_active
            ]
            if not match:
                return f"Grug not find combatant named: {target}"

            try:
                if remove:
                    await _remove_cond(session, enc.id, [match[0].id], condition)
                    await session.commit()
                    return f"Removed '{condition}' from {match[0].name}."
                else:
                    await _add_cond(session, enc.id, [match[0].id], condition)
                    await session.commit()
                    return f"Added '{condition}' to {match[0].name}."
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

    @agent.tool
    async def death_save(
        ctx: RunContext[GrugDeps],
        target: str,
    ) -> str:
        """Roll a death saving throw for a combatant at 0 HP.

        Natural 20 = revive with 1 HP. Natural 1 = two failures. 3 successes
        = stabilized. 3 failures = dead.

        Args:
            target: The combatant's name.

        Returns:
            The death save result and current save tally.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            get_active_encounter,
            roll_death_save as _roll_ds,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            target_lower = target.strip().lower()
            match = [
                c
                for c in enc.combatants
                if c.name.lower() == target_lower and c.is_active
            ]
            if not match:
                return f"Grug not find combatant named: {target}"

            try:
                combatant, roll, success, status = await _roll_ds(
                    session, enc.id, match[0].id
                )
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            status_msgs = {
                "success": f"✅ Success! ({combatant.death_save_successes}/3 successes, {combatant.death_save_failures}/3 failures)",
                "failure": f"❌ Failure! ({combatant.death_save_successes}/3 successes, {combatant.death_save_failures}/3 failures)",
                "stabilized": "🛡️ Stabilized! Three successes!",
                "dead": "💀 Dead. Three failures.",
                "nat20_revive": "🌟 Natural 20! Revived with 1 HP!",
                "nat1_double_fail": f"💀 Natural 1! Two failures! ({combatant.death_save_successes}/3 successes, {combatant.death_save_failures}/3 failures)",
            }

            msg = status_msgs.get(status, status)
            return f"🎲 {combatant.name} death save: {roll}\n{msg}"

    @agent.tool
    async def set_concentration(
        ctx: RunContext[GrugDeps],
        target: str,
        spell: str = "",
    ) -> str:
        """Set or clear concentration for a combatant.

        Args:
            target: The combatant's name.
            spell: Spell name to concentrate on, or empty string to clear.

        Returns:
            Confirmation of concentration change.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            get_active_encounter,
            set_concentration as _set_conc,
        )

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        factory = get_session_factory()
        async with factory() as session:
            enc = await get_active_encounter(session, ctx.deps.campaign_id)
            if enc is None:
                return "No active encounter!"

            target_lower = target.strip().lower()
            match = [
                c
                for c in enc.combatants
                if c.name.lower() == target_lower and c.is_active
            ]
            if not match:
                return f"Grug not find combatant named: {target}"

            try:
                spell_name = spell.strip() if spell else None
                await _set_conc(session, enc.id, match[0].id, spell_name)
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

            if spell:
                return f"🔮 {match[0].name} concentrating on {spell}."
            else:
                return f"{match[0].name} concentration cleared."

    @agent.tool
    async def add_monster(
        ctx: RunContext[GrugDeps],
        monster_name: str,
        display_name: str = "",
        system: str = "",
    ) -> str:
        """Search for a monster by name and add it to the encounter with full stats.

        Looks up the monster in built-in rule sources (D&D 5e SRD or PF2e Archives
        of Nethys) and adds it with HP, AC, initiative modifier, and save modifiers
        auto-populated.

        Args:
            monster_name: The monster to search for (e.g. "Goblin", "Adult Red Dragon",
                "Kobold Warrior").
            display_name: Optional custom display name for the combatant
                (e.g. "Goblin 1").  If empty, uses the monster's official name.
            system: Filter to "dnd5e" or "pf2e".  Leave empty to search all sources.

        Returns:
            Confirmation with the monster's stats, or an error if not found.
        """
        from grug.db.session import get_session_factory
        from grug.encounter import (
            EncounterError,
            add_combatant as _add_combatant,
            get_active_encounter,
        )
        from grug.monster_search import search_monsters

        if ctx.deps.campaign_id is None:
            return "Grug not know which campaign this for. Need campaign channel!"

        # Search for the monster
        sys_filter = system.strip().lower() if system else None
        results = await search_monsters(monster_name, system=sys_filter, limit=3)
        if not results:
            return f"Grug not find any monster matching '{monster_name}'. Try a different name?"

        monster = results[0]  # Best match
        name = display_name.strip() or monster.name

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
                    initiative_modifier=monster.initiative_modifier or 0,
                    is_enemy=True,
                    max_hp=monster.hp,
                    armor_class=monster.ac,
                    save_modifiers=monster.save_modifiers,
                )
                await session.commit()
            except EncounterError as exc:
                return f"Grug have problem: {exc}"

        stats = []
        if monster.hp is not None:
            stats.append(f"HP {monster.hp}")
        if monster.ac is not None:
            stats.append(f"AC {monster.ac}")
        if monster.initiative_modifier is not None:
            mod = monster.initiative_modifier
            stats.append(f"Init {mod:+d}")
        if monster.cr:
            stats.append(f"CR {monster.cr}")
        stats_str = " · ".join(stats) if stats else "no stats found"

        return f"👹 {name} ({monster.name} from {monster.source}) added! [{stats_str}]"
