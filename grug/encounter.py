"""Encounter / initiative tracker service — shared logic for API and agent tools.

Every mutation goes through these functions so both the web dashboard
and the Discord agent get identical behaviour.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from grug.db.models import CombatLogEntry, Combatant, Encounter

logger = logging.getLogger(__name__)

# ── Status constants ─────────────────────────────────────────────────
STATUS_PREPARING = "preparing"
STATUS_ACTIVE = "active"
STATUS_ENDED = "ended"


class EncounterError(Exception):
    """Domain-level error for encounter operations."""


# ── Helpers ──────────────────────────────────────────────────────────


async def get_active_encounter(
    db: AsyncSession,
    campaign_id: int,
) -> Encounter | None:
    """Return the single active/preparing encounter for *campaign_id*, or None."""
    result = await db.execute(
        select(Encounter)
        .options(selectinload(Encounter.combatants))
        .where(
            Encounter.campaign_id == campaign_id,
            Encounter.status.in_([STATUS_PREPARING, STATUS_ACTIVE]),
        )
        .order_by(Encounter.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_encounter_by_id(
    db: AsyncSession,
    encounter_id: int,
    *,
    load_combatants: bool = True,
) -> Encounter | None:
    """Fetch an encounter by PK, optionally eager-loading combatants."""
    stmt = select(Encounter).where(Encounter.id == encounter_id)
    if load_combatants:
        stmt = stmt.options(selectinload(Encounter.combatants))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def sorted_combatants(encounter: Encounter) -> list[Combatant]:
    """Return active combatants sorted by initiative (desc), then sort_order."""
    active = [c for c in encounter.combatants if c.is_active]
    return sorted(
        active,
        key=lambda c: (
            c.initiative_roll if c.initiative_roll is not None else -999,
            -c.sort_order,
        ),
        reverse=True,
    )


# ── Create ───────────────────────────────────────────────────────────


async def create_encounter(
    db: AsyncSession,
    *,
    campaign_id: int,
    guild_id: int,
    name: str,
    created_by: int,
    channel_id: int | None = None,
) -> Encounter:
    """Create a new encounter, ending any existing active one first."""
    existing = await get_active_encounter(db, campaign_id)
    if existing is not None:
        existing.status = STATUS_ENDED
        existing.ended_at = datetime.now(timezone.utc)

    enc = Encounter(
        campaign_id=campaign_id,
        guild_id=guild_id,
        name=name,
        status=STATUS_PREPARING,
        created_by=created_by,
        channel_id=channel_id,
    )
    db.add(enc)
    await db.flush()
    return enc


# ── Combatants ───────────────────────────────────────────────────────


async def add_combatant(
    db: AsyncSession,
    *,
    encounter_id: int,
    name: str,
    initiative_modifier: int = 0,
    is_enemy: bool = False,
    is_hidden: bool = False,
    character_id: int | None = None,
    max_hp: int | None = None,
    armor_class: int | None = None,
    save_modifiers: dict[str, int] | None = None,
) -> Combatant:
    """Add a combatant to an encounter."""
    current_hp = max_hp  # start at full HP
    combatant = Combatant(
        encounter_id=encounter_id,
        name=name,
        initiative_modifier=initiative_modifier,
        is_enemy=is_enemy,
        is_hidden=is_hidden,
        character_id=character_id,
        max_hp=max_hp,
        current_hp=current_hp,
        armor_class=armor_class,
        save_modifiers=save_modifiers,
    )
    db.add(combatant)
    await db.flush()
    return combatant


async def remove_combatant(
    db: AsyncSession,
    encounter_id: int,
    combatant_id: int,
) -> None:
    """Mark a combatant as inactive (soft-remove from initiative)."""
    result = await db.execute(
        select(Combatant).where(
            Combatant.id == combatant_id,
            Combatant.encounter_id == encounter_id,
        )
    )
    combatant = result.scalar_one_or_none()
    if combatant is None:
        raise EncounterError("Combatant not found")
    combatant.is_active = False
    await db.flush()


# ── Initiative rolling ───────────────────────────────────────────────


def _roll_d20() -> int:
    """Cryptographically fair 1d20."""
    return secrets.randbelow(20) + 1


async def roll_all_initiative(
    db: AsyncSession,
    encounter_id: int,
) -> list[Combatant]:
    """Roll initiative for all active combatants that don't yet have a roll."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    for c in encounter.combatants:
        if c.is_active and c.initiative_roll is None:
            c.initiative_roll = _roll_d20() + c.initiative_modifier

    await db.flush()
    return sorted_combatants(encounter)


