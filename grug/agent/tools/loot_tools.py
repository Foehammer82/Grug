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


def register_loot_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register loot generation tools on *agent*."""

    @agent.tool
    async def generate_loot(
        ctx: RunContext[GrugDeps],
        party_level: int,
        party_size: int = 4,
    ) -> str:
        """Generate a level-appropriate treasure bundle for a PF2e party.

        Uses the official Pathfinder 2e *Party Treasure by Level* table to
        determine the right mix of permanent items, consumables, and currency,
        then searches Archives of Nethys for real items at the correct levels.

        Only the GM or a guild admin may generate loot.

        Use when the GM says things like "generate loot for level 5",
        "roll treasure for a level 8 party", "what loot should I give my
        level 3 party", or "create a treasure hoard".

        Parameters
        ----------
        party_level:
            The party's current level (1–20).
        party_size:
            Number of PCs in the party.  Defaults to 4.  Extra PCs add
            bonus currency per the official table.
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

        # ── Validate level ────────────────────────────────────────────────
        if party_level < 1 or party_level > 20:
            return "Party level must be between 1 and 20."

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
        party_level: int,
        party_size: int = 4,
    ) -> str:
        """Look up the PF2e treasure-by-level guidelines for a given party level.

        Returns the official budget breakdown (permanent items, consumables,
        and currency) without generating specific items.  Useful when the GM
        wants to know the recommended treasure budget before deciding what
        to award.

        Use when someone asks "what's the treasure budget for level 7",
        "how much loot for a level 5 party", or "treasure guidelines".

        Parameters
        ----------
        party_level:
            The party's current level (1–20).
        party_size:
            Number of PCs in the party.  Defaults to 4.
        """
        from grug.loot import format_treasure_table, get_treasure_budget

        if party_level < 1 or party_level > 20:
            return "Party level must be between 1 and 20."

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
