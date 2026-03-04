# Grug

!!! warning "🚧 Active Development"
    Grug is under **active development**. Features, APIs, and configuration options may change at any time.
    Full documentation is coming soon — for now this page provides a high-level overview.

---

**Grug** is a self-hosted AI companion built for TTRPGs. Powered by Claude (Anthropic), Grug lives in your Discord server and helps your table with lore tracking, rules lookups, world-building, scheduling, and whatever else you throw at him.

All data stays on your own infrastructure — no third-party services beyond the AI API itself.

---

## Features

| Feature | Where |
|---|---|
| 💬 AI chat with full context awareness | Discord — mention `@Grug` |
| 📖 TTRPG rules lookups (PF2e & D&D 5e SRD) | Discord + Web UI |
| 📖 Server & channel glossaries | Discord slash commands + Web UI |
| 📄 Document upload & RAG retrieval | Discord commands + Web UI |
| 📅 Scheduled reminders & recurring tasks | Discord commands + Web UI |
| 🎲 Campaign & character management | Discord + Web UI |
| 🗒️ Session notes with AI synthesis | Web UI |
| ⚙️ Per-server configuration | Web UI |
| 🔌 Extensible via MCP tool servers | Config file |

---

## Self-Hosting

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- A [Discord bot token](https://discord.com/developers/applications) (with **Message Content Intent** and **Server Members Intent** enabled)
- An [Anthropic API key](https://console.anthropic.com/)

### Quick Start

1. Clone the repository and copy the example env file:

    ```bash
    git clone https://github.com/Foehammer82/Grug.git
    cd Grug
    cp .env.example .env
    ```

2. Fill in the required variables in `.env`:

    ```env
    DISCORD_TOKEN=your_discord_bot_token
    ANTHROPIC_API_KEY=your_anthropic_api_key
    ```

3. Start all services:

    ```bash
    docker compose up -d
    ```

    | Service | URL |
    |---|---|
    | Web dashboard | http://localhost:3000 |
    | REST API | http://localhost:8000 |

That's it! Once the bot is online, invite it to your Discord server and mention `@Grug` to start chatting.

### Key Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Discord bot token |
| `ANTHROPIC_API_KEY` | ✅ | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Claude model to use |
| `DATABASE_URL` | No | `postgresql+asyncpg://grug:grug@localhost:5432/grug` | Postgres + pgvector connection string |
| `DEFAULT_TIMEZONE` | No | `UTC` | Default timezone for scheduled tasks |
| `DISCORD_CLIENT_ID` | No* | — | Required for web dashboard OAuth login |
| `DISCORD_CLIENT_SECRET` | No* | — | Required for web dashboard OAuth login |

> See `.env.example` in the repository for the full list of options.

!!! tip "Self-hosted and private"
    Grug stores all data locally using Postgres with pgvector. Your conversation history, glossary, documents, and configuration never leave your own infrastructure.
