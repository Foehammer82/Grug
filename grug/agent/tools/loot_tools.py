"""Loot generation agent tools — GM treasure bundles using PF2e guidelines.

Registers tools that let Grug generate level-appropriate treasure bundles
following the official PF2e *Party Treasure by Level* table and populated
with real items from Archives of Nethys.

Reference: https://2e.aonprd.com/Rules.aspx?ID=2656
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from grug.loot import _TreasureRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Campaign party auto-detection
# ---------------------------------------------------------------------------


async def _get_party_info(campaign_id: int) -> tuple[int, int] | None:
    """Infer *(party_level, party_size)* from a campaign's character roster.

    Reads each character's ``structured_data["level"]`` and returns the
    average level (rounded) and total character count.

    Returns ``None`` if the campaign has no characters with level data.
    """
    from sqlalchemy import select

    from grug.db.models import Character
    from grug.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        chars = (
            await session.execute(
                select(Character).where(Character.campaign_id == campaign_id)
            )
        ).scalars().all()

    if not chars:
        return None

    levels: list[int] = []
    for char in chars:
        sd = char.structured_data or {}
        level = sd.get("level")
        if isinstance(level, int) and level > 0:
            levels.append(level)

    if not levels:
        return None

    avg_level = round(sum(levels) / len(levels))
    return max(1, min(20, avg_level)), len(chars)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_loot_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register loot generation tools on *agent*."""

    @agent.tool
    async def generate_loot(
        ctx: RunContext[GrugDeps],
        party_level: int = 0,
        party_size: int = 0,
    ) -> str:
        """Generate a level-appropriate treasure bundle for a PF2e party.

        Uses the official Pathfinder 2e *Party Treasure by Level* table to
        determine the right mix of permanent items, consumables, and currency,
        then searches Archives of Nethys for real items at the correct levels.

        Only the GM or a guild admin may generate loot.

        If the current channel is linked to a campaign with characters that
        have level data, ``party_level`` and ``party_size`` are automatically
        inferred from the roster.  You can still override them explicitly.

        Use when the GM says things like "generate loot for level 5",
        "roll treasure for a level 8 party", "what loot should I give my
        level 3 party", or "create a treasure hoard".

        Parameters
        ----------
        party_level:
            The party's current level (1–20).  Set to 0 or omit to
            auto-detect from the campaign's character roster.
        party_size:
            Number of PCs in the party.  Set to 0 or omit to auto-detect
            from the campaign.
        """
        from grug.agent.tools.banking_tools import _is_admin_or_gm
        from grug.loot import (
            format_loot_table,
            get_treasure_budget,
            pick_random_items,
        )

        # ── Permission check ──────────────────────────────────────────────
        if not await _is_admin_or_gm(ctx):
            return (
                "Only the GM or a guild admin can generate loot. "
                "Ask your GM to use this tool!"
            )

        # ── Auto-detect from campaign if not specified ────────────────────
        if party_level == 0 or party_size == 0:
            if ctx.deps.campaign_id is not None:
                info = await _get_party_info(ctx.deps.campaign_id)
                if info is not None:
                    detected_level, detected_size = info
                    if party_level == 0:
                        party_level = detected_level
                    if party_size == 0:
                        party_size = detected_size

        # Fall back to default party size if still unknown
        if party_size == 0:
            party_size = 4

        # ── Validate level ────────────────────────────────────────────────
        if party_level < 1 or party_level > 20:
            return (
                "Party level must be between 1 and 20. "
                "No campaign is linked to this channel (or the campaign's "
                "characters don't have level data). Please specify party_level."
            )

        if party_size < 1 or party_size > 12:
            return "Party size must be between 1 and 12."

        # ── Look up treasure budget ───────────────────────────────────────
        row = get_treasure_budget(party_level)
        if row is None:
            return f"No treasure data for level {party_level}."

        # ── Fetch items from AoN ──────────────────────────────────────────
        perm_items_by_level, cons_items_by_level = await _fetch_item_pools(row)

        # ── Pick random items ─────────────────────────────────────────────
        permanent_picks = pick_random_items(
            row.permanent_items, perm_items_by_level
        )
        consumable_picks = pick_random_items(
            row.consumables, cons_items_by_level
        )

        # ── Calculate currency ────────────────────────────────────────────
        extra = row.extra_currency_per_pc * max(0, party_size - 4)
        total_currency = row.currency_gp + extra

        # ── Format output ─────────────────────────────────────────────────
        loot_text = format_loot_table(
            party_level=party_level,
            party_size=party_size,
            permanent_picks=permanent_picks,
            consumable_picks=consumable_picks,
            currency_gp=total_currency,
        )

        return loot_text

    @agent.tool
    async def get_treasure_guidelines(
        ctx: RunContext[GrugDeps],
        party_level: int = 0,
        party_size: int = 0,
    ) -> str:
        """Look up the PF2e treasure-by-level guidelines for a given party level.

        Returns the official budget breakdown (permanent items, consumables,
        and currency) without generating specific items.  Useful when the GM
        wants to know the recommended treasure budget before deciding what
        to award.

        If the current channel is linked to a campaign, ``party_level`` and
        ``party_size`` can be auto-detected from the character roster.

        Use when someone asks "what's the treasure budget for level 7",
        "how much loot for a level 5 party", or "treasure guidelines".

        Parameters
        ----------
        party_level:
            The party's current level (1–20).  Set to 0 or omit to
            auto-detect from the campaign.
        party_size:
            Number of PCs in the party.  Set to 0 or omit to auto-detect.
        """
        from grug.loot import format_treasure_table, get_treasure_budget

        # ── Auto-detect from campaign if not specified ────────────────────
        if party_level == 0 or party_size == 0:
            if ctx.deps.campaign_id is not None:
                info = await _get_party_info(ctx.deps.campaign_id)
                if info is not None:
                    detected_level, detected_size = info
                    if party_level == 0:
                        party_level = detected_level
                    if party_size == 0:
                        party_size = detected_size

        if party_size == 0:
            party_size = 4

        if party_level < 1 or party_level > 20:
            return (
                "Party level must be between 1 and 20. "
                "No campaign is linked to this channel (or the campaign's "
                "characters don't have level data). Please specify party_level."
            )

        row = get_treasure_budget(party_level)
        if row is None:
            return f"No treasure data for level {party_level}."

        return format_treasure_table(row, party_size=party_size)


async def _fetch_item_pools(row: _TreasureRow):
    """Fetch permanent and consumable item pools from AoN in parallel."""
    from grug.loot import fetch_items_for_slots

    perm_task = fetch_items_for_slots(row.permanent_items, "permanent")
    cons_task = fetch_items_for_slots(row.consumables, "consumable")
    perm_items_by_level, cons_items_by_level = await asyncio.gather(
        perm_task, cons_task
    )
    return perm_items_by_level, cons_items_by_level
