"""Rule-source routes — manage TTRPG lookup sources per guild."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_current_user,
    get_db,
)
from api.schemas import (
    BuiltinOverrideUpdate,
    BuiltinRuleSourceOut,
    RuleSourceCreate,
    RuleSourceOut,
    RuleSourceTestRequest,
    RuleSourceTestResult,
    RuleSourceUpdate,
)
from grug.db.models import GuildBuiltinOverride, RuleSource
from grug.rules.sources import BUILTIN_RULE_SOURCES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rule-sources"])


# ── Built-in sources ─────────────────────────────────────────────────────────


@router.get(
    "/api/guilds/{guild_id}/rule-sources/builtins",
    response_model=list[BuiltinRuleSourceOut],
)
async def list_builtin_sources(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BuiltinRuleSourceOut]:
    """Return all built-in rule sources with their effective enabled state for this guild."""
    assert_guild_member(guild_id, user)

    result = await db.execute(
        select(GuildBuiltinOverride).where(GuildBuiltinOverride.guild_id == guild_id)
    )
    overrides: dict[str, bool] = {
        row.source_id: row.enabled for row in result.scalars().all()
    }

    return [
        BuiltinRuleSourceOut(
            source_id=src.source_id,
            name=src.name,
            description=src.description,
            system=src.system,
            url=src.url,
            enabled=overrides.get(src.source_id, True),
        )
        for src in BUILTIN_RULE_SOURCES
    ]


@router.patch(
    "/api/guilds/{guild_id}/rule-sources/builtins/{source_id}",
    response_model=BuiltinRuleSourceOut,
)
async def update_builtin_source(
    guild_id: int,
    source_id: str,
    body: BuiltinOverrideUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuiltinRuleSourceOut:
    """Enable or disable a built-in rule source for this guild."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    from grug.rules.sources import BUILTIN_SOURCES_BY_ID

    builtin = BUILTIN_SOURCES_BY_ID.get(source_id)
    if builtin is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown built-in source '{source_id}'."
        )

    result = await db.execute(
        select(GuildBuiltinOverride).where(
            GuildBuiltinOverride.guild_id == guild_id,
            GuildBuiltinOverride.source_id == source_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        from grug.utils import ensure_guild

        await ensure_guild(guild_id)
        row = GuildBuiltinOverride(
            guild_id=guild_id, source_id=source_id, enabled=body.enabled
        )
        db.add(row)
    else:
        row.enabled = body.enabled

    await db.commit()

    return BuiltinRuleSourceOut(
        source_id=builtin.source_id,
        name=builtin.name,
        description=builtin.description,
        system=builtin.system,
        url=builtin.url,
        enabled=row.enabled,
    )


# ── Custom sources ────────────────────────────────────────────────────────────


@router.get(
    "/api/guilds/{guild_id}/rule-sources",
    response_model=list[RuleSourceOut],
)
async def list_rule_sources(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RuleSource]:
    """Return all custom rule sources configured for this guild."""
    assert_guild_member(guild_id, user)

    result = await db.execute(
        select(RuleSource)
        .where(RuleSource.guild_id == guild_id)
        .order_by(RuleSource.sort_order, RuleSource.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/rule-sources",
    response_model=RuleSourceOut,
    status_code=201,
)
async def create_rule_source(
    guild_id: int,
    body: RuleSourceCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RuleSource:
    """Add a new custom rule source for this guild."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    from sqlalchemy import func
    from grug.utils import ensure_guild

    await ensure_guild(guild_id)

    # Place the new source at the end of the custom list (max sort_order + 10, or 0).
    max_result = await db.execute(
        select(func.max(RuleSource.sort_order)).where(RuleSource.guild_id == guild_id)
    )
    max_order = max_result.scalar_one_or_none()
    next_order = (max_order + 10) if max_order is not None else 0

    now = datetime.now(timezone.utc)
    src = RuleSource(
        guild_id=guild_id,
        name=body.name,
        url=body.url,
        system=body.system,
        notes=body.notes,
        enabled=body.enabled,
        sort_order=next_order,
        created_at=now,
        updated_at=now,
    )
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return src


@router.patch(
    "/api/guilds/{guild_id}/rule-sources/{source_id}",
    response_model=RuleSourceOut,
)
async def update_rule_source(
    guild_id: int,
    source_id: int,
    body: RuleSourceUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RuleSource:
    """Update a custom rule source."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    result = await db.execute(
        select(RuleSource).where(
            RuleSource.id == source_id,
            RuleSource.guild_id == guild_id,
        )
    )
    src = result.scalar_one_or_none()
    if src is None:
        raise HTTPException(status_code=404, detail="Rule source not found.")

    for field in body.model_fields_set:
        setattr(src, field, getattr(body, field))
    src.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(src)
    return src


@router.delete(
    "/api/guilds/{guild_id}/rule-sources/{source_id}",
    status_code=204,
)
async def delete_rule_source(
    guild_id: int,
    source_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a custom rule source."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    result = await db.execute(
        select(RuleSource).where(
            RuleSource.id == source_id,
            RuleSource.guild_id == guild_id,
        )
    )
    src = result.scalar_one_or_none()
    if src is None:
        raise HTTPException(status_code=404, detail="Rule source not found.")

    await db.delete(src)
    await db.commit()


# ── Test a source ────────────────────────────────────────────────────────────


@router.post(
    "/api/guilds/{guild_id}/rule-sources/test",
    response_model=RuleSourceTestResult,
)
async def test_rule_source(
    guild_id: int,
    body: RuleSourceTestRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> RuleSourceTestResult:
    """Run a live test query against a single rule source and return raw text."""
    assert_guild_member(guild_id, user)

    from grug.agent.tools.rules_tools import (
        _fetch_aon_pf2e,
        _fetch_custom_source,
        _fetch_open5e,
        _fetch_srd_5e,
    )

    try:
        if body.source_id == "aon_pf2e":
            text = await _fetch_aon_pf2e(body.query, size=3)
        elif body.source_id == "srd_5e":
            text = await _fetch_srd_5e(body.query)
        elif body.source_id == "open5e":
            text = await _fetch_open5e(body.query)
        elif body.source_name and body.source_url:
            text = await _fetch_custom_source(
                body.source_name, body.source_url, body.query
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Supply source_id for built-ins or source_name+source_url for custom.",
            )
        return RuleSourceTestResult(result=text)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Rule source test failed: %s", exc)
        return RuleSourceTestResult(result=str(exc), error=True)
