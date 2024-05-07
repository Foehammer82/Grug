import asyncio
import logging.config

from sqlalchemy.engine import Connection

from alembic import context
from grug import models
from grug.db import async_engine
from grug.settings import settings

logging.config.fileConfig(context.config.config_file_name)

target_metadata = models.SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.get_db_urn(is_async=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    async with async_engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await async_engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
