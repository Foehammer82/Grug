"""Database setup and initialization."""

from loguru import logger
from pydantic import PostgresDsn
from sqlalchemy import DDL, NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from grug import models
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
    poolclass=NullPool,  # TODO: only enable this for functional testing
)

# Database session factory singleton
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(models.SQLModel.metadata.create_all)
        await conn.execute(DDL(f"CREATE SCHEMA IF NOT EXISTS {settings.scheduler_db_schema}"))

    logger.info("Database initialized [alembic upgrade head].")
