"""Monster search routes — proxy to external rule-source APIs for structured monster data."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from api.schemas import MonsterSearchResult
from grug.monster_search import search_monsters

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monsters"])


@router.get(
    "/api/monsters/search",
    response_model=list[MonsterSearchResult],
)
async def search_monsters_route(
    q: str = Query(
        ..., min_length=1, max_length=100, description="Monster name substring"
    ),
    system: str | None = Query(None, description="Filter to 'dnd5e' or 'pf2e'"),
    limit: int = Query(5, ge=1, le=20, description="Max results per source"),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[MonsterSearchResult]:
    """Search for monsters across built-in rule sources.

    Returns structured data (HP, AC, initiative modifier, saves) suitable for
    adding combatants to an encounter.
    """
    results = await search_monsters(q, system=system, limit=limit)
    return [
        MonsterSearchResult(
            name=r.name,
            source=r.source,
            system=r.system,
            hp=r.hp,
            ac=r.ac,
            initiative_modifier=r.initiative_modifier,
            cr=r.cr,
            size=r.size,
            type=r.type,
            save_modifiers=r.save_modifiers,
        )
        for r in results
    ]
