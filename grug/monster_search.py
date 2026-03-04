"""Monster search service — search for monsters/NPCs from built-in rule sources.

Provides structured monster data (HP, AC, saves, initiative modifier) for
encounter building. Uses the same APIs as the rule lookup tools but returns
structured data instead of formatted text.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_5E = "https://www.dnd5eapi.co"
BASE_AON = "https://elasticsearch.aonprd.com"

# ---------------------------------------------------------------------------
# In-memory TTL cache for monster search results
# ---------------------------------------------------------------------------

_CACHE_TTL = 300  # 5 minutes
_monster_cache: dict[str, tuple[list[Any], float]] = {}  # key → (results, expires_at)


def _cache_key(query: str, system: str | None, limit: int) -> str:
    return f"{query.lower().strip()}|{system}|{limit}"


def _cache_get(key: str) -> list[Any] | None:
    entry = _monster_cache.get(key)
    if entry is None:
        return None
    results, expires_at = entry
    if time.monotonic() > expires_at:
        del _monster_cache[key]
        return None
    return results


def _cache_set(key: str, results: list[Any]) -> None:
    # Evict expired entries to prevent unbounded growth (keep at most 200 entries)
    if len(_monster_cache) >= 200:
        now = time.monotonic()
        expired = [k for k, (_, exp) in _monster_cache.items() if now > exp]
        for k in expired:
            del _monster_cache[k]
    _monster_cache[key] = (results, time.monotonic() + _CACHE_TTL)


@dataclass
class MonsterResult:
    """Structured monster data for encounter building."""

    name: str
    source: str  # "srd_5e" or "aon_pf2e"
    system: str  # "dnd5e" or "pf2e"
    hp: int | None = None
    ac: int | None = None
    initiative_modifier: int | None = None
    cr: str | None = None
    size: str | None = None
    type: str | None = None
    save_modifiers: dict[str, int] | None = None


def _ability_mod(score: int) -> int:
    """Calculate ability modifier from score."""
    return (score - 10) // 2


def _first_str(val: Any) -> str | None:
    """Return the first element if val is a list, or val itself if a string."""
    if isinstance(val, list):
        return val[0] if val else None
    return val if isinstance(val, str) else None


async def search_monsters_5e(query: str, limit: int = 10) -> list[MonsterResult]:
    """Search D&D 5e SRD monsters by name substring."""

    async with httpx.AsyncClient(timeout=10) as http:
        # Search by name substring
        try:
            resp = await http.get(
                f"{BASE_5E}/api/2014/monsters",
                params={"name": query},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            entries = data.get("results", [])[:limit]
        except Exception:
            logger.exception("5e monster search failed for %r", query)
            return []

        # Fetch full details for all matches in parallel
        async def _fetch_detail(entry: dict) -> MonsterResult | None:
            url = entry.get("url", "")
            if not url:
                return None
            try:
                detail_resp = await http.get(f"{BASE_5E}{url}")
                if detail_resp.status_code != 200:
                    return None
                d = detail_resp.json()

                # Parse AC
                ac_list = d.get("armor_class") or []
                ac = None
                if isinstance(ac_list, list) and ac_list:
                    ac_val = ac_list[0].get("value")
                    if isinstance(ac_val, (int, float)):
                        ac = int(ac_val)

                # Parse HP
                hp = d.get("hit_points")
                if not isinstance(hp, int):
                    hp = None

                # Initiative modifier = DEX modifier
                dex = d.get("dexterity")
                init_mod = _ability_mod(dex) if isinstance(dex, int) else None

                # Save modifiers from proficiencies
                saves: dict[str, int] = {}
                for prof in d.get("proficiencies", []):
                    prof_name = (
                        prof.get("proficiency", {}).get("name", "")
                        if isinstance(prof.get("proficiency"), dict)
                        else ""
                    )
                    val = prof.get("value")
                    if prof_name.startswith("Saving Throw:") and isinstance(
                        val, (int, float)
                    ):
                        ability = prof_name.split(":")[-1].strip()[:3].upper()
                        saves[ability] = int(val)

                return MonsterResult(
                    name=d.get("name", entry.get("name", "Unknown")),
                    source="srd_5e",
                    system="dnd5e",
                    hp=hp,
                    ac=ac,
                    initiative_modifier=init_mod,
                    cr=str(d.get("challenge_rating", "")),
                    size=d.get("size", ""),
                    type=d.get("type", ""),
                    save_modifiers=saves if saves else None,
                )
            except Exception:
                logger.exception("5e monster detail fetch failed for %s", url)
                return None

        detail_results = await asyncio.gather(*[_fetch_detail(e) for e in entries])
        return [r for r in detail_results if r is not None]


async def search_monsters_pf2e(query: str, limit: int = 10) -> list[MonsterResult]:
    """Search PF2e monsters via Archives of Nethys Elasticsearch."""
    results: list[MonsterResult] = []

    body = {
        "size": limit,
        "query": {
            "bool": {
                "must": [
                    {"match": {"name": {"query": query, "fuzziness": "AUTO"}}},
                    {"term": {"category": "creature"}},
                ],
            }
        },
        "_source": [
            "name",
            "hp",
            "ac",
            "dex",
            "perception",
            "level",
            "size",
            "creature_type",
            "str",
            "con",
            "int",
            "wis",
            "cha",
            "fort_save",
            "ref_save",
            "will_save",
        ],
    }

    async with httpx.AsyncClient(timeout=10) as http:
        try:
            resp = await http.post(
                f"{BASE_AON}/aon/_search",
                json=body,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
        except Exception:
            logger.exception("PF2e monster search failed for %r", query)
            return []

        for hit in hits:
            src = hit.get("_source", {})
            name = src.get("name", "Unknown")

            # PF2e uses Perception for initiative by default
            perception = src.get("perception")
            init_mod = int(perception) if isinstance(perception, (int, float)) else None

            hp_val = src.get("hp")
            hp = int(hp_val) if isinstance(hp_val, (int, float)) else None

            ac_val = src.get("ac")
            ac = int(ac_val) if isinstance(ac_val, (int, float)) else None

            # PF2e saves
            saves: dict[str, int] = {}
            for key, ability in [
                ("fort_save", "CON"),
                ("ref_save", "DEX"),
                ("will_save", "WIS"),
            ]:
                val = src.get(key)
                if isinstance(val, (int, float)):
                    saves[ability] = int(val)

            level = src.get("level")
            cr_str = f"Level {level}" if level is not None else None

            # AON may return size/creature_type as a list; normalise to a plain string
            results.append(
                MonsterResult(
                    name=name,
                    source="aon_pf2e",
                    system="pf2e",
                    hp=hp,
                    ac=ac,
                    initiative_modifier=init_mod,
                    cr=cr_str,
                    size=_first_str(src.get("size")),
                    type=_first_str(src.get("creature_type")),
                    save_modifiers=saves if saves else None,
                )
            )

    return results


async def search_monsters(
    query: str, system: str | None = None, limit: int = 10
) -> list[MonsterResult]:
    """Search for monsters across all enabled sources.

    Args:
        query: Search term (monster name).
        system: Filter to a specific system ("dnd5e" or "pf2e"), or None for all.
        limit: Max results per source.

    Returns:
        List of MonsterResult sorted by relevance.
    """
    key = _cache_key(query, system, limit)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    results: list[MonsterResult] = []

    if system is None or system == "dnd5e":
        results.extend(await search_monsters_5e(query, limit=limit))

    if system is None or system == "pf2e":
        results.extend(await search_monsters_pf2e(query, limit=limit))

    _cache_set(key, results)
    return results
