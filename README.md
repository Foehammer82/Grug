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
uv sync          # install all dependencies (including dev)
cp .env.example .env  # fill in values
uv run python main.py
```

---

## Configuration

All configuration is driven by environment variables (or a `.env` file). Key options:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | Yes | — | Discord bot token |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-3-5-sonnet-20241022` | Model to use |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./grug.db` | SQLAlchemy async DB URL |
| `CHROMA_PERSIST_DIR` | No | `./chroma_data` | ChromaDB storage directory |
| `SCHEDULER_TIMEZONE` | No | `UTC` | Default timezone for scheduled tasks |
| `MCP_SERVER_CONFIGS` | No | `[]` | JSON array of MCP server configs |

---

## Project Structure

```
main.py               # Bot entry point
grug/
  agent/              # AI agent core and tools (RAG, MCP, scheduling)
  bot/                # Discord client and cogs
  config/             # Settings (pydantic-settings)
  db/                 # SQLAlchemy models and session management
  rag/                # ChromaDB indexer and retriever
  scheduler/          # APScheduler manager and task definitions
api/                  # FastAPI REST API (served separately)
web/                  # React + Vite web dashboard
tests/                # Pytest test suite
```

## Developer Notes

- Run tests: `uv run pytest tests/`
- The bot, API, and web are three separate services orchestrated via `docker-compose.yml`
- Database migrations are handled automatically on startup via SQLAlchemy
- MCP servers are configured as a JSON array in `MCP_SERVER_CONFIGS` — see `grug/config/settings.py` for the schema
- Game-system-specific logic should live in clearly named modules under `grug/agent/tools/`
