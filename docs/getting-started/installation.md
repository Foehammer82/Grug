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

    No extra config needed. Grug uses a local SQLite database for storage.

    ```dotenv
    # .env — leave DATABASE_URL unset or use:
    DATABASE_URL=sqlite+aiosqlite:///./data/grug.db
    ```

    !!! warning "Persist your data"
        The image does **not** declare Docker volumes automatically. If you want your SQLite database to survive container restarts, mount `/app/data` from your host or a named volume:

        ```yaml
        # docker-compose.yml (grug service)
        volumes:
          - grug_db:/app/data  # SQLite database
        ```

        Without this mount all data is lost when the container is removed.

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
| `web` | `http://localhost:3000` | Web dashboard (nginx) |
| `postgres` | `localhost:5432` | Database |

To use the Vite hot-reload dev server instead of nginx, activate the `dev` profile:

```bash
docker compose --profile dev up -d
```

This replaces the nginx `web` service with the Vite dev server on `http://localhost:5173` and automatically reloads the API on Python file changes.

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

## Deploying with prebuilt images

If you prefer not to build from source, published images are available on GHCR. Create a `docker-compose.yml` like the following and adjust the environment variables to match your setup:

```yaml
services:
  postgres:
    image: ghcr.io/foehammer82/grug-postgres:latest
    restart: unless-stopped
    environment:
      POSTGRES_DB: grug
      POSTGRES_USER: grug
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U grug -d grug"]
      interval: 10s
      timeout: 5s
      retries: 5

  bot:
    image: ghcr.io/foehammer82/grug:latest
    restart: unless-stopped
    volumes:
      - files:/app/file_data
    environment:
      DATABASE_URL: postgresql+asyncpg://grug:${POSTGRES_PASSWORD}@postgres:5432/grug
      FILE_DATA_DIR: /app/file_data
      DISCORD_TOKEN: ${DISCORD_TOKEN}
      DISCORD_CLIENT_ID: ${DISCORD_CLIENT_ID}
      DISCORD_CLIENT_SECRET: ${DISCORD_CLIENT_SECRET}
      DISCORD_REDIRECT_URI: ${DISCORD_REDIRECT_URI}
      WEB_SECRET_KEY: ${WEB_SECRET_KEY}
      WEB_CORS_ORIGINS: ${WEB_CORS_ORIGINS:-https://your-domain.example.com}
      FRONTEND_URL: ${FRONTEND_URL:-https://your-domain.example.com}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-claude-haiku-4-5}
      ANTHROPIC_BIG_BRAIN_MODEL: ${ANTHROPIC_BIG_BRAIN_MODEL:-claude-sonnet-4-6}
      DEFAULT_TIMEZONE: ${DEFAULT_TIMEZONE:-America/Chicago}
      GRUG_SUPER_ADMIN_IDS: ${GRUG_SUPER_ADMIN_IDS}
    depends_on:
      postgres:
        condition: service_healthy

  api:
    image: ghcr.io/foehammer82/grug-api:latest
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://grug:${POSTGRES_PASSWORD}@postgres:5432/grug
      DISCORD_TOKEN: ${DISCORD_TOKEN}
      DISCORD_CLIENT_ID: ${DISCORD_CLIENT_ID}
      DISCORD_CLIENT_SECRET: ${DISCORD_CLIENT_SECRET}
      DISCORD_REDIRECT_URI: ${DISCORD_REDIRECT_URI}
      WEB_SECRET_KEY: ${WEB_SECRET_KEY}
      WEB_CORS_ORIGINS: ${WEB_CORS_ORIGINS:-https://your-domain.example.com}
      FRONTEND_URL: ${FRONTEND_URL:-https://your-domain.example.com}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-claude-haiku-4-5}
      ANTHROPIC_BIG_BRAIN_MODEL: ${ANTHROPIC_BIG_BRAIN_MODEL:-claude-sonnet-4-6}
      DEFAULT_TIMEZONE: ${DEFAULT_TIMEZONE:-America/Chicago}
      GRUG_SUPER_ADMIN_IDS: ${GRUG_SUPER_ADMIN_IDS}
    ports:
      - "8000:8000"
    depends_on:
      - bot
      - postgres

  web:
    image: ghcr.io/foehammer82/grug-web:latest
    restart: unless-stopped
    environment:
      VITE_API_URL: ${API_URL:-https://your-api-domain.example.com}
    ports:
      - "3000:80"
    depends_on:
      - api

volumes:
  files:
  postgres-data:
```

Set all variables in a `.env` file alongside the compose file, or pass them as environment variables. See the [Configuration reference](configuration.md) for the full list.

!!! tip "Reverse proxy"
    In production, put a reverse proxy (Caddy, nginx, Traefik) in front of the `api` and `web` services rather than exposing ports directly. Set `WEB_CORS_ORIGINS` and `FRONTEND_URL` to the public URL of your web service, and `DISCORD_REDIRECT_URI` to your OAuth callback URL.

---

!!! note "Ports in use?"
    If ports 3000 or 8000 clash with existing services, edit the `ports:` entries in `docker-compose.yml` before starting.
