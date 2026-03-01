"""Async SQLAlchemy session management."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grug.config.settings import get_settings
from grug.db.models import Base

logger = logging.getLogger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict = {"echo": False}
        if settings.database_url.startswith("postgresql"):
            # Use a proper connection pool for Postgres.
            kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True})
        _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Initialise the database schema.

    - SQLite: uses SQLAlchemy create_all (fast, no migration tooling needed).
    - Postgres: runs Alembic migrations so schema is version-controlled.
    """
    settings = get_settings()
    if settings.database_url.startswith("postgresql"):
        await _run_alembic_migrations()
    else:
        await _create_all_sqlite()


async def _create_all_sqlite() -> None:
    """Create all SQLite tables via SQLAlchemy metadata (no Alembic needed).

    Also applies incremental column additions for existing tables so that
    upgrading an existing installation does not require a full migration tool.
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Incremental migrations: add new nullable columns to existing tables without
    # breaking existing data.  Each ALTER TABLE is idempotent — it catches the
    # OperationalError that SQLite raises when the column already exists.
    async with get_engine().connect() as conn:
        for ddl in _SQLITE_INCREMENTAL_DDLS:
            try:
                await conn.execute(text(ddl))
                await conn.commit()
            except Exception:
                # Column already exists — safe to ignore.
                await conn.rollback()

    logger.info("SQLite schema initialised via create_all.")


# Each entry is a DDL statement that is safe to run against an already-migrated
# database (the surrounding try/except makes them idempotent).
_SQLITE_INCREMENTAL_DDLS: list[str] = [
    "ALTER TABLE documents ADD COLUMN campaign_id INTEGER NULL",
]


async def _run_alembic_migrations() -> None:
    """Run alembic upgrade head programmatically for Postgres deployments."""
    import asyncio
    from alembic import command
    from alembic.config import Config

    def _upgrade(cfg: Config) -> None:
        command.upgrade(cfg, "head")

    alembic_cfg = Config("alembic.ini")
    await asyncio.to_thread(_upgrade, alembic_cfg)
    logger.info("Postgres schema up to date (alembic upgrade head).")


async def get_session() -> AsyncSession:  # type: ignore[return]
    """Async context-manager helper for a DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
