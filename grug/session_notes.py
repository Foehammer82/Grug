"""Session notes service — submission, LLM synthesis, and RAG indexing.

This module contains the shared business logic for session notes so both
the FastAPI routes and the Discord agent tool call the same functions.

Lifecycle
---------
1.  A user submits raw notes via the web UI or Discord (paste or file upload).
2.  ``create_session_note()`` persists the raw text with ``synthesis_status='pending'``.
3.  A ``BackgroundTask`` calls ``synthesize_note()`` which:
    a.  Flips ``synthesis_status`` to ``'processing'``.
    b.  Calls a fast LLM (claude-haiku) with the raw notes and campaign context.
    c.  Stores the cleaned narrative in ``clean_notes``.
    d.  Indexes ``clean_notes`` into the RAG vector store as a ``Document`` with
        the correct ``campaign_id`` so Grug can search them later.
    e.  Sets ``synthesis_status='done'`` and stores ``rag_document_id``.
    f.  On any failure, sets ``synthesis_status='failed'`` and records the error.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from grug.db.models import SessionNote

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a meticulous scribe for a tabletop RPG campaign. You will receive raw,
unedited session notes submitted by a player or GM. These may be messy, full of
abbreviations, and written in note-taking shorthand.

Your task is to rewrite them into a clean, cohesive session summary that reads
like a proper session recap. The output should:
- Be written in past tense, third-person narrative (e.g. "The party traveled...")
- Preserve ALL events, NPCs, locations, loot, and story beats — do not invent or
  omit anything. If something is unclear, include it verbatim in brackets.
- Organise the content chronologically (or by what makes the most logical sense).
- Highlight key NPCs, new locations, and notable decisions in a brief bullet-point
  "Session Highlights" section at the end.
- Be thorough but not padded — every sentence should convey information.

Do NOT add any fictional events, dialogue, or content not implied by the notes.
Do NOT wrap the output in markdown code fences.
"""


async def is_campaign_member(
    db: AsyncSession,
    campaign_id: int,
    discord_user_id: int,
) -> bool:
    """Return True if the user has a character in the campaign."""
    from grug.db.models import Character

    result = await db.execute(
        select(Character).where(
            Character.campaign_id == campaign_id,
            Character.owner_discord_user_id == discord_user_id,
        )
    )
    return result.scalars().first() is not None


