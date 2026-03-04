"""Encounter / initiative tracker service — shared logic for API and agent tools.

Every mutation goes through these functions so both the web dashboard
and the Discord agent get identical behaviour.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from grug.db.models import Combatant, Encounter

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
    character_id: int | None = None,
) -> Combatant:
    """Add a combatant to an encounter."""
    combatant = Combatant(
        encounter_id=encounter_id,
        name=name,
        initiative_modifier=initiative_modifier,
        is_enemy=is_enemy,
        character_id=character_id,
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
        lines.append(f"{marker}{roll_str:>3}  {c.name}{enemy_tag}")

    return "\n".join(lines)
