import os

import pytest

# Set the environment variables for the unit tests
os.environ["DISCORD_BOT_TOKEN"] = "test_token"
os.environ["DISCORD_SERVER_ID"] = "0"
os.environ["DISCORD_GENERAL_CHANNEL_ID"] = "0"
os.environ["PG_USER"] = "test_user"
os.environ["PG_PASS"] = "test_password"
os.environ["PG_HOST"] = "localhost"
os.environ["OPENAI_KEY"] = "test_key"


@pytest.fixture(scope="session", autouse=True)
def settings():
    """Initialize the settings for unit testing the Grug Bot."""
    from grug.settings import settings

    return settings
