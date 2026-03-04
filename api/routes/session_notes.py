"""Session notes routes — submit, track, and manage per-campaign session logs."""

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_current_user,
    get_db,
    get_or_404,
    is_guild_admin,
)
from api.schemas import (
    DocumentSearchResult,
    SessionNoteCreate,
    SessionNoteOut,
    SessionNoteRagTestRequest,
    SessionNoteUpdate,
)
from grug.db.models import Campaign, SessionNote
from grug.session_notes import (
    create_session_note,
    is_campaign_member,
    synthesize_note,
    delete_session_note as svc_delete_session_note,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["session-notes"])

_ALLOWED_NOTE_EXTENSIONS = {".txt", ".md", ".rst", ".pdf", ".docx", ".doc"}
_TEXT_NOTE_EXTENSIONS = {".txt", ".md", ".rst"}
_MAX_NOTE_SIZE_MB = 20


async def _assert_note_access(
    note: SessionNote,
    guild_id: int,
    user: dict[str, Any],
    *,
    require_write: bool = False,
) -> None:
    """Raise 403/404 if the user cannot access (or write) the note."""
    if note.guild_id != guild_id:
        raise HTTPException(status_code=404, detail="Session note not found")
    if require_write:
        admin = await is_guild_admin(guild_id, user)
        if not admin and note.submitted_by != int(user["id"]):
            raise HTTPException(
                status_code=403,
                detail="Only the note submitter or a guild admin may modify this note.",
            )


