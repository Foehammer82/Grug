import secrets
import string
from pathlib import Path

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).parent.parent.absolute()


class Settings(BaseSettings):
    """Settings for the Grug Bot."""

    model_config = SettingsConfigDict(
        env_file=(
            f"{_ROOT_DIR}/config/postgres.env",
            f"{_ROOT_DIR}/config/local.env",
            f"{_ROOT_DIR}/config/secrets.env",
        ),
        extra="ignore",
    )

    # General Settings
    admin_user: str = "admin"
    admin_password: SecretStr = SecretStr("password")
    enable_metrics: bool = True
    enable_health_endpoint: bool = True

    # Security Settings
    security_key: SecretStr = Field(
        default=SecretStr("".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))),
        description=(
            "The secret key used for security.  If not set, a random key will be generated, however this means that "
            "sessions will not be maintained between restarts."
        ),
    )
    security_algorithm: str = "HS256"
    security_access_token_expire_minutes: int = 30

    # API Settings
    api_port: int = 9000
    api_host: str = "localhost"

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
    # TODO: make discord integration optional
    discord_bot_token: SecretStr
    discord_server_id: int
    discord_bot_channel_id: int | None = None

    # Scheduler Settings
    # TODO: deprecated, remove this once we cut over to the dynamic scheduler
    dnd_session_food_reminder_cron: str = Field(
        default="*/10 * * * *",
        description="Defines the scheduled time for the food reminder",
    )
    dnd_session_schedule_cron: str = Field(
        default="0 17 * * 0",
        description="Defines the time for the weekly D&D session",
    )

    # Database Settings
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "postgres"

    # OpenAI Settings
    openai_key: SecretStr
    openai_model: str = "gpt-3.5-turbo"

    @computed_field
    @property
    def root_dir(self) -> Path:
        """Get the root directory of the project."""
        return _ROOT_DIR


settings = Settings()
