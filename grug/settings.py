import secrets
import string
from pathlib import Path

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).parent.parent.absolute()


class DiscordSettings(BaseSettings):
    """Settings for connecting to discord."""

    model_config = SettingsConfigDict(extra="ignore")

    bot_token: SecretStr
    auto_create_users: bool = False


class Settings(BaseSettings):
    """Settings for the Grug Bot."""

    model_config = SettingsConfigDict(
        env_file=(
            _ROOT_DIR / "config" / "postgres.env",
            _ROOT_DIR / "config" / "local.env",
            _ROOT_DIR / "config" / "secrets.env",
        ),
        extra="ignore",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
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
    security_access_token_expire_minutes: int = 120

    # API Settings
    api_port: int = 9000
    api_host: str = "localhost"

    # Discord Settings
    discord: DiscordSettings | None = None

    # Database Settings
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "postgres"

    # OpenAI Settings
    openai_key: SecretStr
    openai_model: str = "gpt-4o"
    openai_assistant_name: str = "Grug"
    openai_assistant_instructions: str = "\n".join(
        [
            f"- your name is {openai_assistant_name}.",
            "- You should ALWAYS talk as though you are a barbarian orc with low intelligence but high charisma.",
            "- When asked about tabletop RPGs, you should assume the party is playing pathfinder 2E.",
            "- When providing information, you should try to reference or link to the source of the information.",
        ]
    )
    openai_image_daily_generation_limit: int = 25
    openai_image_default_size: str = "1024x1024"
    openai_image_default_quality: str = "standard"
    openai_image_default_model: str = "dall-e-3"

    # DB Settings
    scheduler_db_schema: str = "apscheduler"

    @computed_field
    @property
    def root_dir(self) -> Path:
        """Get the root directory of the project."""
        return _ROOT_DIR


settings = Settings()
