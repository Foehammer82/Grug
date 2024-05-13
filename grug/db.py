"""Database setup and initialization."""

from pydantic import PostgresDsn
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, create_engine

from grug.settings import settings

# Database engine singleton
async_engine = create_async_engine(
    url=str(
        PostgresDsn.build(
            scheme="postgresql+asyncpg",
            host=settings.pg_host,
            port=settings.pg_port,
            username=settings.pg_user,
            password=settings.pg_pass.get_secret_value(),
            path=settings.pg_db,
        )
    ),
    echo=False,
    future=True,
)

# Database session factory singleton
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


def init_db():
    """Initialize the database."""
    # noinspection PyUnresolvedReferences
    from grug import models  # noqa: F401

    SQLModel.metadata.create_all(
        create_engine(
            str(
                PostgresDsn.build(
                    scheme="postgresql",
                    host=settings.pg_host,
                    port=settings.pg_port,
                    username=settings.pg_user,
                    password=settings.pg_pass.get_secret_value(),
                    path=settings.pg_db,
                )
            )
        )
    )
