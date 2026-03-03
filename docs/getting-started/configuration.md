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

!!! info "Vector embeddings"
    Grug uses pgvector for all embedding storage and requires a Postgres deployment. The ChromaDB library is still installed (its ONNX model generates embeddings), but it is not used as a vector database and writes nothing to disk.

---

## AI model

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | The Anthropic model Grug uses for all responses. Replace with any model your API key has access to (e.g. `claude-opus-4-5`). |
| `AGENT_MAX_ITERATIONS` | `10` | Maximum number of tool-calling rounds Grug will perform per message before returning a response. Increase if Grug is cutting off complex tasks. |
| `AGENT_CONTEXT_WINDOW` | `20` | Number of recent messages kept in the active context window per channel. Older messages are archived to the vector store automatically. |
| `AGENT_CONTEXT_LOOKBACK_DAYS` | `30` | How far back (in days) Grug reads passive message history when no per-channel cutoff is set. |
| `AGENT_HISTORY_ARCHIVE_BATCH` | `10` | Minimum number of overflow messages required before the archiver runs. |
| `AGENT_HISTORY_MAX_SUMMARIES` | `100` | Maximum number of per-channel history summary chunks stored in the vector store. |

---

## General

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_TIMEZONE` | `UTC` | Default timezone applied to new guild configs and scheduled tasks. Use IANA tz names (e.g. `America/New_York`). |

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

## Web dashboard

These variables affect the API and the React web UI.

| Variable | Default | Description |
|---|---|---|
| `DISCORD_CLIENT_ID` | — | Discord OAuth2 application client ID. Required for web login. |
| `DISCORD_CLIENT_SECRET` | — | Discord OAuth2 client secret. |
| `DISCORD_REDIRECT_URI` | `http://localhost:8000/auth/discord/callback` | OAuth2 redirect URI — must match what is set in the Discord Developer Portal. |
| `WEB_SECRET_KEY` | — | Secret key used to sign session cookies. **Use a long random string in production.** |
| `WEB_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed CORS origins for the API. |
| `FRONTEND_URL` | `http://localhost:3000` | URL the API redirects to after OAuth login. |
| `VITE_API_URL` | `http://localhost:8000` | URL the **browser** uses to reach the API. Injected at container start — never baked into the JS bundle — so you can change it without rebuilding the image. Set this to your public API URL when hosting on a VPS or behind a domain (e.g. `https://api.yourdomain.com`). |

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

# ── Misc ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```
