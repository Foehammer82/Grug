FROM python:3.11

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

# Copy config files
COPY config config

# Copy application files
COPY grug_bot grug_bot

# Run the application
CMD poetry run python grug_bot
