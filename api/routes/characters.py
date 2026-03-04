"""Character routes — guild-scoped character CRUD and Pathbuilder integration."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
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
    CharacterOut,
    CharacterUpdate,
    PathbuilderLinkRequest,
    SyncPathbuilderRequest,
)
from grug.character.pathbuilder import (
    PathbuilderError,
    fetch_pathbuilder_character,
    parse_pathbuilder_response,
)
from grug.db.models import Campaign, Character, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["characters"])


# --------------------------------------------------------------------------- #
# List characters for the current user in a guild                              #
# --------------------------------------------------------------------------- #


@router.get(
    "/api/guilds/{guild_id}/characters",
    response_model=list[CharacterOut],
)
async def list_guild_characters(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Character]:
    """List characters visible to the current user in a guild.

    Returns all characters whose campaign belongs to this guild,
    owned by any guild member.  Non-admins only see their own characters.
    """
    assert_guild_member(guild_id, user)
    user_id = int(user["id"])
    is_admin = False
    try:
        await assert_guild_admin(guild_id, user)
        is_admin = True
    except HTTPException:
        pass

    # Find campaign IDs for this guild
    campaign_stmt = select(Campaign.id).where(Campaign.guild_id == guild_id)
    campaign_result = await db.execute(campaign_stmt)
    campaign_ids = [row[0] for row in campaign_result.all()]

    # Build character query
    if is_admin:
        # Admins see all characters linked to guild campaigns
        if campaign_ids:
            stmt = (
                select(Character)
                .where(Character.campaign_id.in_(campaign_ids))
                .order_by(Character.name)
            )
        else:
            # No campaigns — return empty or only user's unlinked characters
            stmt = (
                select(Character)
                .where(
                    Character.owner_discord_user_id == user_id,
                    Character.campaign_id.is_(None),
                )
                .order_by(Character.name)
            )
    else:
        # Non-admins see only their own characters in guild campaigns
        if campaign_ids:
            stmt = (
                select(Character)
                .where(
                    Character.owner_discord_user_id == user_id,
                    Character.campaign_id.in_(campaign_ids),
                )
                .order_by(Character.name)
            )
        else:
            return []

    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Get single character                                                         #
# --------------------------------------------------------------------------- #


@router.get(
    "/api/guilds/{guild_id}/characters/{character_id}",
    response_model=CharacterOut,
)
async def get_character(
    guild_id: int,
    character_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Get a single character by ID."""
    assert_guild_member(guild_id, user)
    character = await get_or_404(
        db, Character, Character.id == character_id, detail="Character not found"
    )
    # Verify the character belongs to a campaign in this guild or is owned by user
    if character.campaign_id:
        campaign = await db.get(Campaign, character.campaign_id)
        if not campaign or campaign.guild_id != guild_id:
            raise HTTPException(status_code=404, detail="Character not found")
    else:
        # Unlinked character — only owner can view
        if character.owner_discord_user_id != int(user["id"]):
            raise HTTPException(status_code=404, detail="Character not found")
    return character


# --------------------------------------------------------------------------- #
# Update character                                                             #
# --------------------------------------------------------------------------- #


