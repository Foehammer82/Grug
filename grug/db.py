"""Database setup and initialization."""

import asyncio
import subprocess  # nosec B404
import sys

from loguru import logger
from sqlalchemy import DDL, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grug.settings import settings

# Set the event loop policy for Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Database engine singleton
async_engine = create_async_engine(
    url=settings.postgres_dsn,
    echo=False,
    future=True,
)

# Database session factory singleton
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session_dependency():
    async with async_session() as session:
        yield session


async def init_db():
    # Run the Alembic migrations
    result = subprocess.run(  # nosec B607, B603
        ["alembic", "upgrade", "head"],
        cwd=settings.root_dir.as_posix(),
        capture_output=True,
        text=True,
    )
    logger.info(result.stdout)
    logger.info(result.stderr)

    # Perform any necessary manual DB init steps
    async with async_engine.begin() as conn:
        await conn.execute(DDL(f"CREATE SCHEMA IF NOT EXISTS {settings.postgres_apscheduler_schema}"))

    logger.info("Database initialized [alembic upgrade head].")


def check_db_connection():
    try:
        with create_engine(
            url=settings.postgres_dsn,
            echo=False,
            future=True,
        ).connect() as conn:
            conn.execute(DDL("SELECT 1"))
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False
    return True


if __name__ == "__main__":
    print(check_db_connection())
