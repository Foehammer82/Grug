import asyncio
import logging.config

# noinspection PyUnresolvedReferences
import alembic_postgresql_enum
from pydantic import PostgresDsn
from sqlalchemy.engine import Connection

from alembic import context
from grug import models
from grug.db import async_engine
from grug.settings import settings

logging.config.fileConfig(context.config.config_file_name)


def run_migrations_offline() -> None:
    context.configure(
        url=str(
            PostgresDsn.build(
                scheme="postgresql",
                host=settings.postgres_host,
                port=settings.postgres_port,
                username=settings.postgres_user,
                password=settings.postgres_password.get_secret_value(),
                path=settings.postgres_db,
            )
        ),
        target_metadata=models.SQLModel.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=models.SQLModel.metadata,
        render_as_batch=True,
    )

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
