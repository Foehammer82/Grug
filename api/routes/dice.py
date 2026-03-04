"""Dice rolling routes — roll dice and view roll history within a campaign."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import delete, select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_member,
    get_current_user,
    get_db,
    is_guild_admin,
)
from api.schemas import DiceRollOut, DiceRollRequest, ManualDiceRecordRequest
from grug.db.models import Campaign, DiceRoll
from grug.dice import DiceError, RollType, format_roll, roll

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dice"])

# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------

_RETENTION_HOURS = 24
_RETENTION_MIN_ROLLS = 5  # always keep at least this many per player per campaign


async def _cleanup_old_rolls(db: AsyncSession, campaign_id: int) -> None:
    """Enforce the dice roll retention policy for a campaign.

    For each (campaign, roller) pair: keep all rolls from the past 24 hours
    PLUS the most recent ``_RETENTION_MIN_ROLLS`` rolls regardless of age.
    Older rolls beyond the minimum are deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_RETENTION_HOURS)

    # Identify all distinct rollers in this campaign
    roller_rows = await db.execute(
        select(DiceRoll.roller_discord_user_id)
        .where(DiceRoll.campaign_id == campaign_id)
        .distinct()
    )
    roller_ids = [r[0] for r in roller_rows.all()]

    for roller_id in roller_ids:
        # Find the IDs of the most recent N rolls for this roller
        recent_rows = await db.execute(
            select(DiceRoll.id)
            .where(
                DiceRoll.campaign_id == campaign_id,
                DiceRoll.roller_discord_user_id == roller_id,
            )
            .order_by(desc(DiceRoll.created_at))
            .limit(_RETENTION_MIN_ROLLS)
        )
        keep_ids = {r[0] for r in recent_rows.all()}

        # Delete rolls older than cutoff that are NOT in the keep set
        await db.execute(
            delete(DiceRoll).where(
                DiceRoll.campaign_id == campaign_id,
                DiceRoll.roller_discord_user_id == roller_id,
                DiceRoll.created_at < cutoff,
                DiceRoll.id.not_in(keep_ids),
            )
        )

    await db.commit()


def _serialize_roll(db_roll: DiceRoll, formatted: str = "") -> DiceRollOut:
    """Convert a DiceRoll ORM instance to the API output schema."""
    return DiceRollOut(
        id=db_roll.id,
        guild_id=db_roll.guild_id,
        campaign_id=db_roll.campaign_id,
        roller_discord_user_id=db_roll.roller_discord_user_id,
        roller_display_name=db_roll.roller_display_name,
        character_name=db_roll.character_name,
        expression=db_roll.expression,
        individual_rolls=db_roll.individual_rolls,
        total=db_roll.total,
        roll_type=db_roll.roll_type,
        is_private=db_roll.is_private,
        context_note=db_roll.context_note,
        formatted=formatted,
        created_at=db_roll.created_at,
    )


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/dice/roll",
    response_model=DiceRollOut,
)
async def roll_dice(
    guild_id: int,
    campaign_id: int,
    body: DiceRollRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiceRollOut:
    """Roll dice and persist the result."""
    await assert_guild_member(guild_id, user)

    # Verify campaign exists and belongs to guild
    campaign = (
        await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.guild_id == guild_id,
                Campaign.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Parse and roll
    try:
        result = roll(body.expression)
    except DiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Validate roll_type
    valid_types = {rt.value for rt in RollType}
    roll_type = body.roll_type if body.roll_type in valid_types else "general"

    # Serialise individual die results for DB storage
    individual_rolls = []
    for sign, comp in result.components:
        if hasattr(comp, "sides"):
            individual_rolls.append(
                {
                    "expression": comp.expression,
                    "sides": comp.sides,
                    "rolls": comp.rolls,
                    "kept": comp.kept,
                    "total": comp.total,
                    "sign": sign,
                }
            )
        else:
            individual_rolls.append({"constant": comp, "sign": sign})

    user_id = int(user["id"])
    display_name = user.get("username", str(user_id))

    db_roll = DiceRoll(
        guild_id=guild_id,
        campaign_id=campaign_id,
        roller_discord_user_id=user_id,
        roller_display_name=display_name,
        character_name=body.character_name,
        expression=body.expression,
        individual_rolls=individual_rolls,
        total=result.grand_total,
        roll_type=roll_type,
        is_private=body.is_private,
        context_note=body.context_note,
    )
    db.add(db_roll)
    await db.commit()
    await db.refresh(db_roll)

    formatted = format_roll(result)
    background_tasks.add_task(_cleanup_old_rolls, db, campaign_id)
    return _serialize_roll(db_roll, formatted)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/dice/record",
    response_model=DiceRollOut,
)
async def record_manual_roll(
    guild_id: int,
    campaign_id: int,
    body: ManualDiceRecordRequest,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiceRollOut:
    """Record a manual (physical) dice roll — the total is provided by the player."""
    await assert_guild_member(guild_id, user)

    campaign = (
        await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.guild_id == guild_id,
                Campaign.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not campaign.allow_manual_dice_recording:
        raise HTTPException(
            status_code=403,
            detail="Manual dice recording is not enabled for this campaign.",
        )

    valid_types = {rt.value for rt in RollType}
    roll_type = body.roll_type if body.roll_type in valid_types else "general"

    user_id = int(user["id"])
    display_name = user.get("username", str(user_id))

    db_roll = DiceRoll(
        guild_id=guild_id,
        campaign_id=campaign_id,
        roller_discord_user_id=user_id,
        roller_display_name=display_name,
        character_name=body.character_name,
        expression=body.expression,
        individual_rolls=[{"manual": True, "total": body.total}],
        total=body.total,
        roll_type=roll_type,
        is_private=body.is_private,
        context_note=body.context_note,
    )
    db.add(db_roll)
    await db.commit()
    await db.refresh(db_roll)

    background_tasks.add_task(_cleanup_old_rolls, db, campaign_id)
    return _serialize_roll(db_roll, f"{body.expression} = {body.total} (manual)")


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/dice/history",
    response_model=list[DiceRollOut],
)
async def dice_history(
    guild_id: int,
    campaign_id: int,
    roll_type: str | None = Query(None, description="Filter by roll type"),
    roller_id: str | None = Query(None, description="Filter by roller Discord user ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiceRollOut]:
    """Get dice roll history for a campaign.

    GM and admins see all rolls.  Other members see their own rolls plus
    any roll with ``is_private=False``.
    """
    await assert_guild_member(guild_id, user)

    # Verify campaign exists
    campaign = (
        await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.guild_id == guild_id,
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    user_id = int(user["id"])
    admin = await is_guild_admin(guild_id, user)
    is_gm = (
        campaign.gm_discord_user_id is not None
        and campaign.gm_discord_user_id == user_id
    )

    stmt = (
        select(DiceRoll)
        .where(
            DiceRoll.campaign_id == campaign_id,
            DiceRoll.guild_id == guild_id,
        )
        .order_by(desc(DiceRoll.created_at))
        .limit(limit)
        .offset(offset)
    )

    # Privacy filter: non-GM / non-admin only see public rolls + own rolls
    if not admin and not is_gm:
        stmt = stmt.where(
            or_(
                DiceRoll.is_private.is_(False),
                DiceRoll.roller_discord_user_id == user_id,
            )
        )

    # Optional filters
    if roll_type:
        stmt = stmt.where(DiceRoll.roll_type == roll_type)
    if roller_id:
        stmt = stmt.where(DiceRoll.roller_discord_user_id == int(roller_id))

    result = await db.execute(stmt)
    rolls = result.scalars().all()

    return [_serialize_roll(r) for r in rolls]
