FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Silence hard-link warnings — cache and sync target are on different
# filesystems inside Docker, so uv must copy instead of link.
ENV UV_LINK_MODE=copy

# Install external dependencies only (no workspace packages yet).
# Bind mounts expose the lockfile and all pyproject.toml files to uv
# without writing them into the image layer, keeping this layer
# cache-friendly: it only re-runs when the lock or manifests change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=grug/pyproject.toml,target=grug/pyproject.toml \
    --mount=type=bind,source=api/pyproject.toml,target=api/pyproject.toml \
    uv sync --no-dev --frozen --no-install-workspace

# Copy only what the bot needs — api/, web/, docs/, tests/ etc. are excluded.
COPY grug/ grug/
COPY main.py main.py
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-dev --frozen

# Create data directories
RUN mkdir -p /app/chroma_data

# DATABASE_URL is intentionally NOT set here.
# Supply it via .env or docker-compose environment so the user controls
# whether they get SQLite or Postgres without rebuilding the image.
ENV CHROMA_PERSIST_DIR=/app/chroma_data

VOLUME ["/app/data", "/app/chroma_data"]

CMD ["uv", "run", "python", "main.py"]