@router.patch(
    "/api/guilds/{guild_id}/characters/{character_id}",
    response_model=CharacterOut,
)
async def update_character(
    guild_id: int,
    character_id: int,
    body: CharacterUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Update a character's name, system, or campaign assignment."""
    assert_guild_member(guild_id, user)
    character = await get_or_404(
        db, Character, Character.id == character_id, detail="Character not found"
    )
    # Only owner or guild admin can update
    user_id = int(user["id"])
    if character.owner_discord_user_id != user_id:
        await assert_guild_admin(guild_id, user)

    if "name" in body.model_fields_set:
        character.name = body.name  # type: ignore[assignment]
    if "system" in body.model_fields_set:
        character.system = body.system  # type: ignore[assignment]
    if "campaign_id" in body.model_fields_set:
        if body.campaign_id is not None:
            # Verify campaign belongs to this guild
            await get_or_404(
                db,
                Campaign,
                Campaign.id == body.campaign_id,
                Campaign.guild_id == guild_id,
                detail="Campaign not found in this guild",
            )
        character.campaign_id = body.campaign_id  # type: ignore[assignment]

    await db.commit()
    await db.refresh(character)
    return character


# --------------------------------------------------------------------------- #
# Delete character                                                             #
# --------------------------------------------------------------------------- #


@router.delete(
    "/api/guilds/{guild_id}/characters/{character_id}",
    status_code=204,
)
async def delete_character(
    guild_id: int,
    character_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a character.  Only the owner or a guild admin can delete."""
    assert_guild_member(guild_id, user)
    character = await get_or_404(
        db, Character, Character.id == character_id, detail="Character not found"
    )
    user_id = int(user["id"])
    if character.owner_discord_user_id != user_id:
        await assert_guild_admin(guild_id, user)
    await db.delete(character)
    await db.commit()


# --------------------------------------------------------------------------- #
# Set active character                                                         #
# --------------------------------------------------------------------------- #


@router.post(
    "/api/guilds/{guild_id}/characters/{character_id}/set-active",
    response_model=CharacterOut,
)
async def set_active_character(
    guild_id: int,
    character_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Set a character as the user's active character."""
    assert_guild_member(guild_id, user)
    character = await get_or_404(
        db, Character, Character.id == character_id, detail="Character not found"
    )
    user_id = int(user["id"])
    if character.owner_discord_user_id != user_id:
        raise HTTPException(
            status_code=403, detail="You can only set your own character as active"
        )

    # Get or create user profile
    result = await db.execute(
        select(UserProfile).where(UserProfile.discord_user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(
            discord_user_id=user_id,
            active_character_id=character.id,
        )
        db.add(profile)
    else:
        profile.active_character_id = character.id
    await db.commit()
    return character


# --------------------------------------------------------------------------- #
# Pathbuilder integration                                                      #
# --------------------------------------------------------------------------- #


@router.post(
    "/api/guilds/{guild_id}/characters/link-pathbuilder",
    response_model=CharacterOut,
    status_code=201,
)
async def link_pathbuilder(
    guild_id: int,
    body: PathbuilderLinkRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Create a new character by fetching data from Pathbuilder 2e.

    Fetches the character build from the public Pathbuilder endpoint,
    normalises it into structured_data, and creates a new Character record
    linked to the current user.
    """
    assert_guild_member(guild_id, user)
    user_id = int(user["id"])

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

    char_name = structured_data.get("name") or f"Pathbuilder #{body.pathbuilder_id}"

    character = Character(
        owner_discord_user_id=user_id,
        name=char_name,
        system="pf2e",
        structured_data=structured_data,
        pathbuilder_id=body.pathbuilder_id,
        pathbuilder_synced_at=datetime.now(timezone.utc),
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.post(
    "/api/guilds/{guild_id}/characters/{character_id}/sync-pathbuilder",
    response_model=CharacterOut,
)
async def sync_pathbuilder(
    guild_id: int,
    character_id: int,
    body: SyncPathbuilderRequest = Body(default_factory=SyncPathbuilderRequest),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    """Re-sync a character's data from Pathbuilder.

    Pass ``pathbuilder_data`` in the request body (pre-fetched client-side in
    the browser, which bypasses Cloudflare bot protection) to avoid a
    server-side HTTP request.  Falls back to a server-side fetch when omitted.
    Only works for characters that have a pathbuilder_id set.
    """
    assert_guild_member(guild_id, user)
    character = await get_or_404(
        db, Character, Character.id == character_id, detail="Character not found"
    )

    if not character.pathbuilder_id:
        raise HTTPException(
            status_code=400,
            detail="This character is not linked to Pathbuilder",
        )

    # When client provides pre-fetched data, skip the cooldown check so the
    # user always gets fresh data on an explicit sync action.
    if body.pathbuilder_data is not None:
        try:
            structured_data = parse_pathbuilder_response(
                body.pathbuilder_data, character.pathbuilder_id
            )
        except PathbuilderError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        # 5-minute global cooldown — return current data if synced too recently.
        _cooldown = timedelta(minutes=5)
        if (
            character.pathbuilder_synced_at is not None
            and (datetime.now(timezone.utc) - character.pathbuilder_synced_at)
            < _cooldown
        ):
            return character

        try:
            structured_data = await fetch_pathbuilder_character(
                character.pathbuilder_id
            )
        except PathbuilderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    character.structured_data = structured_data  # type: ignore[assignment]
    # Update name if it changed in Pathbuilder
    new_name = structured_data.get("name")
    if new_name:
        character.name = new_name  # type: ignore[assignment]
    character.system = "pf2e"  # type: ignore[assignment]
    character.pathbuilder_synced_at = datetime.now(timezone.utc)  # type: ignore[assignment]

    await db.commit()
    await db.refresh(character)
    return character
