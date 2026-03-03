FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (tesseract + poppler for OCR on uploaded PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management.
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
    uv sync --all-packages --no-dev --frozen --no-install-workspace

# Copy the full source tree — the API imports from the grug package.
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
COPY grug/ grug/
COPY api/ api/
# Root pyproject.toml and uv.lock are not copied into this image but uv still
# needs them to resolve the project root; use bind mounts so they're visible
# at sync time without adding them to the image layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --all-packages --no-dev --frozen

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
