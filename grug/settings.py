import secrets
import string
from enum import StrEnum
from pathlib import Path

import pytz
from pydantic import AliasChoices, Field, PostgresDsn, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).parent.parent.absolute()
TimeZone = StrEnum("TimeZone", tuple((tz, tz) for tz in pytz.common_timezones))


class DiscordSettings(BaseSettings):
    """Settings for connecting to discord."""

    model_config = SettingsConfigDict(extra="ignore")

    bot_token: SecretStr
    client_id: str
    client_secret: SecretStr
    enable_oauth: bool = True
    admin_user_id: int | None = Field(
        default=None,
        description=(
            "The Discord user ID of the admin user.  Any user set here will be given admin "
            "permissions and cannot be removed from the admin role."
        ),
    )


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
    timezone: TimeZone = Field(default=TimeZone["UTC"], validation_alias=AliasChoices("tz"))
    log_level: str = "info"
    proxy_headers: bool = False

    # Metrics Settings
    enable_metrics_endpoint: bool = True
    metrics_key: SecretStr | None = None

    # Sentry Settings
    # https://docs.sentry.io/platforms/python/#configure
    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(
        default=1.0,
        description="Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.",
    )
    sentry_profiles_sample_rate: float = Field(
        default=0.6,
        description=(
            "Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions. We recommend adjusting "
            "this value in production."
        ),
    )

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
    postgres_apscheduler_schema: str = "apscheduler"

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
    openai_assistant_about: str | None = Field(
        default=(
            "Grug be a charming yet simple-minded barbarian orc who love to help humans, goblins, and all in between. "
            "Grug provide aid with Pathfinder 2E rules, give advice, and make art of homes and dreams. With low brain "
            "power but big heart, Grug strive to make everyone’s day better, one orcish word at a time!\n\n"
            "Documentation: https://foehammer82.github.io/Grug/\n"
            "Privacy Policy: https://github.com/Foehammer82/Grug/blob/main/docs/about/privacy_policy.md\n"
        ),
        description="The about message for the assistant.",
    )
    openai_image_daily_generation_limit: int | None = Field(
        default=25, description="The daily limit of image generations. If None, there is no limit."
    )
    openai_image_default_size: str = "1024x1024"
    openai_image_default_quality: str = "standard"
    openai_image_default_model: str = "dall-e-3"

    @computed_field
    @property
    def root_dir(self) -> Path:
        """Get the root directory of the project."""
        return _ROOT_DIR

    @computed_field
    @property
    def postgres_dsn(self) -> str:
        """Get the Postgres DSN."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                host=self.postgres_host,
                port=self.postgres_port,
                username=self.postgres_user,
                password=self.postgres_password.get_secret_value(),
                path=self.postgres_db,
            )
        )


settings = Settings()
