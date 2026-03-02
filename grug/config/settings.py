"""Configuration settings for Grug loaded from environment variables."""

from functools import cache
import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    # Discord
    discord_token: str = Field(default="", description="Discord bot token")

    # Anthropic
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-haiku-4-5",
        description="Anthropic model to use",
    )
    anthropic_big_brain_model: str = Field(
        default="claude-sonnet-4-6",
        description="More capable model for complex extraction and summarization tasks",
    )

    # Discord OAuth (used by the web API; optional for bot-only deployments)
    discord_client_id: str = Field(default="", description="Discord OAuth client ID")
    discord_client_secret: str = Field(
        default="", description="Discord OAuth client secret"
    )
    discord_redirect_uri: str = Field(
        default="http://localhost:8000/auth/discord/callback",
        description="Discord OAuth redirect URI",
    )
    discord_bot_token: str = Field(
        default="",
        description="Bot token used by the API to proxy guild channel lookups",
    )

    # Web API
    web_secret_key: str = Field(
        default="change-me", description="Secret key for JWT signing"
    )
    web_cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated allowed CORS origins",
    )
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="URL of the frontend for OAuth redirects",
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://grug:grug@localhost:5432/grug",
        description="SQLAlchemy async database URL (Postgres required)",
    )

    # General
    default_timezone: str = Field(
        default="UTC",
        description="Default timezone used for new guild configs and scheduled tasks",
    )

    # MCP servers — stored as a JSON string in the env var
    mcp_server_configs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of MCP server configurations",
    )

    @field_validator("mcp_server_configs", mode="before")
    @classmethod
    def parse_mcp_configs(cls, v: Any) -> list[dict[str, Any]]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    # Agent
    agent_max_iterations: int = Field(
        default=10,
        description="Maximum tool-calling iterations per response",
    )
    agent_context_window: int = Field(
        default=20,
        description="Number of recent messages to keep in context",
    )
    agent_history_archive_batch: int = Field(
        default=10,
        description="Minimum overflow messages required before archiving to RAG history",
    )
    agent_history_max_summaries: int = Field(
        default=100,
        description="Max number of per-channel history summaries kept in the vector store (oldest pruned beyond this)",
    )
    flush_chat_history: bool = Field(
        default=False,
        description="Archive all conversation history on startup (useful for testing prompt changes)",
    )

    # Admin — comma-separated list of Discord user IDs that are Grug super-admins.
    grug_super_admin_ids_raw: str = Field(
        default="",
        alias="grug_super_admin_ids",
        description="Discord user IDs with global admin access (comma-separated)",
    )

    @property
    def grug_super_admin_ids(self) -> list[str]:
        """Parse the comma-separated raw string into a list of user IDs."""
        return [
            uid.strip()
            for uid in self.grug_super_admin_ids_raw.split(",")
            if uid.strip()
        ]

    # File storage — uploaded character sheets are persisted here.
    file_data_dir: str = Field(
        default="./file_data",
        description="Directory to store uploaded character sheet files",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")


@cache
def get_settings() -> Settings:
    """Return the cached Settings instance."""
    return Settings()
