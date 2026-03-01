FROM python:3.12-slim

WORKDIR /app

# Install uv for dependency management.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install project dependencies (includes the grug package).
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen || uv sync --no-dev

# Copy the full source tree — the API imports from the grug package.
COPY grug/ grug/
COPY api/ api/

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
