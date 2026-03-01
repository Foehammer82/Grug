"""Document routes — list and delete indexed documents."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_guild_member, get_current_user, get_db
from api.schemas import DocumentOut
from grug.db.models import Document

router = APIRouter(tags=["documents"])


@router.get("/api/guilds/{guild_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    """List all indexed documents for a guild."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(Document)
        .where(Document.guild_id == guild_id)
        .order_by(Document.created_at)
    )
    return list(result.scalars().all())


@router.delete("/api/guilds/{guild_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    guild_id: int,
    doc_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an indexed document."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.guild_id == guild_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()