async def create_session_note(
    db: AsyncSession,
    *,
    campaign_id: int,
    guild_id: int,
    submitted_by: int,
    raw_notes: str,
    session_date: date | None = None,
    title: str | None = None,
) -> SessionNote:  # type: ignore[name-defined]
    """Persist a new session note with ``synthesis_status='pending'``."""
    from grug.db.models import SessionNote

    note = SessionNote(
        campaign_id=campaign_id,
        guild_id=guild_id,
        submitted_by=submitted_by,
        raw_notes=raw_notes.strip(),
        session_date=session_date,
        title=title,
        synthesis_status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def synthesize_note(note_id: int) -> None:
    """Run LLM synthesis on a session note and index the result for RAG.

    Designed to run as a FastAPI ``BackgroundTask``.  Uses its own DB session
    so it is not tied to the HTTP request session.
    """
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from grug.config.settings import get_settings
    from grug.db.models import Campaign, Document, SessionNote
    from grug.db.session import get_session_factory
    from grug.llm_usage import CallType, record_llm_usage
    from grug.rag.indexer import DocumentIndexer

    factory = get_session_factory()

    async with factory() as session:
        note = await session.get(SessionNote, note_id)
        if note is None:
            logger.warning("synthesize_note: note %d not found", note_id)
            return

        campaign = await session.get(Campaign, note.campaign_id)
        campaign_name = campaign.name if campaign else "Unknown Campaign"
        campaign_system = campaign.system if campaign else "unknown"
        guild_id = note.guild_id

        # Transition to processing.
        note.synthesis_status = "processing"
        note.synthesis_error = None
        note.updated_at = datetime.now(timezone.utc)
        await session.commit()

    # LLM call (outside the session to avoid holding the connection).
    try:
        settings = get_settings()
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        model = AnthropicModel("claude-haiku-4-5", provider=provider)

        date_str = ""
        if note.session_date is not None:
            date_str = f"Session date: {note.session_date.isoformat()}\n"

        user_message = (
            f"Campaign: {campaign_name} (system: {campaign_system})\n"
            f"{date_str}"
            f"Title: {note.title or '(untitled)'}\n\n"
            f"--- RAW NOTES ---\n{note.raw_notes}"
        )

        synthesizer: Agent[None, str] = Agent(
            model,
            output_type=str,
            system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
        )
        result = await synthesizer.run(user_message)
        clean_notes = result.output

        usage = result.usage()
        await record_llm_usage(
            model="claude-haiku-4-5",
            call_type=CallType.SESSION_NOTE_SYNTHESIS,
            input_tokens=usage.request_tokens or 0,
            output_tokens=usage.response_tokens or 0,
            guild_id=guild_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Session note synthesis failed for note %d", note_id)
        async with factory() as session:
            note = await session.get(SessionNote, note_id)
            if note is not None:
                note.synthesis_status = "failed"
                note.synthesis_error = str(exc)
                note.updated_at = datetime.now(timezone.utc)
                await session.commit()
        return

    # Index the clean notes into RAG.
    try:
        indexer = DocumentIndexer()
        title_slug = (note.title or f"session-{note.id}").replace(" ", "_")[:60]
        filename = f"session_note_{note.id}_{title_slug}.txt"

        async with factory() as session:
            doc = Document(
                guild_id=guild_id,
                filename=filename,
                description=f"Session notes — {note.title or 'untitled'} ({campaign_name})",
                chroma_collection=f"guild_{guild_id}",
                chunk_count=0,
                uploaded_by=note.submitted_by,
                campaign_id=note.campaign_id,
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            doc_id = doc.id

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_text(clean_notes, encoding="utf-8")
            chunk_count = await indexer.index_file(
                guild_id=guild_id,
                file_path=tmp_path,
                document_id=doc_id,
                description=doc.description,
            )

        async with factory() as session:
            doc_row = await session.get(Document, doc_id)
            if doc_row is not None:
                doc_row.chunk_count = chunk_count
                await session.commit()

    except Exception as exc:  # noqa: BLE001
        logger.exception("RAG indexing failed for session note %d", note_id)
        # Synthesis text is still good — mark done and note the RAG error.
        async with factory() as session:
            note = await session.get(SessionNote, note_id)
            if note is not None:
                note.clean_notes = clean_notes
                note.synthesis_status = "done"
                note.synthesis_error = f"RAG indexing failed: {exc}"
                note.updated_at = datetime.now(timezone.utc)
                await session.commit()
        return

    # All good — finalise.
    async with factory() as session:
        note = await session.get(SessionNote, note_id)
        if note is not None:
            note.clean_notes = clean_notes
            note.synthesis_status = "done"
            note.synthesis_error = None
            note.rag_document_id = doc_id
            note.updated_at = datetime.now(timezone.utc)
            await session.commit()

    logger.info(
        "Session note %d synthesized and indexed as document %d (%d chunks)",
        note_id,
        doc_id,
        chunk_count,
    )


async def delete_session_note(note_id: int, guild_id: int) -> None:
    """Delete a session note and its associated RAG document."""
    from grug.db.models import Document, SessionNote
    from grug.db.session import get_session_factory
    from grug.rag.indexer import DocumentIndexer

    factory = get_session_factory()
    async with factory() as session:
        note = await session.get(SessionNote, note_id)
        if note is None or note.guild_id != guild_id:
            return

        rag_doc_id = note.rag_document_id
        await session.delete(note)
        await session.commit()

    if rag_doc_id is not None:
        try:
            indexer = DocumentIndexer()
            await indexer.delete_document(guild_id, rag_doc_id)
            async with factory() as session:
                doc = await session.get(Document, rag_doc_id)
                if doc is not None:
                    await session.delete(doc)
                    await session.commit()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to clean up RAG document %d for deleted session note %d",
                rag_doc_id,
                note_id,
            )
