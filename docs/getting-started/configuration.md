# Getting Started — Configuration

All Grug settings are read from environment variables at startup. The recommended approach is to put them in a `.env` file at the project root — Docker Compose loads this file automatically.

---

## Required settings

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token from the Developer Portal. |
| `ANTHROPIC_API_KEY` | Your Anthropic API key from [console.anthropic.com](https://console.anthropic.com/). |

---

## Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/grug.db` | Async SQLAlchemy database URL. Use the SQLite default for a single-node setup, or a `postgresql+asyncpg://` URL to use the pgvector backend. |
| `POSTGRES_USER` | `grug` | Postgres username (PostgreSQL profile only). |
| `POSTGRES_PASSWORD` | `grug` | Postgres password. **Change this in production.** |
| `POSTGRES_DB` | `grug` | Postgres database name. |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | Where ChromaDB stores its data on disk. Only used when `DATABASE_URL` points to SQLite. |

!!! info "Vector backend is auto-detected"
    When `DATABASE_URL` contains `postgresql`, Grug uses pgvector for all embedding storage. Otherwise it uses ChromaDB. You do not need to set anything extra.

---

## AI model

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | The Anthropic model Grug uses for all responses. Replace with any model your API key has access to (e.g. `claude-opus-4-5`). |
| `AGENT_MAX_ITERATIONS` | `10` | Maximum number of tool-calling rounds Grug will perform per message before returning a response. Increase if Grug is cutting off complex tasks. |
| `AGENT_CONTEXT_WINDOW` | `20` | Number of recent messages kept in the active context window per channel. Older messages are archived to the vector store automatically. |
| `AGENT_HISTORY_ARCHIVE_BATCH` | `10` | Minimum number of overflow messages required before the archiver runs. |
| `AGENT_HISTORY_MAX_SUMMARIES` | `100` | Maximum number of per-channel history summary chunks stored in the vector store. |

---

## Discord bot

| Variable | Default | Description |
|---|---|---|
| `DISCORD_PREFIX` | `!` | Command prefix for all prefix-style commands (e.g. `!grug_status`). |

---

## Scheduling

| Variable | Default | Description |
|---|---|---|
| `SCHEDULER_TIMEZONE` | `UTC` | Default timezone for scheduled tasks when no guild-specific timezone is set. Use IANA tz names (e.g. `America/New_York`). |

---

## Files

| Variable | Default | Description |
|---|---|---|
| `FILE_DATA_DIR` | `./file_data` | Directory on disk where uploaded character sheet and other files are stored. |

---

## MCP tool extensions

| Variable | Default | Description |
|---|---|---|
| `MCP_SERVER_CONFIGS` | `[]` | JSON array of MCP server configuration objects. See the [MCP Tools guide](../guides/mcp-tools.md) for the full schema and examples. |

---

## Observability

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Python log level for all Grug services. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## Example `.env` file

```dotenv title=".env"
# ── Required ──────────────────────────────────────────────────────────────
DISCORD_TOKEN=your-discord-bot-token
ANTHROPIC_API_KEY=sk-ant-...

# ── Database (SQLite profile — default) ───────────────────────────────────
# DATABASE_URL=sqlite+aiosqlite:///./data/grug.db

# ── Database (PostgreSQL profile) ─────────────────────────────────────────
# DATABASE_URL=postgresql+asyncpg://grug:grug@postgres:5432/grug
# POSTGRES_USER=grug
# POSTGRES_PASSWORD=change-me
# POSTGRES_DB=grug

# ── Model ─────────────────────────────────────────────────────────────────
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
AGENT_MAX_ITERATIONS=10
AGENT_CONTEXT_WINDOW=20

# ── Bot ───────────────────────────────────────────────────────────────────
DISCORD_PREFIX=!

# ── Misc ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```
