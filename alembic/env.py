"""Alembic migration environment — async SQLAlchemy with asyncpg.

Runs migrations against Postgres only. The DATABASE_URL is read from
grug's settings so it honours the same .env / environment variable as
the rest of the application.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Import all models so their tables are registered with Base.metadata.
from grug.db.models import Base  # noqa: F401 — registers standard tables
import grug.db.pg_models  # noqa: F401 — registers vector embedding tables

from grug.config.settings import get_settings

# Alembic Config object from alembic.ini
config = context.config

# Wire up Python logging from alembic.ini sections.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the live DATABASE_URL so we never need it hardcoded in alembic.ini.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL, no connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
