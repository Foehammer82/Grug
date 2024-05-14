# Grug Bot

[![Static Badge](https://img.shields.io/badge/Github-Public%20Repo-blue?logo=github&link=https%3A%2F%2Fgithub.com%2FFoehammer82%2FGrug)](https://github.com/Foehammer82/Grug)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Project Roadmap / ToDo List

- [x] Grug is able to respond to discord messages
- [x] Grug is aware of DnD schedules and handles food reminders and who's on for food
- [x] embedded FastAPI and admin page
- [ ] migrate legacy Grug models to new models and build more robust food reminder and event system
- [ ] need an easy way to make nice UIs for Grug that can be easily integrated with the FastAPI backend
- [ ] Grug is able to handle DnD attendance tracking (stretch goal)
- [ ] Keep record of group chats in a database and create tooling for Grug to be able to search that
- [ ] Grug is able to read and answer questions from a Google doc (session notes)
- [ ] Grug is able to generate pictures in discord with DALLE
- [ ] Grug can listen to a discord voice channel and transcribe the conversation (possibly even respond in it)
- [ ] Grug is able to send and receive texts
- [ ] Grug is able to create scheduled reminders for things
- [ ] deploy Grug to dockerhub (or make image available in public repo) and include instructions for use
    - these instructions should be clear and complete enough that someone could mindlessly follow them with no previous
      experience and get a Grug of their own deployed
- [x] metrics endpoint (i.e. https://github.com/trallnag/prometheus-fastapi-instrumentator)

### Nice To Have One-Day Features

- [ ] implement discord oauth to enable discord user logins (https://discord.com/developers/docs/topics/oauth2)
