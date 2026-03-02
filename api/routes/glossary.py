"""Glossary routes — CRUD + history for guild-specific terminology."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_guild_member, get_current_user, get_db, get_or_404
from api.schemas import (
    GlossaryTermCreate,
    GlossaryTermHistoryOut,
    GlossaryTermOut,
    GlossaryTermUpdate,
)
from grug.db.models import GlossaryTerm, GlossaryTermHistory

router = APIRouter(tags=["glossary"])


@router.get("/api/guilds/{guild_id}/glossary", response_model=list[GlossaryTermOut])
async def list_glossary_terms(
    guild_id: int,
    channel_id: int | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GlossaryTerm]:
    """List glossary terms for a guild. Pass ``?channel_id=`` to scope by channel."""
    assert_guild_member(guild_id, user)
    stmt = select(GlossaryTerm).where(GlossaryTerm.guild_id == guild_id)
    if channel_id is not None:
        stmt = stmt.where(GlossaryTerm.channel_id == channel_id)
    stmt = stmt.order_by(GlossaryTerm.term)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/glossary", response_model=GlossaryTermOut, status_code=201
)
async def create_glossary_term(
    guild_id: int,
    body: GlossaryTermCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryTerm:
    """Create a human-authored glossary term."""
    assert_guild_member(guild_id, user)
    now = datetime.now(timezone.utc)
    term = GlossaryTerm(
        guild_id=guild_id,
        channel_id=body.channel_id,
        term=body.term,
        definition=body.definition,
        ai_generated=False,
        originally_ai_generated=False,
        created_by=int(user["id"]),
        updated_at=now,
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


@router.patch(
    "/api/guilds/{guild_id}/glossary/{term_id}", response_model=GlossaryTermOut
)
async def update_glossary_term(
    guild_id: int,
    term_id: int,
    body: GlossaryTermUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryTerm:
    """Update a glossary term — saves a history snapshot and clears ai_generated."""
    assert_guild_member(guild_id, user)
    term = await get_or_404(
        db,
        GlossaryTerm,
        GlossaryTerm.id == term_id,
        GlossaryTerm.guild_id == guild_id,
        detail="Glossary term not found",
    )

    # Snapshot before changing.
    history = GlossaryTermHistory(
        term_id=term.id,
        guild_id=term.guild_id,
        old_term=term.term,
        old_definition=term.definition,
        old_ai_generated=term.ai_generated,
        changed_by=int(user["id"]),
    )
    db.add(history)

    if body.term is not None:
        term.term = body.term
    if body.definition is not None:
        term.definition = body.definition
    term.ai_generated = False
    term.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(term)
    return term


@router.delete("/api/guilds/{guild_id}/glossary/{term_id}", status_code=204)
async def delete_glossary_term(
    guild_id: int,
    term_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a glossary term."""
    assert_guild_member(guild_id, user)
    term = await get_or_404(
        db,
        GlossaryTerm,
        GlossaryTerm.id == term_id,
        GlossaryTerm.guild_id == guild_id,
        detail="Glossary term not found",
    )
    await db.delete(term)
    await db.commit()


@router.get(
    "/api/guilds/{guild_id}/glossary/{term_id}/history",
    response_model=list[GlossaryTermHistoryOut],
)
async def get_glossary_term_history(
    guild_id: int,
    term_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GlossaryTermHistory]:
    """Retrieve the full change history for a glossary term."""
    assert_guild_member(guild_id, user)
    # Verify the term exists
    await get_or_404(
        db,
        GlossaryTerm,
        GlossaryTerm.id == term_id,
        GlossaryTerm.guild_id == guild_id,
        detail="Glossary term not found",
    )

    history_result = await db.execute(
        select(GlossaryTermHistory)
        .where(GlossaryTermHistory.term_id == term_id)
        .order_by(GlossaryTermHistory.changed_at.desc())
    )
    return list(history_result.scalars().all())
