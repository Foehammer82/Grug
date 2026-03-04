"""Encounter / initiative tracking routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import (
    assert_guild_member,
    get_current_user,
    get_db,
    is_guild_admin,
)
from api.schemas import CombatantCreate, CombatantOut, EncounterCreate, EncounterOut
from grug.db.models import Campaign, Encounter
from grug.encounter import (
    EncounterError,
    add_combatant,
    advance_turn,
    create_encounter,
    end_encounter,
    get_active_encounter,
    get_encounter_by_id,
    remove_combatant,
    roll_all_initiative,
    roll_combatant_initiative,
    sorted_combatants,
    start_encounter,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["encounters"])


def _serialize(enc: Encounter) -> EncounterOut:
    """Build an EncounterOut with combatants sorted by initiative."""
    order = sorted_combatants(enc)
    return EncounterOut(
        id=enc.id,
        campaign_id=enc.campaign_id,
        guild_id=enc.guild_id,
        name=enc.name,
        status=enc.status,
        current_turn_index=enc.current_turn_index,
        round_number=enc.round_number,
        channel_id=enc.channel_id,
        created_by=enc.created_by,
        created_at=enc.created_at,
        ended_at=enc.ended_at,
        combatants=[CombatantOut.model_validate(c) for c in order],
    )


async def _get_campaign(db: AsyncSession, guild_id: int, campaign_id: int) -> Campaign:
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
    return campaign


async def _get_encounter_or_404(db: AsyncSession, encounter_id: int) -> Encounter:
    enc = await get_encounter_by_id(db, encounter_id)
    if enc is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    return enc


# ── Encounter CRUD ───────────────────────────────────────────────────


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters",
    response_model=EncounterOut,
    status_code=201,
)
async def create_encounter_route(
    guild_id: int,
    campaign_id: int,
    body: EncounterCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    campaign = await _get_campaign(db, guild_id, campaign_id)

    # Only admins / GM can create encounters
    user_id = int(user["id"])
    admin = await is_guild_admin(guild_id, user)
    is_gm = campaign.gm_discord_user_id == user_id
    if not admin and not is_gm:
        raise HTTPException(
            status_code=403, detail="Only GM or admin can create encounters"
        )

    channel_id = int(body.channel_id) if body.channel_id else None
    enc = await create_encounter(
        db,
        campaign_id=campaign_id,
        guild_id=guild_id,
        name=body.name,
        created_by=user_id,
        channel_id=channel_id,
    )
    await db.commit()
    await db.refresh(enc, attribute_names=["combatants"])
    return _serialize(enc)


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/active",
    response_model=EncounterOut | None,
)
async def get_active_encounter_route(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut | None:
    await assert_guild_member(guild_id, user)
    await _get_campaign(db, guild_id, campaign_id)

    enc = await get_active_encounter(db, campaign_id)
    if enc is None:
        return None
    return _serialize(enc)


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters",
    response_model=list[EncounterOut],
)
async def list_encounters(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EncounterOut]:
    await assert_guild_member(guild_id, user)
    await _get_campaign(db, guild_id, campaign_id)

    result = await db.execute(
        select(Encounter)
        .options(selectinload(Encounter.combatants))
        .where(
            Encounter.campaign_id == campaign_id,
            Encounter.guild_id == guild_id,
        )
        .order_by(desc(Encounter.created_at))
        .limit(20)
    )
    return [_serialize(e) for e in result.scalars().all()]


# ── Combatant management ────────────────────────────────────────────


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants",
    response_model=CombatantOut,
    status_code=201,
)
async def add_combatant_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    body: CombatantCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CombatantOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    combatant = await add_combatant(
        db,
        encounter_id=encounter_id,
        name=body.name,
        initiative_modifier=body.initiative_modifier,
        is_enemy=body.is_enemy,
        character_id=body.character_id,
    )
    await db.commit()
    await db.refresh(combatant)
    return CombatantOut.model_validate(combatant)


@router.delete(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}",
    status_code=204,
)
async def remove_combatant_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        await remove_combatant(db, encounter_id, combatant_id)
    except EncounterError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await db.commit()


# ── Initiative rolling ──────────────────────────────────────────────


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/roll-initiative",
    response_model=EncounterOut,
)
async def roll_initiative_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        await roll_all_initiative(db, encounter_id)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}/roll-initiative",
    response_model=CombatantOut,
)
async def roll_combatant_initiative_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CombatantOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        c = await roll_combatant_initiative(db, combatant_id)
    except EncounterError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await db.commit()
    await db.refresh(c)
    return CombatantOut.model_validate(c)


# ── Encounter lifecycle ─────────────────────────────────────────────


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/start",
    response_model=EncounterOut,
)
async def start_encounter_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        enc = await start_encounter(db, encounter_id)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/advance",
    response_model=EncounterOut,
)
async def advance_turn_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        enc, _ = await advance_turn(db, encounter_id)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/end",
    response_model=EncounterOut,
)
async def end_encounter_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        enc = await end_encounter(db, encounter_id)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)
