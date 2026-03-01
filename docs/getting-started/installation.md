# Getting Started — Installation

This guide walks you through running Grug for the first time using Docker Compose.

---

## Prerequisites

Before you begin, make sure you have:

- **Docker** and **Docker Compose** — [docs.docker.com/get-docker](https://docs.docker.com/get-docker/)
- A **Discord application & bot token** — [discord.com/developers](https://discord.com/developers/applications)
- An **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com/)

---

## Step 1 — Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a **New Application**.
2. Navigate to **Bot** and click **Add Bot**.
3. Under **Token**, click **Reset Token** and copy the value — this is your `DISCORD_TOKEN`.
4. Enable the following **Privileged Gateway Intents**:
    - **Message Content Intent** (required for prefix commands)
    - **Server Members Intent** (required for guild membership checks)
5. Go to **OAuth2 → URL Generator**, tick `bot` and `applications.commands`, then choose the permissions your server needs (at minimum **Send Messages**, **Read Message History**, **Embed Links**).
6. Open the generated URL to invite Grug to your server.

---

## Step 2 — Clone the repository

```bash
git clone https://github.com/yourorg/grug.git
cd grug
```

---

## Step 3 — Configure environment variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```dotenv
DISCORD_TOKEN=your-discord-bot-token-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

See the full [Configuration reference](configuration.md) for every available option.

---

## Step 4 — Choose a database profile

Grug supports two deployment profiles:

=== "SQLite (default — simplest)"

    No extra config needed. Grug uses a local SQLite database and ChromaDB for vector storage.

    ```dotenv
    # .env — leave DATABASE_URL unset or use:
    DATABASE_URL=sqlite+aiosqlite:///./data/grug.db
    CHROMA_PERSIST_DIR=/app/chroma_data
    ```

=== "PostgreSQL + pgvector (production)"

    Use this profile for better performance and multi-process safety.

    ```dotenv
    # .env
    DATABASE_URL=postgresql+asyncpg://grug:grug@postgres:5432/grug
    POSTGRES_USER=grug
    POSTGRES_PASSWORD=a-strong-password
    POSTGRES_DB=grug
    ```

    The `postgres` service in `docker-compose.yml` is already configured for pgvector. Just make sure `POSTGRES_PASSWORD` matches in both the `grug/api` env and the `postgres` service.

---

## Step 5 — Start Grug

```bash
docker compose up -d
```

This starts all four services:

| Service | URL | Purpose |
|---|---|---|
| `grug` | — | Discord bot process |
| `api` | `http://localhost:8000` | REST API |
| `web` | `http://localhost:3000` | Web dashboard |
| `postgres` | `localhost:5432` | Database (PostgreSQL profile only) |
| `docs` | `http://localhost:8080` | This documentation site |

Check that everything started cleanly:

```bash
docker compose ps
docker compose logs grug --tail 20
```

You should see a line like:

```
grug  | INFO  Logged in as Grug#1234 (id: 123456789)
```

---

## Step 6 — Verify the bot

In any Discord channel where Grug has **Send Messages** permission, type:

```
!grug_status
```

Grug should respond with a status embed showing the model name and scheduler state.

---

## Updating Grug

```bash
git pull
docker compose build
docker compose up -d
```

---

!!! note "Ports in use?"
    If ports 3000, 8000, or 8080 clash with existing services, edit the `ports:` entries in `docker-compose.yml` before starting.
