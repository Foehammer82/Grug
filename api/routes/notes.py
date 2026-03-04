"""Grug Notes routes — guild-scoped and personal notes.

Guild notes are visible to all members but only editable by admins.
Personal notes are visible to the owning user only.
"""

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
)
from api.schemas import GrugNoteOut, GrugNoteUpdate
from grug.db.models import GrugNote

router = APIRouter(tags=["notes"])


# --------------------------------------------------------------------------- #
# Guild notes                                                                  #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/notes", response_model=GrugNoteOut)
async def get_guild_notes(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrugNote:
    """Return the guild's Grug notes (single document per guild)."""
    await assert_guild_member(guild_id, user)
    result = await db.execute(
        select(GrugNote).where(
            GrugNote.guild_id == guild_id,
            GrugNote.user_id.is_(None),
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        note = GrugNote(guild_id=guild_id, user_id=None, content="", updated_by=0)
        db.add(note)
        await db.commit()
        await db.refresh(note)
    return note


@router.put("/api/guilds/{guild_id}/notes", response_model=GrugNoteOut)
async def update_guild_notes(
    guild_id: int,
    body: GrugNoteUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrugNote:
    """Update the guild's Grug notes (admin-only)."""
    await assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    result = await db.execute(
        select(GrugNote).where(
            GrugNote.guild_id == guild_id,
            GrugNote.user_id.is_(None),
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        note = GrugNote(
            guild_id=guild_id,
            user_id=None,
            content=body.content,
            updated_by=int(user["id"]),
        )
        db.add(note)
    else:
        note.content = body.content
        note.updated_by = int(user["id"])
        note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


# --------------------------------------------------------------------------- #
# Personal notes                                                               #
# --------------------------------------------------------------------------- #


@router.get("/api/personal/notes", response_model=GrugNoteOut)
async def get_personal_notes(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrugNote:
    """Return the current user's personal Grug notes."""
    user_id = int(user["id"])
    result = await db.execute(
        select(GrugNote).where(
            GrugNote.user_id == user_id,
            GrugNote.guild_id.is_(None),
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        note = GrugNote(guild_id=None, user_id=user_id, content="", updated_by=0)
        db.add(note)
        await db.commit()
        await db.refresh(note)
    return note


@router.put("/api/personal/notes", response_model=GrugNoteOut)
async def update_personal_notes(
    body: GrugNoteUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GrugNote:
    """Update the current user's personal Grug notes."""
    user_id = int(user["id"])
    result = await db.execute(
        select(GrugNote).where(
            GrugNote.user_id == user_id,
            GrugNote.guild_id.is_(None),
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        note = GrugNote(
            guild_id=None,
            user_id=user_id,
            content=body.content,
            updated_by=user_id,
        )
        db.add(note)
    else:
        note.content = body.content
        note.updated_by = user_id
        note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note