async def roll_combatant_initiative(
    db: AsyncSession,
    combatant_id: int,
) -> Combatant:
    """Roll (or re-roll) initiative for a single combatant."""
    result = await db.execute(select(Combatant).where(Combatant.id == combatant_id))
    combatant = result.scalar_one_or_none()
    if combatant is None:
        raise EncounterError("Combatant not found")

    combatant.initiative_roll = _roll_d20() + combatant.initiative_modifier
    await db.flush()
    return combatant


async def set_initiative_roll(
    db: AsyncSession,
    encounter_id: int,
    combatant_id: int,
    roll_value: int | None,
) -> Combatant:
    """Manually set (or clear) the initiative roll for a combatant.

    Used when players roll physical dice and want to enter the result,
    or when the GM needs to override a value.  Pass ``None`` to clear
    a previously entered manual roll so Grug will auto-roll on start.
    """
    result = await db.execute(
        select(Combatant).where(
            Combatant.id == combatant_id,
            Combatant.encounter_id == encounter_id,
        )
    )
    combatant = result.scalar_one_or_none()
    if combatant is None:
        raise EncounterError("Combatant not found")

    combatant.initiative_roll = roll_value  # None clears the roll
    await db.flush()
    return combatant


# ── Encounter lifecycle ──────────────────────────────────────────────


async def start_encounter(
    db: AsyncSession,
    encounter_id: int,
) -> Encounter:
    """Transition encounter from preparing → active. Rolls initiative for
    any combatants that haven't rolled yet."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")
    if encounter.status == STATUS_ACTIVE:
        return encounter  # already started
    if encounter.status == STATUS_ENDED:
        raise EncounterError("Cannot start an ended encounter")

    active = [c for c in encounter.combatants if c.is_active]
    if not active:
        raise EncounterError("Cannot start encounter with no combatants")

    # Auto-roll for anyone who hasn't rolled
    for c in active:
        if c.initiative_roll is None:
            c.initiative_roll = _roll_d20() + c.initiative_modifier

    encounter.status = STATUS_ACTIVE
    encounter.round_number = 1
    encounter.current_turn_index = 0
    await db.flush()
    return encounter


async def advance_turn(
    db: AsyncSession,
    encounter_id: int,
) -> tuple[Encounter, Combatant]:
    """Advance to the next combatant's turn. Returns (encounter, next_combatant)."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")
    if encounter.status != STATUS_ACTIVE:
        raise EncounterError("Encounter not active")

    order = sorted_combatants(encounter)
    if not order:
        raise EncounterError("No active combatants")

    next_idx = encounter.current_turn_index + 1
    if next_idx >= len(order):
        # New round
        next_idx = 0
        encounter.round_number += 1

    encounter.current_turn_index = next_idx
    await db.flush()

    return encounter, order[next_idx]


