# Grug

A self-hosted AI agent for Discord, built to assist with TTRPGs and generally have a good time. Grug brings an AI companion powered by Claude into your server, with RAG document search, scheduled prompts, MCP tool support, and a web dashboard.

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (recommended for deployment)
- A [Discord bot token](https://discord.com/developers/applications)
- An [Anthropic API key](https://console.anthropic.com/)

### Running with Docker (recommended)

1. Copy the example env file and fill in your values:

   ```bash
   cp .env.example .env
   ```

2. Set the required variables in `.env`:

   ```env
   DISCORD_TOKEN=your_discord_bot_token
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

3. Start all services:

   ```bash
   docker compose up -d
   ```

   - Bot: runs in the background
   - API: http://localhost:8000
   - Web dashboard: http://localhost:3000

### Running locally (development)

```bash
uv sync               # install all dependencies (including dev)
cp .env.example .env   # fill in values
```

You need a running Postgres instance with pgvector. The dev compose file brings one up for you:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Or start just the database:

```bash
docker compose up -d postgres
```

Then run the bot:

```bash
uv run python main.py
```

---

## Configuration

All configuration is driven by environment variables (or a `.env` file). Key options:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | Yes | — | Discord bot token |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Anthropic model to use |
| `DATABASE_URL` | No | `postgresql+asyncpg://grug:grug@localhost:5432/grug` | SQLAlchemy async DB URL (Postgres + pgvector required) |
| `DEFAULT_TIMEZONE` | No | `UTC` | Default timezone for new guild configs and scheduled tasks |
| `MCP_SERVER_CONFIGS` | No | `[]` | JSON array of MCP server configs |
| `AGENT_CONTEXT_WINDOW` | No | `20` | Number of recent messages to keep in context |
| `AGENT_HISTORY_ARCHIVE_BATCH` | No | `10` | Overflow messages needed before archiving to RAG |
| `AGENT_HISTORY_MAX_SUMMARIES` | No | `100` | Max history summaries per channel in the vector store |
| `FLUSH_CHAT_HISTORY` | No | `false` | Archive all conversation history on startup |
| `LOG_LEVEL` | No | `INFO` | Logging level |

OAuth / Web dashboard variables (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `WEB_SECRET_KEY`, `WEB_CORS_ORIGINS`, `FRONTEND_URL`, `VITE_API_URL`) are documented in `.env.example`.

> **Deploying on a VPS or behind a domain?** Set `VITE_API_URL` to your public API URL (e.g. `https://api.yourdomain.com`). Unlike other env vars, this one is injected at container start rather than baked into the JS bundle — so you never need to rebuild the web image to change it.

---

## Project Structure

```
main.py               # Bot entry point
grug/
  agent/              # AI agent core (pydantic-ai) and system prompt
    tools/            # Agent tool modules (RAG, MCP, scheduling, glossary, characters)
  bot/                # Discord client and cogs
  character/          # Character sheet parsing and indexing
  config/             # Settings (pydantic-settings)
  db/                 # SQLAlchemy models and async session management
  rag/                # pgvector-backed RAG indexer, retriever, and embedder
  scheduler/          # APScheduler manager and task definitions
alembic/              # Alembic migration environment and versions
api/                  # FastAPI REST API (served separately)
web/                  # React + Vite web dashboard
scripts/              # Dev tooling (pre-commit hooks)
tests/                # Pytest test suite
```

## Database

Grug uses **Postgres with pgvector** — there is no SQLite mode. Alembic manages all schema migrations:

- Migrations run automatically on startup via `init_db()`.
- When you change an ORM model in `grug/db/models.py` or `grug/db/pg_models.py`, a pre-commit hook auto-generates the migration and pauses the commit for review.
- Manual migration commands use `uv run alembic` (see `.github/skills/alembic-migrations/SKILL.md` for the full workflow).

## Developer Notes

- **Dependencies**: managed with [uv](https://docs.astral.sh/uv/). Add packages with `uv add <pkg>` (or `uv add --dev <pkg>`). No `requirements.txt`.
- **Run tests**: `uv run pytest tests/`
- **Pre-commit**: `uv run pre-commit install` — hooks include ruff, pyupgrade, uv-lock, and Alembic autogenerate.
- The bot, API, and web are three separate services orchestrated via `docker-compose.yml`.
- MCP servers are configured as a JSON array in `MCP_SERVER_CONFIGS` — see `grug/config/settings.py` for the schema.
- Game-system-specific logic should live in clearly named modules under `grug/agent/tools/`.
