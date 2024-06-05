"""Database setup and initialization."""

import subprocess

from loguru import logger
from pydantic import PostgresDsn
from sqlalchemy import DDL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grug.settings import settings

# Database engine singleton
async_engine = create_async_engine(
    url=str(
        PostgresDsn.build(
            scheme="postgresql+asyncpg",
            host=settings.postgres_host,
            port=settings.postgres_port,
            username=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
            path=settings.postgres_db,
        )
    ),
    echo=False,
    future=True,
    # poolclass=NullPool,  # TODO: may need this for functional tests
)

# Database session factory singleton
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    # Run the Alembic migrations
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=settings.root_dir.as_posix(),
        capture_output=True,
        text=True,
    )
    logger.info(result.stdout)
    logger.info(result.stderr)

    # Perform any necessary manual DB init steps
    async with async_engine.begin() as conn:
        await conn.execute(DDL(f"CREATE SCHEMA IF NOT EXISTS {settings.scheduler_db_schema}"))

    logger.info("Database initialized [alembic upgrade head].")
