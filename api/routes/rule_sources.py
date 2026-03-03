"""Rule-source routes — manage TTRPG lookup sources per guild."""

import logging
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
    RuleSourceTestRequest,
    RuleSourceTestResult,
)
from grug.db.models import GuildBuiltinOverride
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
        _fetch_srd_5e,
    )

    try:
        if body.source_id == "aon_pf2e":
            text = await _fetch_aon_pf2e(body.query)
        elif body.source_id == "srd_5e":
            text = await _fetch_srd_5e(body.query)
        else:
            raise HTTPException(
                status_code=400,
                detail="Supply a valid source_id for a built-in source.",
            )
        return RuleSourceTestResult(result=text)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Rule source test failed: %s", exc)
        return RuleSourceTestResult(result=str(exc), error=True)
