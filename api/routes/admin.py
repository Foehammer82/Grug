"""Admin routes — manage GrugUser privileges and generate invite URLs.

All endpoints require Grug super-admin status except ``GET /api/invite-url``
which also allows users with the ``can_invite`` privilege.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_can_invite,
    assert_super_admin,
    get_bot_token,
    get_current_user,
    get_db,
)
from api.schemas import (
    DiscordMemberOut,
    DiscordUserOut,
    GrugUserOut,
    GrugUserUpdate,
    InviteUrlOut,
)
from grug.config.settings import get_settings
from grug.db.models import GrugUser, GuildConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# Discord bot permissions needed:
#   MANAGE_ROLES (0x10000000) = 268435456
#   SEND_MESSAGES (0x800) = 2048
#   EMBED_LINKS (0x4000) = 16384
#   READ_MESSAGE_HISTORY (0x10000) = 65536
#   USE_APPLICATION_COMMANDS (0x80000000) = 2147483648
#   ADD_REACTIONS (0x40) = 64
#   VIEW_CHANNEL (0x400) = 1024
#   ATTACH_FILES (0x8000) = 32768
_BOT_PERMISSIONS = (
    268435456  # MANAGE_ROLES
    | 2048  # SEND_MESSAGES
    | 16384  # EMBED_LINKS
    | 65536  # READ_MESSAGE_HISTORY
    | 2147483648  # USE_APPLICATION_COMMANDS
    | 64  # ADD_REACTIONS
    | 1024  # VIEW_CHANNEL
    | 32768  # ATTACH_FILES
)


# --------------------------------------------------------------------------- #
# Invite URL                                                                   #
# --------------------------------------------------------------------------- #


@router.get("/api/invite-url", response_model=InviteUrlOut)
async def get_invite_url(
    user: dict[str, Any] = Depends(get_current_user),
) -> InviteUrlOut:
    """Return the bot invite URL. Requires super-admin or can_invite privilege."""
    await assert_can_invite(user)
    settings = get_settings()
    if not settings.discord_client_id:
        raise HTTPException(status_code=503, detail="Discord client ID not configured")

    url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={settings.discord_client_id}"
        f"&permissions={_BOT_PERMISSIONS}"
        f"&scope={quote('bot applications.commands')}"
    )
    return InviteUrlOut(url=url)


# --------------------------------------------------------------------------- #
# Member search (super-admin only)                                             #
# --------------------------------------------------------------------------- #


@router.get("/api/admin/users/search", response_model=list[DiscordMemberOut])
async def search_discord_members(
    q: str = Query(min_length=1),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscordMemberOut]:
    """Search Discord members across all guilds the bot is joined to.

    Uses the Discord REST member-search endpoint which requires the
    GUILD_MEMBERS privileged intent to be enabled for the application.
    Results are deduplicated by user ID across all guilds.
    """
    await assert_super_admin(user)
    bot_token = get_bot_token()

    # Gather all guild IDs the bot is present in
    guild_result = await db.execute(select(GuildConfig.guild_id))
    guild_ids: list[int] = [row[0] for row in guild_result.all()]

    if not guild_ids:
        return []

    seen: set[str] = set()
    members: list[DiscordMemberOut] = []

    async def _search_guild(guild_id: int) -> list[DiscordMemberOut]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(
                    f"https://discord.com/api/v10/guilds/{guild_id}/members/search",
                    headers={"Authorization": f"Bot {bot_token}"},
                    params={"query": q, "limit": 25},
                )
            if resp.status_code != 200:
                logger.debug(
                    "Member search for guild %s returned %s", guild_id, resp.status_code
                )
                return []
            results: list[DiscordMemberOut] = []
            for m in resp.json():
                u = m.get("user", {})
                uid = u.get("id")
                if not uid:
                    continue
                avatar_hash = m.get("avatar") or u.get("avatar")
                if avatar_hash:
                    # Use guild avatar if present, else user avatar
                    if m.get("avatar"):
                        avatar_url = (
                            f"https://cdn.discordapp.com/guilds/{guild_id}"
                            f"/users/{uid}/avatars/{avatar_hash}.png"
                        )
                    else:
                        avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png"
                else:
                    avatar_url = None
                display_name = (
                    m.get("nick") or u.get("global_name") or u.get("username", uid)
                )
                results.append(
                    DiscordMemberOut(
                        discord_user_id=uid,
                        username=u.get("username", uid),
                        display_name=display_name,
                        avatar_url=avatar_url,
                    )
                )
            return results
        except Exception:
            logger.warning("Member search failed for guild %s", guild_id, exc_info=True)
            return []

    all_results = await asyncio.gather(*[_search_guild(gid) for gid in guild_ids])
    for guild_members in all_results:
        for m in guild_members:
            if m.discord_user_id not in seen:
                seen.add(m.discord_user_id)
                members.append(m)

    return members


# --------------------------------------------------------------------------- #
# User management (super-admin only)                                           #
# --------------------------------------------------------------------------- #


@router.get("/api/admin/users", response_model=list[GrugUserOut])
async def list_grug_users(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GrugUserOut]:
    """List all GrugUser records. Super-admin only."""
    await assert_super_admin(user)
    settings = get_settings()

    result = await db.execute(select(GrugUser).order_by(GrugUser.created_at))
    rows = result.scalars().all()

    # Build output, enriching with super-admin flag from env var OR DB column
    existing_ids: set[str] = set()
    out: list[GrugUserOut] = []
    for r in rows:
        uid = str(r.discord_user_id)
        existing_ids.add(uid)
        out.append(
            GrugUserOut(
                discord_user_id=uid,
                can_invite=r.can_invite,
                is_super_admin=(uid in settings.grug_super_admin_ids)
                or r.is_super_admin,
                is_env_super_admin=uid in settings.grug_super_admin_ids,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )

    # Also include env-var super-admins who don't have a DB row yet
    now = datetime.now(timezone.utc)
    for sa_id in settings.grug_super_admin_ids:
        if sa_id not in existing_ids:
            out.append(
                GrugUserOut(
                    discord_user_id=sa_id,
                    can_invite=True,  # super-admins implicitly can invite
                    is_super_admin=True,
                    is_env_super_admin=True,
                    created_at=now,
                    updated_at=now,
                )
            )

    return out


@router.get("/api/admin/users/{discord_user_id}", response_model=GrugUserOut)
async def get_grug_user(
    discord_user_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrugUserOut:
    """Get a single GrugUser record. Super-admin only."""
    await assert_super_admin(user)
    settings = get_settings()

    result = await db.execute(
        select(GrugUser).where(GrugUser.discord_user_id == int(discord_user_id))
    )
    grug_user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if grug_user is None:
        # Check if it's an env-var super-admin without a DB row
        if discord_user_id in settings.grug_super_admin_ids:
            return GrugUserOut(
                discord_user_id=discord_user_id,
                can_invite=True,
                is_super_admin=True,
                is_env_super_admin=True,
                created_at=now,
                updated_at=now,
            )
        raise HTTPException(status_code=404, detail="User not found")

    return GrugUserOut(
        discord_user_id=str(grug_user.discord_user_id),
        can_invite=grug_user.can_invite,
        is_super_admin=(discord_user_id in settings.grug_super_admin_ids)
        or grug_user.is_super_admin,
        is_env_super_admin=discord_user_id in settings.grug_super_admin_ids,
        created_at=grug_user.created_at,
        updated_at=grug_user.updated_at,
    )


@router.patch("/api/admin/users/{discord_user_id}", response_model=GrugUserOut)
async def update_grug_user(
    discord_user_id: str,
    body: GrugUserUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrugUserOut:
    """Update a GrugUser (upserts if no row exists). Super-admin only."""
    await assert_super_admin(user)
    settings = get_settings()

    uid = int(discord_user_id)
    result = await db.execute(select(GrugUser).where(GrugUser.discord_user_id == uid))
    grug_user = result.scalar_one_or_none()

    if grug_user is None:
        # Upsert: create record for this user
        now = datetime.now(timezone.utc)
        grug_user = GrugUser(
            discord_user_id=uid,
            can_invite=body.can_invite if body.can_invite is not None else False,
            is_super_admin=body.is_super_admin
            if body.is_super_admin is not None
            else False,
            created_at=now,
            updated_at=now,
        )
        db.add(grug_user)
    else:
        if "can_invite" in body.model_fields_set:
            grug_user.can_invite = body.can_invite  # type: ignore[assignment]
        if "is_super_admin" in body.model_fields_set:
            grug_user.is_super_admin = body.is_super_admin  # type: ignore[assignment]
        grug_user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(grug_user)

    return GrugUserOut(
        discord_user_id=str(grug_user.discord_user_id),
        can_invite=grug_user.can_invite,
        is_super_admin=(discord_user_id in settings.grug_super_admin_ids)
        or grug_user.is_super_admin,
        is_env_super_admin=discord_user_id in settings.grug_super_admin_ids,
        created_at=grug_user.created_at,
        updated_at=grug_user.updated_at,
    )


@router.delete("/api/admin/users/{discord_user_id}", status_code=204)
async def delete_grug_user(
    discord_user_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a GrugUser record. Super-admin only."""
    await assert_super_admin(user)
    result = await db.execute(
        select(GrugUser).where(GrugUser.discord_user_id == int(discord_user_id))
    )
    grug_user = result.scalar_one_or_none()
    if grug_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(grug_user)
    await db.commit()


# --------------------------------------------------------------------------- #
# Discord user lookup (super-admin only)                                       #
# --------------------------------------------------------------------------- #


@router.get("/api/discord/users/{discord_user_id}", response_model=DiscordUserOut)
async def get_discord_user(
    discord_user_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> DiscordUserOut:
    """Resolve a Discord user ID to their profile via the bot token.

    Returns username, display name, avatar URL, and a link to their Discord
    profile page.  Super-admin only.
    """
    await assert_super_admin(user)
    bot_token = get_bot_token()

    async with httpx.AsyncClient(timeout=5.0) as http:
        resp = await http.get(
            f"https://discord.com/api/v10/users/{discord_user_id}",
            headers={"Authorization": f"Bot {bot_token}"},
        )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Discord user not found")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Discord API returned {resp.status_code}",
        )

    data = resp.json()
    uid = data["id"]
    avatar_hash = data.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png"
        if avatar_hash
        else None
    )
    return DiscordUserOut(
        discord_user_id=uid,
        username=data["username"],
        display_name=data.get("global_name") or data["username"],
        avatar_url=avatar_url,
        profile_url=f"https://discord.com/users/{uid}",
    )
