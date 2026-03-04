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
from api.schemas import (
    CombatantCreate,
    CombatantOut,
    CombatantUpdate,
    CombatLogEntryOut,
    ConditionBody,
    ConcentrationBody,
    DamageHealBody,
    EncounterCreate,
    EncounterOut,
    EncounterUpdate,
    SavingThrowBody,
    SavingThrowResult,
    SetInitiativeBody,
)
from grug.db.models import Campaign, CombatLogEntry, Encounter
from grug.encounter import (
    EncounterError,
    add_combatant,
    add_condition,
    advance_turn,
    create_encounter,
    deal_damage,
    end_encounter,
    get_active_encounter,
    get_encounter_by_id,
    heal_combatant,
    remove_combatant,
    remove_condition,
    roll_all_initiative,
    roll_combatant_initiative,
    roll_death_save,
    roll_saving_throws,
    set_concentration,
    set_initiative_roll,
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


async def _assert_gm_or_admin(
    db: AsyncSession,
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any],
) -> None:
    """Raise 403 unless the user is a guild admin or the campaign GM."""
    user_id = int(user["id"])
    admin = await is_guild_admin(guild_id, user)
    if not admin:
        campaign = await _get_campaign(db, guild_id, campaign_id)
        if campaign.gm_discord_user_id != user_id:
            raise HTTPException(
                status_code=403, detail="Only GM or admin can modify encounters"
            )


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


# ── Encounter renaming ──────────────────────────────────────────────────


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}",
    response_model=EncounterOut,
)
async def rename_encounter_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    body: EncounterUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    """Rename an encounter.  GM or admin only."""
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")
    user_id = int(user["id"])
    admin = await is_guild_admin(guild_id, user)
    campaign = await _get_campaign(db, guild_id, campaign_id)
    is_gm = campaign.gm_discord_user_id == user_id
    if not admin and not is_gm:
        raise HTTPException(
            status_code=403, detail="Only GM or admin can rename encounters"
        )
    enc.name = body.name  # type: ignore[assignment]
    await db.commit()
    await db.refresh(enc, attribute_names=["combatants"])
    return _serialize(enc)


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}",
    response_model=EncounterOut,
)
async def rename_combatant_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    body: CombatantUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    """Update a combatant (currently: rename).  GM or admin only."""
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")
    user_id = int(user["id"])
    admin = await is_guild_admin(guild_id, user)
    campaign = await _get_campaign(db, guild_id, campaign_id)
    is_gm = campaign.gm_discord_user_id == user_id
    if not admin and not is_gm:
        raise HTTPException(
            status_code=403, detail="Only GM or admin can rename combatants"
        )
    combatant = next((c for c in enc.combatants if c.id == combatant_id), None)
    if combatant is None:
        raise HTTPException(status_code=404, detail="Combatant not found")
    if body.name is not None:
        combatant.name = body.name  # type: ignore[assignment]
    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

    combatant = await add_combatant(
        db,
        encounter_id=encounter_id,
        name=body.name,
        initiative_modifier=body.initiative_modifier,
        is_enemy=body.is_enemy,
        character_id=body.character_id,
        max_hp=body.max_hp,
        armor_class=body.armor_class,
        save_modifiers=body.save_modifiers,
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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

    try:
        c = await roll_combatant_initiative(db, combatant_id)
    except EncounterError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await db.commit()
    await db.refresh(c)
    return CombatantOut.model_validate(c)


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}/initiative",
    response_model=EncounterOut,
)
async def set_initiative_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    body: SetInitiativeBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    """Manually set a combatant's initiative roll.

    Players can set their own combatants' rolls during the preparing phase
    (for physical dice). The GM can override any combatant at any time.
    """
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    user_id = int(user["id"])
    admin = await is_guild_admin(guild_id, user)
    campaign = await _get_campaign(db, guild_id, campaign_id)
    is_gm = campaign.gm_discord_user_id == user_id

    if not admin and not is_gm:
        # Players may only set their own combatant's roll during preparing
        if enc.status != "preparing":
            raise HTTPException(
                status_code=403,
                detail="Players can only set initiative before combat begins",
            )
        # Verify the combatant belongs to the player
        combatant = next((c for c in enc.combatants if c.id == combatant_id), None)
        if combatant is None:
            raise HTTPException(status_code=404, detail="Combatant not found")
        if combatant.character_id is None:
            raise HTTPException(
                status_code=403,
                detail="You can only set initiative for your own characters",
            )
        # Check character ownership
        from grug.db.models import Character

        char = (
            await db.execute(
                select(Character).where(Character.id == combatant.character_id)
            )
        ).scalar_one_or_none()
        if char is None or char.owner_discord_user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only set initiative for your own characters",
            )

    try:
        await set_initiative_roll(db, encounter_id, combatant_id, body.initiative_roll)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

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
    await _assert_gm_or_admin(db, guild_id, campaign_id, user)

    try:
        enc = await end_encounter(db, encounter_id)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


# ── Combat actions (standard+ depth) ───────────────────────────────


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/damage",
    response_model=EncounterOut,
)
async def damage_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    body: DamageHealBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        await deal_damage(
            db,
            encounter_id,
            body.combatant_ids,
            body.amount,
            damage_type=body.damage_type,
            source=body.source,
        )
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/heal",
    response_model=EncounterOut,
)
async def heal_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    body: DamageHealBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        await heal_combatant(
            db,
            encounter_id,
            body.combatant_ids,
            body.amount,
            source=body.source,
        )
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/saving-throw",
    response_model=list[SavingThrowResult],
)
async def saving_throw_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    body: SavingThrowBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavingThrowResult]:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        results = await roll_saving_throws(
            db, encounter_id, body.combatant_ids, body.ability, body.dc
        )
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    return [
        SavingThrowResult(
            combatant_id=r.combatant_id,
            combatant_name=r.combatant_name,
            roll=r.roll,
            modifier=r.modifier,
            total=r.total,
            dc=r.dc,
            passed=r.passed,
        )
        for r in results
    ]


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}/condition",
    response_model=EncounterOut,
)
async def add_condition_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    body: ConditionBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        if body.remove:
            await remove_condition(db, encounter_id, [combatant_id], body.condition)
        else:
            await add_condition(db, encounter_id, [combatant_id], body.condition)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}/concentration",
    response_model=EncounterOut,
)
async def concentration_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    body: ConcentrationBody,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        await set_concentration(db, encounter_id, combatant_id, body.spell)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combatants/{combatant_id}/death-save",
    response_model=EncounterOut,
)
async def death_save_route(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    combatant_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EncounterOut:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        await roll_death_save(db, encounter_id, combatant_id)
    except EncounterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    enc = await _get_encounter_or_404(db, encounter_id)
    return _serialize(enc)


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/encounters/{encounter_id}/combat-log",
    response_model=list[CombatLogEntryOut],
)
async def get_combat_log(
    guild_id: int,
    campaign_id: int,
    encounter_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CombatLogEntryOut]:
    await assert_guild_member(guild_id, user)
    enc = await _get_encounter_or_404(db, encounter_id)
    if enc.campaign_id != campaign_id or enc.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    result = await db.execute(
        select(CombatLogEntry)
        .where(CombatLogEntry.encounter_id == encounter_id)
        .order_by(CombatLogEntry.created_at.desc())
        .limit(100)
    )
    return [CombatLogEntryOut.model_validate(e) for e in result.scalars().all()]