async def end_encounter(
    db: AsyncSession,
    encounter_id: int,
) -> Encounter:
    """End an encounter."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")
    if encounter.status == STATUS_ENDED:
        return encounter  # idempotent

    encounter.status = STATUS_ENDED
    encounter.ended_at = datetime.now(timezone.utc)
    await db.flush()
    return encounter


# ── Formatting ───────────────────────────────────────────────────────


def format_initiative_order(encounter: Encounter) -> str:
    """Build a human-readable initiative order string."""
    order = sorted_combatants(encounter)
    if not order:
        return "No combatants in encounter."

    lines: list[str] = []
    lines.append(f"⚔️ {encounter.name} — Round {encounter.round_number}")
    lines.append("")

    for idx, c in enumerate(order):
        marker = (
            "▶ "
            if idx == encounter.current_turn_index and encounter.status == STATUS_ACTIVE
            else "  "
        )
        roll_str = str(c.initiative_roll) if c.initiative_roll is not None else "—"
        enemy_tag = " [Enemy]" if c.is_enemy else ""
        # HP display for standard+ depth
        hp_str = ""
        if c.max_hp is not None and c.current_hp is not None:
            hp_str = f" ({c.current_hp}/{c.max_hp} HP)"
            if c.temp_hp:
                hp_str = f" ({c.current_hp}+{c.temp_hp}/{c.max_hp} HP)"
        ac_str = f" AC:{c.armor_class}" if c.armor_class is not None else ""
        cond_str = ""
        if c.conditions:
            cond_str = f" [{', '.join(c.conditions)}]"
        conc_str = ""
        if c.concentration_spell:
            conc_str = f" 🔮{c.concentration_spell}"
        lines.append(
            f"{marker}{roll_str:>3}  {c.name}{enemy_tag}{hp_str}{ac_str}{cond_str}{conc_str}"
        )

    return "\n".join(lines)


# ── Saving throws ────────────────────────────────────────────────────

# Standard ability abbreviations
ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


@dataclass
class SaveResult:
    """Result of a single saving throw roll."""

    combatant_id: int
    combatant_name: str
    roll: int
    modifier: int
    total: int
    dc: int
    passed: bool


async def roll_saving_throws(
    db: AsyncSession,
    encounter_id: int,
    combatant_ids: list[int],
    ability: str,
    dc: int,
) -> list[SaveResult]:
    """Roll saving throws for the specified combatants.

    Args:
        db: Database session.
        encounter_id: The encounter these combatants belong to.
        combatant_ids: Which combatants to roll for.
        ability: Ability abbreviation, e.g. "DEX".
        dc: Difficulty class to beat.

    Returns:
        List of SaveResult with pass/fail for each combatant.
    """
    ability = ability.upper()
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    results: list[SaveResult] = []
    for c in encounter.combatants:
        if c.id not in combatant_ids or not c.is_active:
            continue

        modifier = 0
        if c.save_modifiers and ability in c.save_modifiers:
            modifier = c.save_modifiers[ability]

        roll = _roll_d20()
        total = roll + modifier
        passed = total >= dc

        results.append(
            SaveResult(
                combatant_id=c.id,
                combatant_name=c.name,
                roll=roll,
                modifier=modifier,
                total=total,
                dc=dc,
                passed=passed,
            )
        )

    return results


def format_save_results(results: list[SaveResult], ability: str, dc: int) -> str:
    """Format saving throw results into a readable table."""
    if not results:
        return "No results."

    lines: list[str] = [f"🎲 {ability.upper()} Save DC {dc}:", ""]
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        mod_str = f"+{r.modifier}" if r.modifier >= 0 else str(r.modifier)
        lines.append(f"  {r.combatant_name}: {r.roll}{mod_str} = {r.total} {status}")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    lines.append(f"\nResults: {passed} passed, {failed} failed")
    return "\n".join(lines)


# ── HP & Damage tracking ────────────────────────────────────────────


async def deal_damage(
    db: AsyncSession,
    encounter_id: int,
    combatant_ids: list[int],
    amount: int,
    *,
    damage_type: str | None = None,
    source: str | None = None,
) -> list[tuple[Combatant, int]]:
    """Deal damage to one or more combatants. Returns list of (combatant, actual_damage_taken).

    Damage absorbs temp HP first, then reduces current HP.
    """
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    results: list[tuple[Combatant, int]] = []
    for c in encounter.combatants:
        if c.id not in combatant_ids or not c.is_active:
            continue
        if c.current_hp is None:
            # No HP tracking for this combatant
            continue

        remaining = amount
        actual_taken = 0

        # Absorb with temp HP first
        if c.temp_hp > 0:
            absorbed = min(c.temp_hp, remaining)
            c.temp_hp -= absorbed
            remaining -= absorbed

        # Apply to current HP
        if remaining > 0:
            actual_taken = remaining
            c.current_hp = max(0, c.current_hp - remaining)

        # Log the damage
        log_entry = CombatLogEntry(
            encounter_id=encounter_id,
            combatant_id=c.id,
            round_number=encounter.round_number,
            event_type="damage",
            details={
                "amount": amount,
                "actual_taken": actual_taken,
                "damage_type": damage_type,
                "source": source,
            },
        )
        db.add(log_entry)
        results.append((c, actual_taken))

    await db.flush()
    return results


async def heal_combatant(
    db: AsyncSession,
    encounter_id: int,
    combatant_ids: list[int],
    amount: int,
    *,
    source: str | None = None,
) -> list[tuple[Combatant, int]]:
    """Heal one or more combatants. Returns list of (combatant, actual_healed).

    Cannot exceed max_hp. Resets death saves if HP goes above 0.
    """
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    results: list[tuple[Combatant, int]] = []
    for c in encounter.combatants:
        if c.id not in combatant_ids or not c.is_active:
            continue
        if c.current_hp is None or c.max_hp is None:
            continue

        old_hp = c.current_hp
        c.current_hp = min(c.max_hp, c.current_hp + amount)
        actual = c.current_hp - old_hp

        # Healing resets death saves
        if old_hp == 0 and c.current_hp > 0:
            c.death_save_successes = 0
            c.death_save_failures = 0

        log_entry = CombatLogEntry(
            encounter_id=encounter_id,
            combatant_id=c.id,
            round_number=encounter.round_number,
            event_type="healing",
            details={"amount": amount, "actual_healed": actual, "source": source},
        )
        db.add(log_entry)
        results.append((c, actual))

    await db.flush()
    return results


def format_damage_results(
    results: list[tuple[Combatant, int]], amount: int, damage_type: str | None
) -> str:
    """Format damage results into readable text."""
    if not results:
        return "No valid targets."
    dtype = f" {damage_type}" if damage_type else ""
    lines: list[str] = [f"💥 {amount}{dtype} damage!", ""]
    for c, actual in results:
        hp_str = f"{c.current_hp}/{c.max_hp}" if c.max_hp else "?"
        temp_str = f"+{c.temp_hp} temp" if c.temp_hp else ""
        down_str = " 💀 DOWN!" if c.current_hp == 0 else ""
        lines.append(f"  {c.name}: took {actual} → {hp_str} {temp_str}{down_str}")
    return "\n".join(lines)


def format_heal_results(results: list[tuple[Combatant, int]], amount: int) -> str:
    """Format healing results into readable text."""
    if not results:
        return "No valid targets."
    lines: list[str] = [f"💚 {amount} healing!", ""]
    for c, actual in results:
        hp_str = f"{c.current_hp}/{c.max_hp}" if c.max_hp else "?"
        lines.append(f"  {c.name}: healed {actual} → {hp_str}")
    return "\n".join(lines)


# ── Conditions ───────────────────────────────────────────────────────

# Predefined conditions per system
CONDITIONS_5E = [
    "Blinded",
    "Charmed",
    "Deafened",
    "Frightened",
    "Grappled",
    "Incapacitated",
    "Invisible",
    "Paralyzed",
    "Petrified",
    "Poisoned",
    "Prone",
    "Restrained",
    "Stunned",
    "Unconscious",
    "Exhaustion",
]

CONDITIONS_PF2E = [
    "Blinded",
    "Broken",
    "Clumsy",
    "Concealed",
    "Confused",
    "Controlled",
    "Dazzled",
    "Deafened",
    "Doomed",
    "Drained",
    "Dying",
    "Encumbered",
    "Enfeebled",
    "Fascinated",
    "Fatigued",
    "Fleeing",
    "Frightened",
    "Grabbed",
    "Hidden",
    "Immobilized",
    "Invisible",
    "Observed",
    "Off-Guard",
    "Paralyzed",
    "Petrified",
    "Prone",
    "Quickened",
    "Restrained",
    "Sickened",
    "Slowed",
    "Stunned",
    "Stupefied",
    "Unconscious",
    "Undetected",
    "Unnoticed",
    "Wounded",
]

SYSTEM_CONDITIONS: dict[str, list[str]] = {
    "dnd5e": CONDITIONS_5E,
    "pf2e": CONDITIONS_PF2E,
}


async def add_condition(
    db: AsyncSession,
    encounter_id: int,
    combatant_ids: list[int],
    condition: str,
) -> list[Combatant]:
    """Add a condition to one or more combatants."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    affected: list[Combatant] = []
    for c in encounter.combatants:
        if c.id not in combatant_ids or not c.is_active:
            continue

        current = list(c.conditions or [])
        if condition not in current:
            current.append(condition)
            c.conditions = current

            log_entry = CombatLogEntry(
                encounter_id=encounter_id,
                combatant_id=c.id,
                round_number=encounter.round_number,
                event_type="condition_add",
                details={"condition": condition},
            )
            db.add(log_entry)
            affected.append(c)

    await db.flush()
    return affected


