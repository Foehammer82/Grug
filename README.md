# Grug Bot

[![Static Badge](https://img.shields.io/badge/Github-Public%20Repo-blue?logo=github&link=https%3A%2F%2Fgithub.com%2FFoehammer82%2FGrug)](https://github.com/Foehammer82/Grug)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![mypy](https://img.shields.io/badge/mypy-checked-blue)](https://github.com/python/mypy)

## Project Roadmap / ToDo List

### MVP Tasks

- [x] Grug is able to respond to discord messages
- [x] Grug is aware of DnD schedules and handles food reminders and who's on for food
- [x] Admin web-ui for managing the Grug app
- [x] embedded FastAPI application at `/api`
- [x] metrics endpoint
    - instrumented with prometheus https://github.com/trallnag/prometheus-fastapi-instrumentator
- [x] Grug is able to generate pictures in discord with Dall-E
- [x] Grug is able to handle DnD attendance tracking
- [x] secure the metrics endpoint so that it requires a key passed as an HTTP query parameter
- [x] implement discord oauth to enable discord user logins for the API and admin interface
    - https://discord.com/developers/docs/topics/oauth2
    - this will allow for users to be made admins, so they can log in to the admin interface

### Post-MVP Tasks

- [ ] backup and recovery functionality
    - ability to back up to a dedicated directory that a user could map to a volume to handle backups and recovery
- [ ] SMS Integration
    - Grug is able to send and receive texts
- [ ] Google Docs Integration
    - Grug is able to read and answer questions from a Google doc (session notes)
- [ ] Email Integration
    - Grug is able to send Emails
- [ ] create unit tests

### Tasks that must be complete before Grug can be used publicly

- [ ] deploy Grug to dockerhub, and/or make image available in public repo
- [ ] setup mkdocs documentation
    - quick-start docs focused on deploying with Docker

### Future Consideration Tasks (May or May Not Be Implemented...)

- [ ] plugins framework
    - create a way for users to create functions that Grug can use as tools
    - was thinking it could be cool to utilize jupyter notebooks that can be toggled through the admin interface
    - otherwise, have a way to map a directory that has `.py` files with functions, that are again, parsed and
      toggleable through the admin interface would work
    - (maybe both solutions above are good? "por que no los dos?")
- [ ] add ability for Grug to moderate a discord server
    - I'm thinking of having levels of moderation, from sending warning about inappropriate messages to full on
      blocking or banning players
    - for reference: https://platform.openai.com/docs/guides/moderation
