# Grug Bot

Test repo mirror 1

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Project Roadmap

- [x] Grug is able to respond to discord messages
- [x] Grug is aware of DnD schedules and handles food reminders and who's on for food
- [ ] Grug is able to handle DnD attendance tracking (stretch goal)
- [ ] Grug is able to draw pictures (stretch goal)
- [ ] Grug is able to send and receive texts
- [ ] Grug is able to create scheduled reminders for things
- [ ] deploy Grug to dockerhub (or make image available in public repo) and include instructions for use

## Development

### Setup

1. Install:
    - [Docker](https://docs.docker.com/get-docker/)
    - [Docker Compose](https://docs.docker.com/compose/install/)
    - [Poetry](https://python-poetry.org/docs/#installation)
2. Clone this repository.
3. Run `poetry install` to install dependencies.
4. Run `pre-commit install` to install pre-commit hooks.
5. Run `docker-compose up -d` to start the database.

### Poetry Reference

- `poetry add <package>` to add a new dependency.
    - `poetry add -G dev <package>` to add a new dev dependency.
    - `poetry add -G docs <package>` to add a new docs dependency.
- `poetry install` to install dependencies.
- `poetry update` to update dependencies.

### Alembic Reference

[Official Docs](https://alembic.sqlalchemy.org/en/latest/tutorial.html#running-our-first-migration)

- first migration: `alembic upgrade head`
- create a new migration: `alembic revision --autogenerate -m "migration message"`
    - then run the migration: `alembic upgrade head`

## References

- [discord.py](https://github.com/Rapptz/discord.py)
- [Rocketry](https://rocketry.readthedocs.io/en/stable/index.html)
- [SQLModel](https://sqlmodel.tiangolo.com/)