async def remove_condition(
    db: AsyncSession,
    encounter_id: int,
    combatant_ids: list[int],
    condition: str,
) -> list[Combatant]:
    """Remove a condition from one or more combatants."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    affected: list[Combatant] = []
    for c in encounter.combatants:
        if c.id not in combatant_ids or not c.is_active:
            continue

        current = list(c.conditions or [])
        if condition in current:
            current.remove(condition)
            c.conditions = current if current else None

            log_entry = CombatLogEntry(
                encounter_id=encounter_id,
                combatant_id=c.id,
                round_number=encounter.round_number,
                event_type="condition_remove",
                details={"condition": condition},
            )
            db.add(log_entry)
            affected.append(c)

    await db.flush()
    return affected


# ── Death saves & Concentration (full depth) ─────────────────────────


async def roll_death_save(
    db: AsyncSession,
    encounter_id: int,
    combatant_id: int,
) -> tuple[Combatant, int, bool, str]:
    """Roll a death saving throw for a combatant at 0 HP.

    Returns:
        (combatant, roll, success, status_message)
        status_message is one of: 'success', 'failure', 'stabilized', 'dead',
        'nat20_revive', 'nat1_double_fail'
    """
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    combatant = None
    for c in encounter.combatants:
        if c.id == combatant_id and c.is_active:
            combatant = c
            break

    if combatant is None:
        raise EncounterError("Combatant not found")
    if combatant.current_hp is None or combatant.current_hp > 0:
        raise EncounterError(f"{combatant.name} is not at 0 HP — no death save needed")

    roll = _roll_d20()

    if roll == 20:
        # Natural 20: regain 1 HP, reset death saves
        combatant.current_hp = 1
        combatant.death_save_successes = 0
        combatant.death_save_failures = 0
        status = "nat20_revive"
        success = True
    elif roll == 1:
        # Natural 1: two failures
        combatant.death_save_failures = min(3, combatant.death_save_failures + 2)
        status = "nat1_double_fail"
        success = False
    elif roll >= 10:
        combatant.death_save_successes += 1
        success = True
        status = "success"
    else:
        combatant.death_save_failures += 1
        success = False
        status = "failure"

    # Check for stabilized or dead
    if combatant.death_save_successes >= 3:
        status = "stabilized"
        combatant.death_save_successes = 3
    if combatant.death_save_failures >= 3:
        status = "dead"
        combatant.death_save_failures = 3

    log_entry = CombatLogEntry(
        encounter_id=encounter_id,
        combatant_id=combatant.id,
        round_number=encounter.round_number,
        event_type="death_save",
        details={"roll": roll, "success": success, "status": status},
    )
    db.add(log_entry)
    await db.flush()

    return combatant, roll, success, status


async def set_concentration(
    db: AsyncSession,
    encounter_id: int,
    combatant_id: int,
    spell: str | None,
) -> Combatant:
    """Set or clear concentration for a combatant."""
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    combatant = None
    for c in encounter.combatants:
        if c.id == combatant_id and c.is_active:
            combatant = c
            break

    if combatant is None:
        raise EncounterError("Combatant not found")

    combatant.concentration_spell = spell
    await db.flush()
    return combatant


async def check_concentration(
    db: AsyncSession,
    encounter_id: int,
    combatant_id: int,
    damage_taken: int,
) -> tuple[Combatant, int, int, bool] | None:
    """Check concentration after taking damage.

    Returns (combatant, dc, roll_total, passed) or None if not concentrating.
    The DC is max(10, damage_taken // 2).
    """
    encounter = await get_encounter_by_id(db, encounter_id)
    if encounter is None:
        raise EncounterError("Encounter not found")

    combatant = None
    for c in encounter.combatants:
        if c.id == combatant_id and c.is_active:
            combatant = c
            break

    if combatant is None:
        raise EncounterError("Combatant not found")

    if not combatant.concentration_spell:
        return None

    dc = max(10, damage_taken // 2)
    roll = _roll_d20()
    modifier = 0
    if combatant.save_modifiers and "CON" in combatant.save_modifiers:
        modifier = combatant.save_modifiers["CON"]
    total = roll + modifier
    passed = total >= dc

    log_entry = CombatLogEntry(
        encounter_id=encounter_id,
        combatant_id=combatant.id,
        round_number=encounter.round_number,
        event_type="concentration_check" if passed else "concentration_broken",
        details={
            "dc": dc,
            "roll": roll,
            "modifier": modifier,
            "total": total,
            "passed": passed,
            "spell": combatant.concentration_spell,
        },
    )
    db.add(log_entry)

    if not passed:
        combatant.concentration_spell = None

    await db.flush()
    return combatant, dc, total, passed
