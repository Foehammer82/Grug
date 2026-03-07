"""Campaign routes — CRUD for guild-specific campaigns and their characters."""

import hashlib
import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_current_user,
    get_db,
    get_or_404,
    is_guild_admin,
)
from api.schemas import (
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    CharacterCopyRequest,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    DocumentChunk,
    DocumentOut,
    DocumentSearchRequest,
    DocumentSearchResult,
    DocumentUpdate,
    PathbuilderLinkRequest,
)
from grug.character.indexer import CharacterIndexer
from grug.character.parser import CharacterSheetParser
from grug.character.pathbuilder import (
    PathbuilderError,
    fetch_pathbuilder_character,
    parse_pathbuilder_response,
)
from grug.config.settings import get_settings
from grug.db.models import Campaign, Character, Document

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

_ALLOWED_DOC_EXTENSIONS = {".txt", ".md", ".rst", ".pdf"}
_MAX_DOC_SIZE_MB = 10

# Lazy singleton for document indexer — avoids loading heavy ML deps at import time.
_doc_indexer = None


def _get_doc_indexer():
    global _doc_indexer
    if _doc_indexer is None:
        from grug.rag.indexer import DocumentIndexer

        _doc_indexer = DocumentIndexer()
    return _doc_indexer


@router.get("/api/guilds/{guild_id}/campaigns", response_model=list[CampaignOut])
async def list_campaigns(
    guild_id: int,
    include_deleted: bool = False,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignOut]:
    """List campaigns for a guild.

    Admins see all non-deleted campaigns by default; pass ``include_deleted=true``
    to also include soft-deleted campaigns.  Non-admin members see only campaigns
    that contain at least one of their own characters (deleted campaigns excluded).
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)

    stmt = (
        select(Campaign)
        .where(Campaign.guild_id == guild_id)
        .order_by(Campaign.name)
        .options(selectinload(Campaign.characters))
    )

    if admin and include_deleted:
        # Return everything — active and soft-deleted.
        pass
    elif admin:
        stmt = stmt.where(Campaign.deleted_at.is_(None))
    else:
        # Non-admin: only non-deleted campaigns where they own at least one character.
        user_id = int(user["id"])
        stmt = (
            stmt.where(Campaign.deleted_at.is_(None))
            .join(Character, Character.campaign_id == Campaign.id)
            .where(Character.owner_discord_user_id == user_id)
            .distinct()
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
            gm_discord_user_id=c.gm_discord_user_id,
            schedule_mode=c.schedule_mode,
            combat_tracker_depth=c.combat_tracker_depth,
            banking_enabled=c.banking_enabled,
            player_banking_enabled=c.player_banking_enabled,
            allow_manual_dice_recording=c.allow_manual_dice_recording,
            llm_model=c.llm_model,
            party_gold=float(c.party_gold),
            created_by=c.created_by,
            created_at=c.created_at,
            deleted_at=c.deleted_at,
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
        gm_discord_user_id=int(body.gm_discord_user_id)
        if body.gm_discord_user_id
        else None,
        schedule_mode=body.schedule_mode,
        combat_tracker_depth=body.combat_tracker_depth,
        banking_enabled=body.banking_enabled,
        player_banking_enabled=body.player_banking_enabled,
        llm_model=body.llm_model,
        created_by=int(user["id"]),
        created_at=datetime.now(timezone.utc),
    )
    db.add(campaign)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A campaign already exists for this channel.",
        )
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
    # Fetch before auth so we can check GM ownership.
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    admin = await is_guild_admin(guild_id, user)
    is_campaign_gm = campaign.gm_discord_user_id is not None and str(
        campaign.gm_discord_user_id
    ) == str(user["id"])
    if not admin and not is_campaign_gm:
        raise HTTPException(
            status_code=403,
            detail="Only guild admins or the campaign GM may edit this campaign.",
        )
    if "name" in body.model_fields_set:
        campaign.name = body.name  # type: ignore[assignment]
    if "system" in body.model_fields_set:
        campaign.system = body.system  # type: ignore[assignment]
    if "is_active" in body.model_fields_set:
        campaign.is_active = body.is_active  # type: ignore[assignment]
    if "channel_id" in body.model_fields_set:
        campaign.channel_id = int(body.channel_id)  # type: ignore[assignment]
    if "gm_discord_user_id" in body.model_fields_set:
        campaign.gm_discord_user_id = (  # type: ignore[assignment]
            int(body.gm_discord_user_id) if body.gm_discord_user_id else None
        )
    if "banking_enabled" in body.model_fields_set:
        campaign.banking_enabled = body.banking_enabled  # type: ignore[assignment]
    if "player_banking_enabled" in body.model_fields_set:
        campaign.player_banking_enabled = body.player_banking_enabled  # type: ignore[assignment]
    if "schedule_mode" in body.model_fields_set:
        campaign.schedule_mode = body.schedule_mode  # type: ignore[assignment]
    if "combat_tracker_depth" in body.model_fields_set:
        campaign.combat_tracker_depth = body.combat_tracker_depth  # type: ignore[assignment]
    if "allow_manual_dice_recording" in body.model_fields_set:
        campaign.allow_manual_dice_recording = body.allow_manual_dice_recording  # type: ignore[assignment]
    if "llm_model" in body.model_fields_set:
        campaign.llm_model = body.llm_model  # type: ignore[assignment]
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
    """Soft-delete a campaign.  Sets deleted_at; the campaign can be restored later."""
    await assert_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    campaign.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    await db.commit()


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/restore",
    response_model=CampaignOut,
)
async def restore_campaign(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Campaign:
    """Restore a soft-deleted campaign, clearing its deleted_at timestamp."""
    await assert_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    campaign.deleted_at = None  # type: ignore[assignment]
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.delete(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/permanent",
    status_code=204,
)
async def permanently_delete_campaign(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently and irreversibly delete a campaign and all its characters."""
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
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    user_id = int(user["id"])
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
    characters = list(result.scalars().all())
    # Redact private notes for characters the caller does not own (unless admin).
    if not admin:
        for ch in characters:
            if ch.owner_discord_user_id != user_id:
                ch.notes = None  # type: ignore[assignment]
    return characters


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
    """Create a character and link it to a campaign.

    Any guild member can create a character (owned by themselves).  Admins
    may optionally specify ``owner_discord_user_id`` and/or
    ``owner_display_name`` to create characters for other users or NPCs.
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    user_id = int(user["id"])
    if admin:
        owner_id = (
            body.owner_discord_user_id
            if body.owner_discord_user_id is not None
            else user_id
        )
        owner_name = body.owner_display_name
    else:
        owner_id = user_id
        owner_name = None
    character = Character(
        owner_discord_user_id=owner_id,
        owner_display_name=owner_name,
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
    """Update a character’s name, system, notes, or owner.

    Guild members can update their own characters (name, system, notes).
    Admins can update any character and may also reassign the owner.
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    user_id = int(user["id"])
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
    is_owner = character.owner_discord_user_id == user_id
    if not admin and not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Only the character owner or a guild admin can edit this character",
        )
    # Fields any owner can change
    if "name" in body.model_fields_set:
        character.name = body.name  # type: ignore[assignment]
    if "system" in body.model_fields_set:
        character.system = body.system  # type: ignore[assignment]
    if "notes" in body.model_fields_set:
        character.notes = body.notes  # type: ignore[assignment]
    # Owner-reassignment and campaign transfer are admin-only
    if admin:
        if "owner_discord_user_id" in body.model_fields_set:
            character.owner_discord_user_id = body.owner_discord_user_id  # type: ignore[assignment]
        if "owner_display_name" in body.model_fields_set:
            character.owner_display_name = body.owner_display_name  # type: ignore[assignment]
        if "campaign_id" in body.model_fields_set:
            character.campaign_id = body.campaign_id  # type: ignore[assignment]
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
    """Remove a character from a campaign (deletes the character record).

    The character owner or any guild admin may delete the character.
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    user_id = int(user["id"])
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
    is_owner = character.owner_discord_user_id == user_id
    if not admin and not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Only the character owner or a guild admin can delete this character",
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
    # Uploading a file supersedes any Pathbuilder link — clear pathbuilder_id.
    character.pathbuilder_id = None  # type: ignore[assignment]
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


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters/{character_id}/copy",
    response_model=CharacterOut,
    status_code=201,
)
async def copy_campaign_character(
    guild_id: int,
    campaign_id: int,
    character_id: int,
    body: CharacterCopyRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Deep-copy a character to a different campaign in the same guild.

    All fields (name, system, raw sheet text, structured data, Pathbuilder ID,
    file path) are duplicated onto a new row.  The copy is owned by the same
    Discord user and lands in the target campaign.
    """
    await assert_guild_admin(guild_id, user)
    # Verify source campaign belongs to this guild
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Source campaign not found",
    )
    # Verify target campaign also belongs to this guild
    await get_or_404(
        db,
        Campaign,
        Campaign.id == body.target_campaign_id,
        Campaign.guild_id == guild_id,
        detail="Target campaign not found",
    )
    source = await get_or_404(
        db,
        Character,
        Character.id == character_id,
        Character.campaign_id == campaign_id,
        detail="Character not found",
    )
    char_copy = Character(
        owner_discord_user_id=source.owner_discord_user_id,
        campaign_id=body.target_campaign_id,
        name=source.name,
        system=source.system,
        raw_sheet_text=source.raw_sheet_text,
        structured_data=source.structured_data,
        pathbuilder_id=source.pathbuilder_id,
        file_path=source.file_path,
    )
    db.add(char_copy)
    await db.commit()
    await db.refresh(char_copy)
    return char_copy


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/characters/{character_id}/link-pathbuilder",
    response_model=CharacterOut,
)
async def link_campaign_character_pathbuilder(
    guild_id: int,
    campaign_id: int,
    character_id: int,
    body: PathbuilderLinkRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Link an existing campaign character to a Pathbuilder 2e character.

    Fetches the build from the public Pathbuilder endpoint, updates the
    character's structured_data, name, and system.  Clears any previously
    uploaded file path — one sheet source per character.
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

    try:
        if body.pathbuilder_data is not None:
            # Client pre-fetched the data (bypasses Cloudflare bot protection).
            structured_data = parse_pathbuilder_response(
                body.pathbuilder_data, body.pathbuilder_id
            )
        else:
            structured_data = await fetch_pathbuilder_character(body.pathbuilder_id)
    except PathbuilderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    character.structured_data = structured_data  # type: ignore[assignment]
    char_name = structured_data.get("name") or character.name
    character.name = char_name  # type: ignore[assignment]
    character.system = "pf2e"  # type: ignore[assignment]
    character.pathbuilder_id = body.pathbuilder_id  # type: ignore[assignment]
    character.pathbuilder_synced_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    # Linking Pathbuilder supersedes any uploaded file — clear file reference.
    character.file_path = None  # type: ignore[assignment]
    character.raw_sheet_text = None  # type: ignore[assignment]

    await db.commit()
    await db.refresh(character)
    return character


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/sync-pathbuilder",
)
async def sync_campaign_pathbuilder(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sync Pathbuilder data for all linked characters in a campaign.

    Each character respects its own 5-minute cooldown; stale characters
    are fetched from the Pathbuilder API and updated.  Returns a summary
    with counts of synced and skipped characters.
    """
    await assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )

    result = await db.execute(
        select(Character).where(
            Character.campaign_id == campaign_id,
            Character.pathbuilder_id.is_not(None),
        )
    )
    characters = result.scalars().all()

    cooldown = timedelta(minutes=5)
    now = datetime.now(timezone.utc)
    synced = 0
    skipped = 0
    errors = 0

    for character in characters:
        if (
            character.pathbuilder_synced_at is not None
            and (now - character.pathbuilder_synced_at) < cooldown
        ):
            skipped += 1
            continue
        try:
            structured_data = await fetch_pathbuilder_character(
                character.pathbuilder_id
            )  # type: ignore[arg-type]
            character.structured_data = structured_data  # type: ignore[assignment]
            new_name = structured_data.get("name")
            if new_name:
                character.name = new_name  # type: ignore[assignment]
            character.system = "pf2e"  # type: ignore[assignment]
            character.pathbuilder_synced_at = now  # type: ignore[assignment]
            synced += 1
        except Exception:
            logger.exception(
                "Failed to sync character %d from Pathbuilder", character.id
            )
            errors += 1

    await db.commit()
    return {"synced": synced, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Passive checks
# ---------------------------------------------------------------------------


@router.post("/api/guilds/{guild_id}/campaigns/{campaign_id}/passives")
async def check_passives(
    guild_id: int,
    campaign_id: int,
    body: dict,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Compute passive skill scores for every character in the campaign.

    **GM / admin only** — prevents leaking hidden check info to players.

    Request body::

        { "skill": "perception", "dc": 15 }   // dc is optional

    Returns a list of ``{ name, owner_discord_user_id, score, pass }`` dicts.
    ``score`` is ``null`` when the character lacks sufficient sheet data.
    ``pass`` is ``null`` when no DC is provided, otherwise ``true``/``false``.
    """
    from grug.character.passives import compute_passive_score, normalize_skill_key

    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)

    campaign = await get_or_404(
        db, Campaign, Campaign.id == campaign_id, Campaign.guild_id == guild_id
    )
    is_gm = str(campaign.gm_discord_user_id) == str(user["id"])
    if not admin and not is_gm:
        raise HTTPException(
            status_code=403, detail="Only the GM or an admin can check passive scores."
        )

    skill: str = normalize_skill_key(body.get("skill") or "perception")
    dc: int | None = body.get("dc")

    chars = (
        (
            await db.execute(
                select(Character).where(Character.campaign_id == campaign_id)
            )
        )
        .scalars()
        .all()
    )

    results: list[dict[str, Any]] = []
    for c in chars:
        sd = c.structured_data or {}
        score = compute_passive_score(sd, skill)
        passed: bool | None = None
        if dc is not None and score is not None:
            passed = score >= dc
        results.append(
            {
                "name": c.name,
                "owner_discord_user_id": str(c.owner_discord_user_id)
                if c.owner_discord_user_id
                else None,
                "score": score,
                "pass": passed,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Campaign document routes
# ---------------------------------------------------------------------------
# Documents are now campaign-scoped resources.  The GM or any guild admin can
# upload, edit, and delete documents for their campaign.  Guild members can
# list and search (read-only).
# ---------------------------------------------------------------------------


def _assert_gm_or_admin(is_admin: bool, campaign: Campaign, user: dict) -> None:
    """Raise 403 unless the user is a guild admin or the campaign's GM."""
    is_gm = campaign.gm_discord_user_id is not None and str(
        campaign.gm_discord_user_id
    ) == str(user["id"])
    if not is_admin and not is_gm:
        raise HTTPException(
            status_code=403,
            detail="Only guild admins or the campaign GM may manage documents.",
        )


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/documents",
    response_model=list[DocumentOut],
)
async def list_campaign_documents(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    """List documents for a campaign.

    GMs and guild admins see all documents (public and private).
    Regular campaign members only see documents marked ``is_public=True``.
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    is_gm = campaign.gm_discord_user_id is not None and str(
        campaign.gm_discord_user_id
    ) == str(user["id"])

    stmt = select(Document).where(
        Document.guild_id == guild_id,
        Document.campaign_id == campaign_id,
    )
    # Non-GM, non-admin users only see public documents.
    if not admin and not is_gm:
        stmt = stmt.where(Document.is_public.is_(True))

    result = await db.execute(stmt.order_by(Document.created_at))
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/documents",
    response_model=DocumentOut,
    status_code=201,
)
async def upload_campaign_document(
    guild_id: int,
    campaign_id: int,
    file: UploadFile,
    description: str = Form(""),
    is_public: bool = Form(False),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Upload and index a document for a campaign (GM or admin only).

    Documents are private by default (``is_public=False``).  Set
    ``is_public=True`` to make the document visible to all campaign
    members and include it in Grug's player-facing searches.
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _assert_gm_or_admin(admin, campaign, user)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_DOC_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_DOC_EXTENSIONS))}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > _MAX_DOC_SIZE_MB:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds {_MAX_DOC_SIZE_MB} MB limit.",
        )

    content_hash = hashlib.sha256(contents).hexdigest()

    # Reject duplicate content within the same campaign.
    existing = await db.execute(
        select(Document).where(
            Document.campaign_id == campaign_id,
            Document.content_hash == content_hash,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="A document with identical content has already been uploaded to this campaign.",
        )

    safe_filename = Path(file.filename or "upload").name or "upload"
    uploader_id = int(user["id"])

    doc = Document(
        guild_id=guild_id,
        campaign_id=campaign_id,
        filename=safe_filename,
        description=description or None,
        chroma_collection=f"guild_{guild_id}",
        chunk_count=0,
        uploaded_by=uploader_id,
        content_hash=content_hash,
        is_public=is_public,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Persist raw file to disk so it can be served/downloaded later.
    settings = get_settings()
    doc_dir = Path(settings.file_data_dir) / "campaigns" / str(campaign_id) / "docs"
    doc_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{doc.id}_{safe_filename}"
    stored_path = doc_dir / stored_name
    stored_path.write_bytes(contents)
    # Store path relative to file_data_dir for portability.
    doc.file_path = str(Path("campaigns") / str(campaign_id) / "docs" / stored_name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / safe_filename
        tmp_path.write_bytes(contents)
        chunk_count = await _get_doc_indexer().index_file(
            guild_id=guild_id,
            file_path=tmp_path,
            document_id=doc.id,
            description=description or None,
        )

    doc.chunk_count = chunk_count
    await db.commit()
    await db.refresh(doc)
    return doc


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/documents/{doc_id}",
    response_model=DocumentOut,
)
async def update_campaign_document(
    guild_id: int,
    campaign_id: int,
    doc_id: int,
    body: DocumentUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Update a campaign document's description (GM or admin only)."""
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _assert_gm_or_admin(admin, campaign, user)
    doc = await get_or_404(
        db,
        Document,
        Document.id == doc_id,
        Document.campaign_id == campaign_id,
        detail="Document not found",
    )
    if "description" in body.model_fields_set:
        doc.description = body.description
    if "is_public" in body.model_fields_set and body.is_public is not None:
        doc.is_public = body.is_public
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/documents/{doc_id}",
    status_code=204,
)
async def delete_campaign_document(
    guild_id: int,
    campaign_id: int,
    doc_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a campaign document and its indexed chunks (GM or admin only)."""
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _assert_gm_or_admin(admin, campaign, user)
    doc = await get_or_404(
        db,
        Document,
        Document.id == doc_id,
        Document.campaign_id == campaign_id,
        detail="Document not found",
    )
    # Remove persisted raw file from disk if it exists.
    if doc.file_path:
        settings = get_settings()
        full_path = Path(settings.file_data_dir) / doc.file_path
        try:
            full_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete document file at %s", full_path)
    await _get_doc_indexer().delete_document(guild_id, doc_id)
    await db.delete(doc)
    await db.commit()


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/documents/{doc_id}/download",
)
async def download_campaign_document(
    guild_id: int,
    campaign_id: int,
    doc_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the raw file for a campaign document.

    GMs and guild admins can download any document.
    Regular members can only download documents where ``is_public=True``.
    Returns 404 if the raw file was not persisted (legacy document).
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    is_gm = campaign.gm_discord_user_id is not None and str(
        campaign.gm_discord_user_id
    ) == str(user["id"])

    doc = await get_or_404(
        db,
        Document,
        Document.id == doc_id,
        Document.campaign_id == campaign_id,
        detail="Document not found",
    )

    # Non-GM/non-admin users can only download public documents.
    if not admin and not is_gm and not doc.is_public:
        raise HTTPException(status_code=403, detail="This document is private.")

    if not doc.file_path:
        raise HTTPException(
            status_code=404,
            detail="Raw file not available for this document.",
        )

    settings = get_settings()
    full_path = Path(settings.file_data_dir) / doc.file_path
    if not full_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found on server.",
        )

    return FileResponse(
        path=str(full_path),
        filename=doc.filename,
        media_type="application/octet-stream",
    )


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/documents/search",
    response_model=DocumentSearchResult,
)
async def search_campaign_documents(
    guild_id: int,
    campaign_id: int,
    body: DocumentSearchRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentSearchResult:
    """Run a live RAG search against a campaign's indexed documents (GM or admin only).

    Returns the top-k matching chunks with similarity scores so GMs can verify
    that a document has been indexed correctly and is retrievable.
    """
    await assert_guild_member(guild_id, user)
    admin = await is_guild_admin(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _assert_gm_or_admin(admin, campaign, user)

    from grug.rag.retriever import DocumentRetriever

    try:
        retriever = DocumentRetriever()
        raw = await retriever.search(
            guild_id,
            body.query,
            k=body.k,
            document_id=body.document_id,
            campaign_id=campaign_id,
        )
        chunks = [
            DocumentChunk(
                text=c["text"],
                filename=c["filename"],
                chunk_index=c["chunk_index"],
                distance=round(float(c.get("distance", 0.0)), 4),
            )
            for c in raw
        ]
        return DocumentSearchResult(chunks=chunks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Campaign document search failed: %s", exc)
        return DocumentSearchResult(chunks=[], error=True)
