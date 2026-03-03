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
) -> list[RuleSourceOut]:
    """Return all custom rule sources configured for this guild."""
    assert_guild_member(guild_id, user)

    result = await db.execute(
        select(RuleSource)
        .where(RuleSource.guild_id == guild_id)
        .order_by(RuleSource.created_at)
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
) -> RuleSourceOut:
    """Add a new custom rule source for this guild."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    from grug.utils import ensure_guild

    await ensure_guild(guild_id)
    now = datetime.now(timezone.utc)
    src = RuleSource(
        guild_id=guild_id,
        name=body.name,
        url=body.url,
        system=body.system,
        notes=body.notes,
        enabled=body.enabled,
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
) -> RuleSourceOut:
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
