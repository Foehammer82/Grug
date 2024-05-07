from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).parent.parent.absolute()


class Settings(BaseSettings):
    """Settings for the Grug Bot."""

    model_config = SettingsConfigDict(
        env_file=f"{_ROOT_DIR}/config/secrets.env",
        extra="ignore",
    )

    # Bot Settings
    bot_name: str = "Grug"
    bot_instructions: str = "\n".join(
        [
            f"- your name is {bot_name}.",
            "- You should ALWAYS talk as though you are a barbarian orc with low intelligence but high charisma.",
            "- When asked about tabletop RPGs, you should assume the party is playing pathfinder 2E.",
            "- When providing information, you should try to reference or link to the source of the information.",
        ]
    )

    # Discord Settings
    discord_bot_token: SecretStr
    discord_server_id: int
    discord_bot_channel: int | None = None
    discord_copy_global_on_startup: bool = True

    # Scheduler Settings
    dnd_session_food_reminder_cron: str = "30 * * * *"
    dnd_session_schedule_cron: str = "0 17 * * 0"

    # Database Settings
    pg_user: str
    pg_pass: SecretStr
    pg_host: str
    pg_port: int = 5342
    pg_db: str = "postgres"

    # OpenAI Settings
    openai_key: SecretStr
    openai_model: str = "gpt-3.5-turbo"

    @property
    def root_dir(self) -> Path:
        """Get the root directory of the project."""
        return _ROOT_DIR

    def get_db_urn(self, is_async: bool = True) -> str:
        """
        Get the database URN for the PostgreSQL database.

        Args:
            is_async (bool): Whether to use the asyncpg driver.
        """

        return (
            f"postgresql+{'asyncpg' if is_async else 'psycopg2'}://"
            f"{self.pg_user}:{self.pg_pass.get_secret_value()}"
            f"@{self.pg_host}:{self.pg_port}"
            f"/{self.pg_db}"
        )


settings = Settings()
