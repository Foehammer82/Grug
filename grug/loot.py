"""PF2e loot generation — treasure tables and AoN item search.

Encodes the official Pathfinder 2e *Party Treasure by Level* table and
provides helpers that search Archives of Nethys for real items at the
requested item levels.

Reference: https://2e.aonprd.com/Rules.aspx?ID=2656
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Treasure-by-level table  (PF2e Remaster, party of 4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ItemSlot:
    """A slot in the treasure table: *count* items at *item_level*."""

    item_level: int
    count: int


@dataclass(frozen=True)
class _TreasureRow:
    """One row of the Party Treasure by Level table."""

    party_level: int
    permanent_items: tuple[_ItemSlot, ...]
    consumables: tuple[_ItemSlot, ...]
    currency_gp: int
    extra_currency_per_pc: int


# fmt: off
TREASURE_TABLE: dict[int, _TreasureRow] = {row.party_level: row for row in [
    _TreasureRow( 1, (_ItemSlot(2, 2), _ItemSlot(1, 2)), (_ItemSlot(2, 2), _ItemSlot(1, 3)),      40,    10),
    _TreasureRow( 2, (_ItemSlot(3, 2), _ItemSlot(2, 2)), (_ItemSlot(3, 2), _ItemSlot(2, 2), _ItemSlot(1, 2)),  70,    18),
    _TreasureRow( 3, (_ItemSlot(4, 2), _ItemSlot(3, 2)), (_ItemSlot(4, 2), _ItemSlot(3, 2), _ItemSlot(2, 2)), 120,    30),
    _TreasureRow( 4, (_ItemSlot(5, 2), _ItemSlot(4, 2)), (_ItemSlot(5, 2), _ItemSlot(4, 2), _ItemSlot(3, 2)), 200,    50),
    _TreasureRow( 5, (_ItemSlot(6, 2), _ItemSlot(5, 2)), (_ItemSlot(6, 2), _ItemSlot(5, 2), _ItemSlot(4, 2)), 320,    80),
    _TreasureRow( 6, (_ItemSlot(7, 2), _ItemSlot(6, 2)), (_ItemSlot(7, 2), _ItemSlot(6, 2), _ItemSlot(5, 2)), 500,   125),
    _TreasureRow( 7, (_ItemSlot(8, 2), _ItemSlot(7, 2)), (_ItemSlot(8, 2), _ItemSlot(7, 2), _ItemSlot(6, 2)), 720,   180),
    _TreasureRow( 8, (_ItemSlot(9, 2), _ItemSlot(8, 2)), (_ItemSlot(9, 2), _ItemSlot(8, 2), _ItemSlot(7, 2)), 1_000, 250),
    _TreasureRow( 9, (_ItemSlot(10, 2), _ItemSlot(9, 2)), (_ItemSlot(10, 2), _ItemSlot(9, 2), _ItemSlot(8, 2)), 1_400, 350),
    _TreasureRow(10, (_ItemSlot(11, 2), _ItemSlot(10, 2)), (_ItemSlot(11, 2), _ItemSlot(10, 2), _ItemSlot(9, 2)), 2_000, 500),
    _TreasureRow(11, (_ItemSlot(12, 2), _ItemSlot(11, 2)), (_ItemSlot(12, 2), _ItemSlot(11, 2), _ItemSlot(10, 2)), 2_800, 700),
    _TreasureRow(12, (_ItemSlot(13, 2), _ItemSlot(12, 2)), (_ItemSlot(13, 2), _ItemSlot(12, 2), _ItemSlot(11, 2)), 4_000, 1_000),
    _TreasureRow(13, (_ItemSlot(14, 2), _ItemSlot(13, 2)), (_ItemSlot(14, 2), _ItemSlot(13, 2), _ItemSlot(12, 2)), 6_000, 1_500),
    _TreasureRow(14, (_ItemSlot(15, 2), _ItemSlot(14, 2)), (_ItemSlot(15, 2), _ItemSlot(14, 2), _ItemSlot(13, 2)), 9_000, 2_250),
    _TreasureRow(15, (_ItemSlot(16, 2), _ItemSlot(15, 2)), (_ItemSlot(16, 2), _ItemSlot(15, 2), _ItemSlot(14, 2)), 13_000, 3_250),
    _TreasureRow(16, (_ItemSlot(17, 2), _ItemSlot(16, 2)), (_ItemSlot(17, 2), _ItemSlot(16, 2), _ItemSlot(15, 2)), 20_000, 5_000),
    _TreasureRow(17, (_ItemSlot(18, 2), _ItemSlot(17, 2)), (_ItemSlot(18, 2), _ItemSlot(17, 2), _ItemSlot(16, 2)), 30_000, 7_500),
    _TreasureRow(18, (_ItemSlot(19, 2), _ItemSlot(18, 2)), (_ItemSlot(19, 2), _ItemSlot(18, 2), _ItemSlot(17, 2)), 48_000, 12_000),
    _TreasureRow(19, (_ItemSlot(20, 2), _ItemSlot(19, 2)), (_ItemSlot(20, 2), _ItemSlot(19, 2), _ItemSlot(18, 2)), 80_000, 20_000),
    _TreasureRow(20, (_ItemSlot(20, 4),), (_ItemSlot(20, 4), _ItemSlot(19, 2)), 140_000, 35_000),
]}
# fmt: on


def get_treasure_budget(party_level: int) -> _TreasureRow | None:
    """Look up the PF2e treasure budget for *party_level*.

    Returns ``None`` if the level is out of range (1–20).
    """
    return TREASURE_TABLE.get(party_level)


def format_treasure_table(row: _TreasureRow, party_size: int = 4) -> str:
    """Format a treasure-budget row as human-readable text."""
    lines: list[str] = [
        f"**PF2e Treasure Budget — Party Level {row.party_level}** "
        f"(party of {party_size})",
        "",
    ]

    lines.append("**Permanent Items:**")
    for slot in row.permanent_items:
        lines.append(f"  • {slot.count}× item level {slot.item_level}")

    lines.append("")
    lines.append("**Consumables:**")
    for slot in row.consumables:
        lines.append(f"  • {slot.count}× item level {slot.item_level}")

    extra = row.extra_currency_per_pc * max(0, party_size - 4)
    total_currency = row.currency_gp + extra
    lines.append("")
    lines.append(f"**Currency:** {total_currency:,} gp")
    if party_size > 4:
        lines.append(
            f"  (base {row.currency_gp:,} gp + "
            f"{row.extra_currency_per_pc:,} gp × {party_size - 4} extra PCs)"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AoN item search helpers
# ---------------------------------------------------------------------------


@dataclass
class AoNItem:
    """A single item fetched from Archives of Nethys."""

    name: str
    item_level: int | None = None
    item_type: str = ""
    rarity: str = ""
    traits: list[str] = field(default_factory=list)
    url: str = ""
    price: str = ""
    description: str = ""


# Item sub-types commonly found in PF2e treasure
_CONSUMABLE_TYPES = frozenset({
    "Alchemical Bombs", "Alchemical Elixirs", "Alchemical Poisons",
    "Alchemical Tools", "Ammunition", "Fulu", "Gadget", "Magical Tattoo",
    "Oil", "Potion", "Scroll", "Snare", "Spellheart", "Talisman",
})

_PERMANENT_TYPES = frozenset({
    "Armor", "Held Item", "Shield", "Staff", "Wand", "Weapon", "Worn Item",
    "Apex Item", "Rune",
})


# ---------------------------------------------------------------------------
# In-memory TTL cache for AoN item searches
# ---------------------------------------------------------------------------
# AoN item data changes infrequently (only when new PF2e books release).
# A 1-hour TTL keeps repeated generate_loot calls fast while ensuring fresh
# data is fetched periodically.  Keyed by (item_level, category, size).

_ITEM_CACHE_TTL = 3600  # 1 hour
_ITEM_CACHE_MAX = 200  # max entries (20 levels × 3 categories × ~3 sizes)
_item_cache: dict[str, tuple[list[AoNItem], float]] = {}  # key → (results, expires_at)


def _item_cache_key(item_level: int, category: str, size: int) -> str:
    return f"{item_level}|{category}|{size}"


def _item_cache_get(key: str) -> list[AoNItem] | None:
    entry = _item_cache.get(key)
    if entry is None:
        return None
    results, expires_at = entry
    if time.monotonic() > expires_at:
        del _item_cache[key]
        return None
    return results


def _item_cache_set(key: str, results: list[AoNItem]) -> None:
    # Evict expired entries to prevent unbounded growth
    if len(_item_cache) >= _ITEM_CACHE_MAX:
        now = time.monotonic()
        expired = [k for k, (_, exp) in _item_cache.items() if now > exp]
        for k in expired:
            del _item_cache[k]
    _item_cache[key] = (results, time.monotonic() + _ITEM_CACHE_TTL)


async def search_aon_items(
    item_level: int,
    *,
    category: str = "any",
    size: int = 20,
) -> list[AoNItem]:
    """Search AoN Elasticsearch for PF2e items at a specific item level.

    Results are cached in-memory with a 1-hour TTL to avoid redundant
    network calls when generating loot for the same level repeatedly.

    Args:
        item_level: The PF2e item level to filter on.
        category: ``"permanent"``, ``"consumable"``, or ``"any"``.
        size: Max results to return from Elasticsearch.
    """
    # ── Check cache first ─────────────────────────────────────────────
    cache_key = _item_cache_key(item_level, category, size)
    cached = _item_cache_get(cache_key)
    if cached is not None:
        logger.debug("AoN item cache hit: level=%d category=%s", item_level, category)
        return cached

    try:
        from elasticsearch import AsyncElasticsearch
    except ImportError:
        logger.warning("elasticsearch package not installed — skipping AoN search")
        return []

    must_clauses: list[dict] = [
        {"term": {"type": "Item"}},
        {"term": {"level": item_level}},
    ]

    try:
        async with AsyncElasticsearch(
            "https://elasticsearch.aonprd.com/",
            headers={
                "Accept": "application/vnd.elasticsearch+json",
                "Content-Type": "application/vnd.elasticsearch+json",
            },
        ) as es:
            es_response = await es.search(
                index="aon",
                query={"bool": {"must": must_clauses}},
                source=[
                    "name", "type", "text", "url", "level",
                    "rarity", "trait_raw", "price_raw",
                    "item_category", "item_subcategory",
                ],
                size=size,
            )

        hits = es_response["hits"]["hits"]
        items: list[AoNItem] = []
        for hit in hits:
            src = hit["_source"]
            subcategory = src.get("item_subcategory", "")

            # Filter by category if requested
            if category == "consumable":
                if subcategory not in _CONSUMABLE_TYPES and "Consumable" not in (
                    src.get("trait_raw") or []
                ):
                    continue
            elif category == "permanent":
                if subcategory in _CONSUMABLE_TYPES or "Consumable" in (
                    src.get("trait_raw") or []
                ):
                    continue

            # Extract a short description from the text field
            full_text = (src.get("text") or "").strip()
            desc = full_text[:200] + "…" if len(full_text) > 200 else full_text

            items.append(
                AoNItem(
                    name=src.get("name", "?"),
                    item_level=src.get("level"),
                    item_type=subcategory or src.get("item_category", ""),
                    rarity=src.get("rarity", "Common"),
                    traits=src.get("trait_raw") or [],
                    url=(
                        f"https://2e.aonprd.com{src['url']}"
                        if src.get("url")
                        else ""
                    ),
                    price=src.get("price_raw", ""),
                    description=desc,
                )
            )

        # ── Store in cache ────────────────────────────────────────────
        _item_cache_set(cache_key, items)
        return items
    except Exception as exc:
        logger.warning("AoN item search failed for level %d: %s", item_level, exc)
        return []


async def fetch_items_for_slots(
    slots: tuple[_ItemSlot, ...],
    category: str,
) -> dict[int, list[AoNItem]]:
    """Fetch AoN items for all item-level slots in parallel.

    Returns a dict mapping item_level → list of available items.
    """
    levels = {s.item_level for s in slots}
    results = await asyncio.gather(
        *(search_aon_items(lvl, category=category) for lvl in levels),
        return_exceptions=True,
    )
    items_by_level: dict[int, list[AoNItem]] = {}
    for lvl, result in zip(levels, results, strict=True):
        if isinstance(result, Exception):
            logger.warning("Item fetch failed for level %d: %s", lvl, result)
            items_by_level[lvl] = []
        else:
            items_by_level[lvl] = result
    return items_by_level


def pick_random_items(
    slots: tuple[_ItemSlot, ...],
    items_by_level: dict[int, list[AoNItem]],
) -> list[AoNItem]:
    """Pick random items from the available pool to fill the slot requirements."""
    picked: list[AoNItem] = []
    for slot in slots:
        available = items_by_level.get(slot.item_level, [])
        if not available:
            # Create placeholder if no AoN items found
            for _ in range(slot.count):
                picked.append(
                    AoNItem(
                        name=f"[Level {slot.item_level} item — choose from AoN]",
                        item_level=slot.item_level,
                        url=f"https://2e.aonprd.com/Equipment.aspx?Level={slot.item_level}",
                    )
                )
            continue
        # Sample without replacement if possible, with replacement if not enough
        count = slot.count
        if len(available) >= count:
            picked.extend(random.sample(available, count))
        else:
            picked.extend(random.choices(available, k=count))
    return picked


def format_loot_table(
    party_level: int,
    party_size: int,
    permanent_picks: list[AoNItem],
    consumable_picks: list[AoNItem],
    currency_gp: int,
) -> str:
    """Format a generated loot bundle into a readable markdown summary."""
    lines: list[str] = [
        f"# 🎲 Loot Bundle — Party Level {party_level} (party of {party_size})",
        "",
        "*(Generated from PF2e Treasure by Level guidelines — "
        "https://2e.aonprd.com/Rules.aspx?ID=2656)*",
        "",
    ]

    if permanent_picks:
        lines.append("## Permanent Items")
        for item in permanent_picks:
            entry = f"• **{item.name}**"
            if item.item_level is not None:
                entry += f" (Level {item.item_level})"
            if item.rarity and item.rarity.lower() != "common":
                entry += f" [{item.rarity}]"
            if item.price:
                entry += f" — {item.price}"
            if item.item_type:
                entry += f" | {item.item_type}"
            if item.url:
                entry += f"\n  {item.url}"
            lines.append(entry)
        lines.append("")

    if consumable_picks:
        lines.append("## Consumables")
        for item in consumable_picks:
            entry = f"• **{item.name}**"
            if item.item_level is not None:
                entry += f" (Level {item.item_level})"
            if item.rarity and item.rarity.lower() != "common":
                entry += f" [{item.rarity}]"
            if item.price:
                entry += f" — {item.price}"
            if item.item_type:
                entry += f" | {item.item_type}"
            if item.url:
                entry += f"\n  {item.url}"
            lines.append(entry)
        lines.append("")

    lines.append(f"## Currency\n{currency_gp:,} gp")
    lines.append("")
    lines.append(
        "*Swap or adjust items to suit the party's needs. "
        "These are guidelines, not mandates!*"
    )

    return "\n".join(lines)
