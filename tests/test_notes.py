"""Tests for the GrugNote model — guild-scoped and personal notes."""

from __future__ import annotations


import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session():
    """In-memory async SQLite session for notes tests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from grug.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


async def test_guild_note_creates_ok(db_session):
    """A guild-scoped GrugNote can be inserted and queried."""
    from sqlalchemy import select

    from grug.db.models import GrugNote

    note = GrugNote(
        guild_id=111, user_id=None, content="# Server Rules\n- Be kind", updated_by=0
    )
    db_session.add(note)
    await db_session.commit()

    result = await db_session.execute(
        select(GrugNote).where(GrugNote.guild_id == 111, GrugNote.user_id.is_(None))
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].content == "# Server Rules\n- Be kind"
    assert rows[0].user_id is None


async def test_personal_note_creates_ok(db_session):
    """A personal GrugNote (user-scoped, no guild) can be inserted and queried."""
    from sqlalchemy import select

    from grug.db.models import GrugNote

    note = GrugNote(guild_id=None, user_id=42, content="Likes spicy food", updated_by=0)
    db_session.add(note)
    await db_session.commit()

    result = await db_session.execute(
        select(GrugNote).where(GrugNote.user_id == 42, GrugNote.guild_id.is_(None))
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].content == "Likes spicy food"
    assert rows[0].guild_id is None


async def test_guild_and_personal_notes_coexist(db_session):
    """Guild notes and personal notes can coexist in the same table."""
    from sqlalchemy import select

    from grug.db.models import GrugNote

    db_session.add(
        GrugNote(guild_id=111, user_id=None, content="Guild note", updated_by=0)
    )
    db_session.add(
        GrugNote(guild_id=None, user_id=42, content="Personal note", updated_by=0)
    )
    await db_session.commit()

    result = await db_session.execute(select(GrugNote))
    all_notes = result.scalars().all()
    assert len(all_notes) == 2


async def test_note_content_update(db_session):
    """Updating a note's content persists correctly."""

    from grug.db.models import GrugNote

    note = GrugNote(guild_id=111, user_id=None, content="Original", updated_by=0)
    db_session.add(note)
    await db_session.commit()

    note.content = "Updated content"
    note.updated_by = 999
    await db_session.commit()
    await db_session.refresh(note)

    assert note.content == "Updated content"
    assert note.updated_by == 999


async def test_note_defaults(db_session):
    """Default values are set correctly for timestamps and updated_by."""
    from grug.db.models import GrugNote

    note = GrugNote(guild_id=111, user_id=None, content="test")
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    assert note.created_at is not None
    assert note.updated_at is not None
    assert note.updated_by == 0
