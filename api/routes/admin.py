"""Admin routes — manage GrugUser privileges and generate invite URLs.

All endpoints require Grug super-admin status except ``GET /api/invite-url``
which also allows users with the ``can_invite`` privilege.
"""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_can_invite,
    assert_super_admin,
    get_current_user,
    get_db,
)
from api.schemas import GrugUserOut, GrugUserUpdate, InviteUrlOut
from grug.config.settings import get_settings
from grug.db.models import GrugUser

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
# User management (super-admin only)                                           #
# --------------------------------------------------------------------------- #


@router.get("/api/admin/users", response_model=list[GrugUserOut])
async def list_grug_users(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GrugUserOut]:
    """List all GrugUser records. Super-admin only."""
    assert_super_admin(user)
    settings = get_settings()

    result = await db.execute(select(GrugUser).order_by(GrugUser.created_at))
    rows = result.scalars().all()

    # Build output, enriching with super-admin flag from env var
    existing_ids: set[str] = set()
    out: list[GrugUserOut] = []
    for r in rows:
        uid = str(r.discord_user_id)
        existing_ids.add(uid)
        out.append(
            GrugUserOut(
                discord_user_id=uid,
                can_invite=r.can_invite,
                is_super_admin=uid in settings.grug_super_admin_ids,
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
    assert_super_admin(user)
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
                created_at=now,
                updated_at=now,
            )
        raise HTTPException(status_code=404, detail="User not found")

    return GrugUserOut(
        discord_user_id=str(grug_user.discord_user_id),
        can_invite=grug_user.can_invite,
        is_super_admin=discord_user_id in settings.grug_super_admin_ids,
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
    assert_super_admin(user)
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
            created_at=now,
            updated_at=now,
        )
        db.add(grug_user)
    else:
        if "can_invite" in body.model_fields_set:
            grug_user.can_invite = body.can_invite  # type: ignore[assignment]
        grug_user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(grug_user)

    return GrugUserOut(
        discord_user_id=str(grug_user.discord_user_id),
        can_invite=grug_user.can_invite,
        is_super_admin=discord_user_id in settings.grug_super_admin_ids,
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
    assert_super_admin(user)
    result = await db.execute(
        select(GrugUser).where(GrugUser.discord_user_id == int(discord_user_id))
    )
    grug_user = result.scalar_one_or_none()
    if grug_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(grug_user)
    await db.commit()
