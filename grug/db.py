"""Database setup and initialization."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, create_engine

from grug.settings import settings

# Database engine singleton
async_engine = create_async_engine(
    url=settings.get_db_urn(is_async=True),
    echo=False,
    future=True,
)

# Database session factory singleton
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


def init_db():
    """Initialize the database."""
    # noinspection PyUnresolvedReferences
    from grug import models  # noqa: F401

    SQLModel.metadata.create_all(create_engine(settings.get_db_urn(is_async=False)))
