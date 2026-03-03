"""Campaign routes — CRUD for guild-specific campaigns and their characters."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_current_user,
    get_db,
    get_or_404,
)
from api.schemas import (
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
)
from grug.db.models import Campaign, Character

router = APIRouter(tags=["campaigns"])


@router.get("/api/guilds/{guild_id}/campaigns", response_model=list[CampaignOut])
async def list_campaigns(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Campaign]:
    """List all campaigns for a guild."""
    await assert_guild_admin(guild_id, user)
    stmt = select(Campaign).where(Campaign.guild_id == guild_id).order_by(Campaign.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/campaigns",
    response_model=CampaignOut,
    status_code=201,
)
async def create_campaign(
    guild_id: int,
    body: CampaignCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    """Create a new campaign for a guild."""
    await assert_guild_admin(guild_id, user)
    campaign = Campaign(
        guild_id=guild_id,
        channel_id=int(body.channel_id),
        name=body.name,
        system=body.system,
        is_active=True,
        created_by=int(user["id"]),
        created_at=datetime.now(timezone.utc),
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}",
    response_model=CampaignOut,
)
async def update_campaign(
    guild_id: int,
    campaign_id: int,
    body: CampaignUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    """Update a campaign.  Only fields present in the request body are changed."""
    await assert_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    if "name" in body.model_fields_set:
        campaign.name = body.name  # type: ignore[assignment]
    if "system" in body.model_fields_set:
        campaign.system = body.system  # type: ignore[assignment]
    if "is_active" in body.model_fields_set:
        campaign.is_active = body.is_active  # type: ignore[assignment]
    if "channel_id" in body.model_fields_set:
        campaign.channel_id = int(body.channel_id)  # type: ignore[assignment]
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.delete(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}",
    status_code=204,
)
async def delete_campaign(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a campaign."""
    await assert_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    await db.delete(campaign)
    await db.commit()


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters",
    response_model=list[CharacterOut],
)
async def list_campaign_characters(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Character]:
    """List characters associated with a campaign."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    # Verify the campaign belongs to the guild
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    stmt = (
        select(Character)
        .where(Character.campaign_id == campaign_id)
        .order_by(Character.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters",
    response_model=CharacterOut,
    status_code=201,
)
async def create_campaign_character(
    guild_id: int,
    campaign_id: int,
    body: CharacterCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Create a character and link it to a campaign."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    character = Character(
        owner_discord_user_id=int(user["id"]),
        campaign_id=campaign_id,
        name=body.name,
        system=body.system,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters/{character_id}",
    response_model=CharacterOut,
)
async def update_campaign_character(
    guild_id: int,
    campaign_id: int,
    character_id: int,
    body: CharacterUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Update a character’s name or system."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    # Verify campaign ownership
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    character = await get_or_404(
        db,
        Character,
        Character.id == character_id,
        Character.campaign_id == campaign_id,
        detail="Character not found",
    )
    if "name" in body.model_fields_set:
        character.name = body.name  # type: ignore[assignment]
    if "system" in body.model_fields_set:
        character.system = body.system  # type: ignore[assignment]
    await db.commit()
    await db.refresh(character)
    return character


@router.delete(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters/{character_id}",
    status_code=204,
)
async def delete_campaign_character(
    guild_id: int,
    campaign_id: int,
    character_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a character from a campaign (deletes the character record)."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    character = await get_or_404(
        db,
        Character,
        Character.id == character_id,
        Character.campaign_id == campaign_id,
        detail="Character not found",
    )
    await db.delete(character)
    await db.commit()
