"""Async SQLAlchemy session management."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grug.config.settings import get_settings
from grug.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Create all tables and apply lightweight column migrations."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe migration: add archived column to existing conversation_messages tables.
        try:
            await conn.execute(
                text(
                    "ALTER TABLE conversation_messages "
                    "ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        except Exception:
            pass  # Column already exists — nothing to do.


async def get_session() -> AsyncSession:  # type: ignore[return]
    """Async context-manager helper for a DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