async def _assert_campaign_member_or_admin(
    db: AsyncSession,
    campaign: Campaign,
    user: dict[str, Any],
) -> None:
    """Raise 403 unless the user is a campaign member or guild admin."""
    admin = await is_guild_admin(campaign.guild_id, user)
    if admin:
        return
    member = await is_campaign_member(db, campaign.id, int(user["id"]))
    if not member:
        raise HTTPException(
            status_code=403,
            detail="You must have a character in this campaign to submit session notes.",
        )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes",
    response_model=list[SessionNoteOut],
)
async def list_session_notes(
    guild_id: int,
    campaign_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionNote]:
    """List all session notes for a campaign."""
    assert_guild_member(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    await _assert_campaign_member_or_admin(db, campaign, user)

    result = await db.execute(
        select(SessionNote)
        .where(SessionNote.campaign_id == campaign_id)
        .order_by(
            SessionNote.session_date.desc().nulls_last(), SessionNote.created_at.desc()
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes/{note_id}",
    response_model=SessionNoteOut,
)
async def get_session_note(
    guild_id: int,
    campaign_id: int,
    note_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionNote:
    """Fetch a single session note including raw and clean content."""
    assert_guild_member(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    await _assert_campaign_member_or_admin(db, campaign, user)
    note = await get_or_404(
        db,
        SessionNote,
        SessionNote.id == note_id,
        SessionNote.campaign_id == campaign_id,
        detail="Session note not found",
    )
    await _assert_note_access(note, guild_id, user)
    return note


# ---------------------------------------------------------------------------
# Create (text paste)
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes",
    response_model=SessionNoteOut,
    status_code=201,
)
async def create_session_note_route(
    guild_id: int,
    campaign_id: int,
    body: SessionNoteCreate,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionNote:
    """Submit raw session notes as JSON text.  Synthesis runs in the background."""
    assert_guild_member(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    await _assert_campaign_member_or_admin(db, campaign, user)

    if not body.raw_notes.strip():
        raise HTTPException(status_code=422, detail="raw_notes must not be empty.")

    note = await create_session_note(
        db,
        campaign_id=campaign_id,
        guild_id=guild_id,
        submitted_by=int(user["id"]),
        raw_notes=body.raw_notes,
        session_date=body.session_date,
        title=body.title,
    )
    background_tasks.add_task(synthesize_note, note.id)
    return note


# ---------------------------------------------------------------------------
# Create (file upload)
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes/upload",
    response_model=SessionNoteOut,
    status_code=201,
)
async def upload_session_note(
    guild_id: int,
    campaign_id: int,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session_date: str | None = Form(default=None),
    title: str | None = Form(default=None),
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionNote:
    """Upload a text file as session notes.  Synthesis runs in the background."""
    assert_guild_member(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    await _assert_campaign_member_or_admin(db, campaign, user)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_NOTE_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_NOTE_EXTENSIONS))}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > _MAX_NOTE_SIZE_MB:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds {_MAX_NOTE_SIZE_MB} MB limit.",
        )

    # Extract text — plain-text files decoded directly; binary formats via indexer helper.
    if ext in _TEXT_NOTE_EXTENSIONS:
        raw_notes = contents.decode("utf-8", errors="replace").strip()
    else:
        import asyncio
        import tempfile as _tempfile
        from grug.rag.indexer import _extract_text

        safe_name = Path(file.filename or f"upload{ext}").name
        with _tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / safe_name
            tmp_path.write_bytes(contents)
            raw_notes = await asyncio.to_thread(_extract_text, tmp_path)
        raw_notes = raw_notes.strip()
    if not raw_notes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    parsed_date: date | None = None
    if session_date:
        try:
            parsed_date = date.fromisoformat(session_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid session_date format '{session_date}'. Expected YYYY-MM-DD.",
            )

    note = await create_session_note(
        db,
        campaign_id=campaign_id,
        guild_id=guild_id,
        submitted_by=int(user["id"]),
        raw_notes=raw_notes,
        session_date=parsed_date,
        title=title or Path(file.filename or "").stem or None,
    )
    background_tasks.add_task(synthesize_note, note.id)
    return note


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.patch(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes/{note_id}",
    response_model=SessionNoteOut,
)
async def update_session_note(
    guild_id: int,
    campaign_id: int,
    note_id: int,
    body: SessionNoteUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionNote:
    """Update a session note's title, date, or raw notes (using model_fields_set)."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    note = await get_or_404(
        db,
        SessionNote,
        SessionNote.id == note_id,
        SessionNote.campaign_id == campaign_id,
        detail="Session note not found",
    )
    await _assert_note_access(note, guild_id, user, require_write=True)

    if "title" in body.model_fields_set:
        note.title = body.title
    if "session_date" in body.model_fields_set:
        note.session_date = body.session_date
    if "raw_notes" in body.model_fields_set:
        if body.raw_notes is not None and not body.raw_notes.strip():
            raise HTTPException(status_code=422, detail="raw_notes must not be empty.")
        note.raw_notes = body.raw_notes  # type: ignore[assignment]

    note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


# ---------------------------------------------------------------------------
# Re-trigger synthesis
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes/{note_id}/synthesize",
    response_model=SessionNoteOut,
)
async def synthesize_session_note(
    guild_id: int,
    campaign_id: int,
    note_id: int,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionNote:
    """Re-trigger LLM synthesis (e.g. after editing raw notes).

    Resets synthesis status to 'pending' and launches a background task.
    """
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    note = await get_or_404(
        db,
        SessionNote,
        SessionNote.id == note_id,
        SessionNote.campaign_id == campaign_id,
        detail="Session note not found",
    )
    await _assert_note_access(note, guild_id, user, require_write=True)

    note.synthesis_status = "pending"
    note.synthesis_error = None
    note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)

    background_tasks.add_task(synthesize_note, note.id)
    return note


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes/{note_id}",
    status_code=204,
)
async def delete_session_note_route(
    guild_id: int,
    campaign_id: int,
    note_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a session note and its RAG index entry."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    note = await get_or_404(
        db,
        SessionNote,
        SessionNote.id == note_id,
        SessionNote.campaign_id == campaign_id,
        detail="Session note not found",
    )
    await _assert_note_access(note, guild_id, user, require_write=True)

    # Delegate to service so RAG cleanup is centralised.
    await svc_delete_session_note(note.id, guild_id)


# ---------------------------------------------------------------------------
# RAG test
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes/test-rag",
    response_model=DocumentSearchResult,
)
async def test_session_notes_rag(
    guild_id: int,
    campaign_id: int,
    body: SessionNoteRagTestRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentSearchResult:
    """Run a live RAG search against indexed session notes for this campaign.

    Admin-only.  Returns the top-k matching chunks so admins can verify that
    session notes have been indexed correctly and are retrievable.
    """
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )

    from api.schemas import DocumentChunk
    from grug.rag.retriever import DocumentRetriever

    try:
        retriever = DocumentRetriever()
        raw = await retriever.search(
            guild_id,
            body.query,
            k=body.k,
            campaign_id=campaign_id,
        )
        chunks = [
            DocumentChunk(
                text=c["text"],
                filename=c.get("filename", "session-notes"),
                chunk_index=c["chunk_index"],
                distance=round(float(c.get("distance", 0.0)), 4),
            )
            for c in raw
        ]
        return DocumentSearchResult(chunks=chunks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Session notes RAG test failed: %s", exc)
        return DocumentSearchResult(chunks=[], error=True)
