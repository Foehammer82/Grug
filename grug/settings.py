from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

import pytz
from pydantic import AliasChoices, Field, PostgresDsn, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TimeZone = StrEnum("TimeZone", tuple((tz, tz) for tz in pytz.common_timezones))
_ROOT_DIR = Path(__file__).parent.parent.absolute()

# TODO: enable secrets loading from text files as an option


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
    environment: Literal["dev", "prd"] = "dev"
    dev_guild_id: int | None = None
    timezone: TimeZone = Field(default=TimeZone["UTC"], validation_alias=AliasChoices("tz"))

    # Discord Settings
    discord_bot_token: SecretStr | None = None
    discord_bot_channel_id: int | None = None

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

    # Database Settings
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str = "postgres"
    postgres_apscheduler_schema: str = "apscheduler"

    # OpenAI Settings
    openai_key: SecretStr | None = None
    openai_model: str = "gpt-4o"
    openai_fallback_model: str = "gpt-4o-mini"
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
            "Grug be a charming yet simple-minded barbarian orc who love to help humans, goblins, and all in between! "
            "If want to know more about Grug, just ask! Grug always happy to help!  Or, checkout my documentation at "
            "https://foehammer82.github.io/Grug/"
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

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        if self.openai_fallback_model == self.openai_model:
            raise ValueError("fallback model cannot be the same as the primary model")

        return self


# Create the settings singleton object
settings = Settings()
