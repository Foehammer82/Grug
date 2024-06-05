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
- [ ] need an easy way to make nice UIs for Grug that can be easily integrated with the FastAPI backend
    - wait until there is a clear need for a UI endpoint first before just implementing this. i have a feeling we're
      going to want some basic form pages so that Grug can send users to something easy to fill out or interact with
      when conversational based inputs aren't optimal (i.e. allowing a user to change their profile or something, i
      could see sending a link with a unique key as a param or something with one time access and possibly a TTL to
      enable them to easily adjust stuff)
    - I could also see having dedicated UI's with sessions and logins would make sense too (specifically for user
      settings, like changing a password or linking accounts (i.e. link discord to phone number or something))
- [ ] Grug is able to handle DnD attendance tracking
- [ ] Grug is able to read and answer questions from a Google doc (session notes)
- [ ] Grug is able to generate pictures in discord with DALLE
- [ ] Grug can listen to a discord voice channel and transcribe the conversation (possibly even respond in it)
- [ ] Grug is able to send and receive texts
- [ ] deploy Grug to dockerhub (or make image available in public repo) and include instructions for use
- [ ] setup mkdocs documentation focused on both deploying and using Grug as is, and for how to fork and extend Grug for
  use in custom applications
- [ ] ability to export and import a grug database for backups and migrations
- [ ] ability to back up to a dedicated directory that a user could map to a volume to handle backups and recovery

### Nice To Have One-Day Features

- [ ] implement discord oauth to enable discord user logins (https://discord.com/developers/docs/topics/oauth2)
