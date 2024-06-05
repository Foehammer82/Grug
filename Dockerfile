FROM python:3.11-slim

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

# Run DB migrations and then start the application
CMD alembic upgrade head && poetry run python grug
