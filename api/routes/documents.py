"""Document routes — list, upload, edit, and delete indexed documents."""

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
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
    DocumentOut,
    DocumentSearchRequest,
    DocumentSearchResult,
    DocumentUpdate,
)
from grug.db.models import Document
from grug.rag.indexer import DocumentIndexer

router = APIRouter(tags=["documents"])

_ALLOWED_EXTENSIONS = {".txt", ".md", ".rst", ".pdf"}
_MAX_SIZE_MB = 10
_indexer = DocumentIndexer()
logger = logging.getLogger(__name__)


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


@router.post(
    "/api/guilds/{guild_id}/documents", response_model=DocumentOut, status_code=201
)
async def upload_document(
    guild_id: int,
    file: UploadFile,
    description: str = "",
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Upload and index a text document for RAG retrieval."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > _MAX_SIZE_MB:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds {_MAX_SIZE_MB} MB limit.",
        )

    content_hash = hashlib.sha256(contents).hexdigest()

    # Reject if this guild already has a document with identical content.
    existing = await db.execute(
        select(Document).where(
            Document.guild_id == guild_id,
            Document.content_hash == content_hash,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="A document with identical content has already been uploaded to this server.",
        )

    # Strip any directory components from the filename to prevent path traversal.
    safe_filename = Path(file.filename or "upload").name or "upload"

    uploader_id = int(user["id"])

    doc = Document(
        guild_id=guild_id,
        filename=safe_filename,
        description=description or None,
        chroma_collection=f"guild_{guild_id}",
        chunk_count=0,
        uploaded_by=uploader_id,
        campaign_id=None,
        content_hash=content_hash,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / safe_filename
        tmp_path.write_bytes(contents)
        chunk_count = await _indexer.index_file(
            guild_id=guild_id,
            file_path=tmp_path,
            document_id=doc.id,
            description=description or None,
        )

    doc.chunk_count = chunk_count
    await db.commit()
    await db.refresh(doc)
    return doc


@router.patch("/api/guilds/{guild_id}/documents/{doc_id}", response_model=DocumentOut)
async def update_document(
    guild_id: int,
    doc_id: int,
    body: DocumentUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Update a document's description."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    doc = await get_or_404(
        db,
        Document,
        Document.id == doc_id,
        Document.guild_id == guild_id,
        detail="Document not found",
    )
    if "description" in body.model_fields_set:
        doc.description = body.description
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/api/guilds/{guild_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    guild_id: int,
    doc_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an indexed document."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    doc = await get_or_404(
        db,
        Document,
        Document.id == doc_id,
        Document.guild_id == guild_id,
        detail="Document not found",
    )
    await _indexer.delete_document(guild_id, doc_id)
    await db.delete(doc)
    await db.commit()


@router.post(
    "/api/guilds/{guild_id}/documents/search",
    response_model=DocumentSearchResult,
)
async def search_documents(
    guild_id: int,
    body: DocumentSearchRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> DocumentSearchResult:
    """Run a live RAG search against the guild's indexed documents.

    Returns the top-k matching chunks with similarity scores so admins can
    verify that a document has been indexed correctly and is retrievable.
    """
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)

    from api.schemas import DocumentChunk
    from grug.rag.retriever import DocumentRetriever

    try:
        retriever = DocumentRetriever()
        raw = await retriever.search(
            guild_id,
            body.query,
            k=body.k,
            document_id=body.document_id,
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
        logger.exception("Document search failed: %s", exc)
        return DocumentSearchResult(chunks=[], error=True)
