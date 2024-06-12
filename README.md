# Grug Bot

[![Static Badge](https://img.shields.io/badge/Github-Public%20Repo-blue?logo=github&link=https%3A%2F%2Fgithub.com%2FFoehammer82%2FGrug)](https://github.com/Foehammer82/Grug)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![mypy](https://img.shields.io/badge/mypy-checked-blue)](https://github.com/python/mypy)

## Project Roadmap / ToDo List

- [x] Grug is able to respond to discord messages
- [x] Grug is aware of DnD schedules and handles food reminders and who's on for food
- [x] embedded FastAPI and admin page
- [x] migrate legacy Grug models to new models and build more robust food reminder and event system
- [x] metrics endpoint (i.e. https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [x] Grug is able to generate pictures in discord with Dall-E
- [ ] Grug is able to handle DnD attendance tracking
- [ ] Grug is able to send and receive texts
- [ ] Grug is able to read and answer questions from a Google doc (session notes)
- [ ] deploy Grug to dockerhub (or make image available in public repo) and include instructions for use
- [ ] setup mkdocs documentation focused on both deploying for self-hosting and forking for personal use
- [ ] ability to back up to a dedicated directory that a user could map to a volume to handle backups and recovery

### Tech-Debt Tasks

- [ ] create unit tests (should have started with this, but was having more fun messing around)

### Nice To Have One-Day Features

- [ ] implement discord oauth to enable discord user logins (https://discord.com/developers/docs/topics/oauth2)
- [ ] implement moderating into Grug so that he can monitor, respond to, and take action against "harmful" text
    - https://platform.openai.com/docs/guides/moderation

### Notes

- checkout Dify as a LLM Application Development platform:  https://docs.dify.ai/getting-started/install-self-hosted/docker-compose
