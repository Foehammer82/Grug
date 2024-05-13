# Local Development

## Setup

1. Set up the following:
    - Discord Application
        1. [Discord Developer Portal](https://discord.com/developers/applications)
        2. TODO: write out detailed instructions for getting the Discord application setup
            - The long term plan is to make Grug not tied to one message service, so this will turn into a
              recommendation and not a requirement at some point, as we will likely create a simple web interface to
              interact with Grug, and then create configs to plug him into other services like Discord, Slack, Teams,
              etc.
    - obtain an OpenAI API Key
        1. [OpenAI API Signup](https://openai.com/index/openai-api/)
2. Install:
    - [Docker](https://docs.docker.com/get-docker/)
    - [Docker Compose](https://docs.docker.com/compose/install/)
    - [Python](https://www.python.org/downloads/)
    - [Poetry](https://python-poetry.org/docs/#installation)
3. Clone this repository.
4. Run `poetry install` to install dependencies.
5. Run `pre-commit install` to install pre-commit hooks.
6. Run `docker-compose up -d postgres` to start the database.
7. Set up your config file by following instructions in the `config/secrets.example.env` file.
    - NOTE
8. Start the docker postgres container: `docker-compose up -d postgres`
9. run initial alembic database migrations:
    1. `poetry run alembic upgrade head`
    2. `poetry run alembic revision --autogenerate -m "Initial migration"`

## Poetry Reference

- `poetry add <package>` to add a new dependency.
    - `poetry add -G dev <package>` to add a new dev dependency.
    - `poetry add -G docs <package>` to add a new docs dependency.
- `poetry install` to install dependencies.
- `poetry update` to update dependencies.

## Alembic Reference

[Official Docs](https://alembic.sqlalchemy.org/en/latest/tutorial.html#running-our-first-migration)

- first migration: `alembic upgrade head`
- create a new migration: `alembic revision --autogenerate -m "migration message"`
    - then run the migration: `alembic upgrade head`
