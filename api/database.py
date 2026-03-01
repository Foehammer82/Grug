"""Async SQLAlchemy session factory for the API."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

_engine_kwargs: dict = {"echo": False}
if settings.database_url.startswith("postgresql"):
    _engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True})

engine = create_async_engine(settings.database_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
