"""Configuration settings for Grug loaded from environment variables."""

import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Discord
    discord_token: str = Field(..., description="Discord bot token")
    discord_prefix: str = Field(default="!", description="Command prefix")

    # Anthropic
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model to use",
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./grug.db",
        description="SQLAlchemy async database URL",
    )

    # ChromaDB (only relevant when vector_backend == 'chroma')
    chroma_persist_dir: str = Field(
        default="./chroma_data",
        description="Directory to persist ChromaDB data",
    )

    @property
    def vector_backend(self) -> str:
        """Derived from DATABASE_URL — 'pgvector' for Postgres, 'chroma' otherwise."""
        return "pgvector" if self.database_url.startswith("postgresql") else "chroma"

    # Scheduler
    scheduler_timezone: str = Field(
        default="UTC",
        description="Default timezone for scheduled tasks",
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

    # File storage — uploaded character sheets are persisted here.
    file_data_dir: str = Field(
        default="./file_data",
        description="Directory to store uploaded character sheet files",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
