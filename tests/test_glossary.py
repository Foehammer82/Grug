"""Tests for the glossary feature: DB models, agent tools, and ownership rules."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session():
    """In-memory async SQLite session for glossary tests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from grug.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
async def human_term(db_session):
    """A GuildConfig + human-owned GlossaryTerm (guild-wide)."""
    from grug.db.models import GlossaryTerm, GuildConfig

    db_session.add(GuildConfig(guild_id=111))
    await db_session.commit()

    term = GlossaryTerm(
        guild_id=111,
        channel_id=None,
        term="dragon",
        definition="A great serpent worshipped by the lizardfolk.",
        ai_generated=False,
        originally_ai_generated=False,
        created_by=999,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(term)
    await db_session.commit()
    await db_session.refresh(term)
    return term


@pytest.fixture()
async def ai_term(db_session):
    """A GuildConfig + AI-owned GlossaryTerm (guild-wide)."""
    from grug.db.models import GlossaryTerm, GuildConfig

    db_session.add(GuildConfig(guild_id=222))
    await db_session.commit()

    term = GlossaryTerm(
        guild_id=222,
        channel_id=None,
        term="hearth stone",
        definition="A magical stone that warms a room.",
        ai_generated=True,
        originally_ai_generated=True,
        created_by=0,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(term)
    await db_session.commit()
    await db_session.refresh(term)
    return term


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


async def test_glossary_term_creates_ok(db_session):
    """GlossaryTerm can be inserted and queried back."""
    from sqlalchemy import select

    from grug.db.models import GlossaryTerm, GuildConfig

    db_session.add(GuildConfig(guild_id=333))
    await db_session.commit()

    db_session.add(
        GlossaryTerm(
            guild_id=333,
            term="rune",
            definition="A magical symbol carved into stone.",
            ai_generated=False,
            originally_ai_generated=False,
            created_by=1,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(GlossaryTerm).where(GlossaryTerm.guild_id == 333)
    )
    terms = result.scalars().all()
    assert len(terms) == 1
    assert terms[0].term == "rune"


async def test_channel_and_guild_scoped_terms_coexist(db_session):
    """Channel-scoped and guild-scoped entries for the same term can coexist."""
    from sqlalchemy import select

    from grug.db.models import GlossaryTerm, GuildConfig

    db_session.add(GuildConfig(guild_id=444))
    await db_session.commit()

    now = datetime.now(timezone.utc)
    db_session.add(
        GlossaryTerm(
            guild_id=444,
            channel_id=None,
            term="sword",
            definition="Guild sword.",
            ai_generated=False,
            originally_ai_generated=False,
            created_by=1,
            updated_at=now,
        )
    )
    db_session.add(
        GlossaryTerm(
            guild_id=444,
            channel_id=777,
            term="sword",
            definition="Channel sword.",
            ai_generated=False,
            originally_ai_generated=False,
            created_by=1,
            updated_at=now,
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(GlossaryTerm).where(GlossaryTerm.guild_id == 444)
    )
    entries = result.scalars().all()
    assert len(entries) == 2
    scopes = {e.channel_id for e in entries}
    assert scopes == {None, 777}


async def test_history_row_written_on_update(db_session, ai_term):
    """Updating an AI term saves a history row capturing the previous state."""
    from sqlalchemy import select

    from grug.db.models import GlossaryTermHistory

    history = GlossaryTermHistory(
        term_id=ai_term.id,
        guild_id=ai_term.guild_id,
        old_term=ai_term.term,
        old_definition=ai_term.definition,
        old_ai_generated=ai_term.ai_generated,
        changed_by=0,
    )
    db_session.add(history)
    ai_term.definition = "A stone that conjures fire."
    await db_session.commit()

    result = await db_session.execute(
        select(GlossaryTermHistory).where(GlossaryTermHistory.term_id == ai_term.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].old_definition == "A magical stone that warms a room."
    assert rows[0].old_ai_generated is True


async def test_originally_ai_generated_never_mutated(db_session, ai_term):
    """originally_ai_generated remains True even after ai_generated is cleared by a human edit."""
    ai_term.ai_generated = False
    await db_session.commit()
    await db_session.refresh(ai_term)

    assert ai_term.ai_generated is False
    assert ai_term.originally_ai_generated is True


async def test_api_patch_semantics(db_session, ai_term):
    """Simulating an API PATCH: ai_generated=False, originally_ai_generated unchanged."""
    from grug.db.models import GlossaryTermHistory

    history = GlossaryTermHistory(
        term_id=ai_term.id,
        guild_id=ai_term.guild_id,
        old_term=ai_term.term,
        old_definition=ai_term.definition,
        old_ai_generated=ai_term.ai_generated,
        changed_by=42,
    )
    db_session.add(history)
    ai_term.definition = "A warm rock, edited by human."
    ai_term.ai_generated = False
    # originally_ai_generated intentionally NOT touched
    await db_session.commit()
    await db_session.refresh(ai_term)

    assert ai_term.ai_generated is False
    assert ai_term.originally_ai_generated is True

    from sqlalchemy import select

    result = await db_session.execute(
        select(GlossaryTermHistory).where(GlossaryTermHistory.term_id == ai_term.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].changed_by == 42
    assert rows[0].old_ai_generated is True


# ---------------------------------------------------------------------------
# Agent tool unit tests
# ---------------------------------------------------------------------------


async def test_agent_refuses_to_overwrite_human_term():
    """upsert_glossary_term returns a non-writing refusal for human-owned terms."""
    from dataclasses import dataclass

    @dataclass
    class FakeDeps:
        guild_id: int = 111
        channel_id: int = 0
        user_id: int = 1
        username: str = "tester"

    class FakeCtx:
        deps = FakeDeps()

    fake_term = MagicMock()
    fake_term.ai_generated = False
    fake_term.term = "dragon"
    fake_term.definition = "A great serpent."

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake_term)

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_factory = MagicMock(return_value=fake_session)

    with patch("grug.db.session.get_session_factory", return_value=fake_factory):
        import grug.agent.tools.glossary_tools as gt_module
        from pydantic_ai import Agent
        from pydantic_ai.models.test import TestModel

        test_agent: Agent = Agent(TestModel(), deps_type=object, output_type=str)
        gt_module.register_glossary_tools(test_agent)

        upsert_fn = test_agent._function_toolset.tools["upsert_glossary_term"].function

        result = await upsert_fn(FakeCtx(), term="dragon", definition="A new def")
        assert "not change" in result or "respect" in result
        # Session should NOT have had add() called (no write occurred).
        fake_session.add.assert_not_called()


async def test_agent_can_create_new_term():
    """upsert_glossary_term inserts a new row when no existing term is found."""
    from dataclasses import dataclass

    @dataclass
    class FakeDeps:
        guild_id: int = 555
        channel_id: int = 0
        user_id: int = 0
        username: str = "grug"

    class FakeCtx:
        deps = FakeDeps()

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)  # term does not exist

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.add = MagicMock()  # add() is synchronous in SQLAlchemy
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_factory = MagicMock(return_value=fake_session)

    with (
        patch("grug.db.session.get_session_factory", return_value=fake_factory),
        patch("grug.utils.ensure_guild", new=AsyncMock()),
    ):
        import grug.agent.tools.glossary_tools as gt_module
        from pydantic_ai import Agent
        from pydantic_ai.models.test import TestModel

        test_agent: Agent = Agent(TestModel(), deps_type=object, output_type=str)
        gt_module.register_glossary_tools(test_agent)

        upsert_fn = test_agent._function_toolset.tools["upsert_glossary_term"].function

        result = await upsert_fn(
            FakeCtx(), term="vorpal", definition="Exceptionally sharp."
        )
        assert "add" in result.lower() or "vorpal" in result
        fake_session.add.assert_called_once()
        fake_session.commit.assert_called_once()
