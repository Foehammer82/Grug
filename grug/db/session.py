"""Async SQLAlchemy session management."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grug.config.settings import get_settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Run Alembic migrations to bring the Postgres schema up to date."""
    await _run_alembic_migrations()


async def _run_alembic_migrations() -> None:
    """Run alembic upgrade head programmatically for Postgres deployments."""
    import asyncio
    from alembic import command
    from alembic.config import Config

    def _upgrade(cfg: Config) -> None:
        command.upgrade(cfg, "head")

    # Build the config without pointing at alembic.ini so that alembic's
    # fileConfig() is never called — which would otherwise kill all existing
    # log handlers that main.py set up.
    settings = get_settings()
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("prepend_sys_path", ".")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    alembic_cfg.set_main_option(
        "file_template",
        "%%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s",
    )
    logger.info("Running Alembic migrations (upgrade head)...")
    await asyncio.to_thread(_upgrade, alembic_cfg)
    logger.info("Postgres schema up to date (alembic upgrade head).")


async def get_session() -> AsyncSession:  # type: ignore[return]
    """Async context-manager helper for a DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
