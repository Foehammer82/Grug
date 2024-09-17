import os

import pytest

from grug.db import async_session


def pytest_sessionstart(session):
    # TODO: configure to use sqlite for local development and testing, when postgres is not available
    os.environ["POSTGRES_USER"] = "fake-pg-user"
    os.environ["POSTGRES_PASSWORD"] = "fake-pg-password"


@pytest.fixture(scope="package", autouse=True)
def settings():
    """Initialize the settings for unit testing the Grug Bot."""
    from grug.settings import settings

    return settings


@pytest.fixture()
async def async_db_session():
    """Create a new async database session for each test."""
    async with async_session() as session:
        yield session
