FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl

ARG WORKDIR=/app

WORKDIR $WORKDIR
ENV PYTHONPATH=$WORKDIR

# Install poetry
RUN pip install poetry
ENV POETRY_VIRTUALENVS_CREATE=false

# Install dependencies
COPY poetry.lock pyproject.toml $WORKDIR/
RUN poetry install --only=main

# Copy Alembic files
COPY alembic alembic
COPY alembic.ini alembic.ini

# Copy application files
COPY grug grug

EXPOSE 9000
ENV API_HOST="0.0.0.0"
ENV ENVIRONMENT="prd"

# Start the application
CMD poetry run python grug start

# Container Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD poetry run python grug health || exit 1
