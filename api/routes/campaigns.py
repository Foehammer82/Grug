"""Campaign routes — CRUD for guild-specific campaigns and their characters."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from grug.character.indexer import CharacterIndexer
from grug.character.parser import CharacterSheetParser
from grug.config.settings import get_settings
from grug.db.models import Campaign, Character

logger = logging.getLogger(__name__)

_ALLOWED_SHEET_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".pdf",
    ".docx",
    ".doc",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
_MAX_SHEET_SIZE_MB = 20

router = APIRouter(tags=["campaigns"])


@router.get("/api/guilds/{guild_id}/campaigns", response_model=list[CampaignOut])
async def list_campaigns(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignOut]:
    """List all campaigns for a guild, including a character count."""
    await assert_guild_admin(guild_id, user)
    stmt = (
        select(Campaign)
        .where(Campaign.guild_id == guild_id)
        .order_by(Campaign.name)
        .options(selectinload(Campaign.characters))
    )
    result = await db.execute(stmt)
    campaigns = result.scalars().all()
    return [
        CampaignOut(
            id=c.id,
            guild_id=c.guild_id,
            channel_id=c.channel_id,
            name=c.name,
            system=c.system,
            is_active=c.is_active,
            created_by=c.created_by,
            created_at=c.created_at,
            character_count=len(c.characters),
        )
        for c in campaigns
    ]


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


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters/{character_id}/upload",
    response_model=CharacterOut,
)
async def upload_character_sheet(
    guild_id: int,
    campaign_id: int,
    character_id: int,
    file: UploadFile,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Upload and parse a character sheet PDF/image for a campaign character.

    Mirrors the ``/character upload`` Discord bot command: parses the file with
    Claude, stores the structured data + raw text on the character record,
    saves the raw file to disk, and re-indexes the character for RAG search.
    """
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

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_SHEET_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_SHEET_EXTENSIONS))}"
            ),
        )

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > _MAX_SHEET_SIZE_MB:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds {_MAX_SHEET_SIZE_MB} MB limit.",
        )

    settings = get_settings()
    parser = CharacterSheetParser(
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_big_brain_model,
    )
    try:
        raw_text, structured_data, detected_system = await parser.parse(
            file_bytes, file.filename or "upload"
        )
    except Exception as exc:
        logger.exception(
            "Character sheet parsing failed for character %d: %s", character_id, exc
        )
        raise HTTPException(
            status_code=502, detail="Character sheet parsing failed."
        ) from exc

    character.raw_sheet_text = raw_text  # type: ignore[assignment]
    character.structured_data = structured_data  # type: ignore[assignment]
    character.system = detected_system  # type: ignore[assignment]
    await db.commit()

    # Persist the raw file so it can be re-processed later
    file_data_dir = Path(settings.file_data_dir)
    file_data_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name or "upload"
    dest = file_data_dir / f"character_{character_id}_{safe_name}"
    dest.write_bytes(file_bytes)
    character.file_path = str(dest)  # type: ignore[assignment]
    await db.commit()

    # Re-index for RAG / semantic search
    indexer = CharacterIndexer()
    await indexer.index_character(character_id, raw_text)

    await db.refresh(character)
    return character
