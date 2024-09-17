# Grug Bot

[![Static Badge](https://img.shields.io/badge/Github-Public%20Repo-blue?logo=github&link=https%3A%2F%2Fgithub.com%2FFoehammer82%2FGrug)](https://github.com/Foehammer82/Grug)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![mypy](https://img.shields.io/badge/mypy-checked-blue)](https://github.com/python/mypy)

[**Documentation**](https://foehammer82.github.io/Grug)

## Project Roadmap / ToDo List

- [ ] alternative attendance tracking (by user poll)
    - as a user I expect to see a notification in discord that asks what day in the next n days work, I select all the
      ones that work. later, after other users have done the same I expect to get a poll with the days that work for
      everyone, I vote for 1, the winning date is picked and announced to everyone. or could possibly save a step if
      everyone picks a day that is the same, it just auto-selects the first day that everyone votes for Or just start
      with a discord poll tagging everyone with an option for every tuesday that month.
- [ ] backup and recovery functionality
    - ability to back up to a dedicated directory that a user could map to a volume to handle backups and recovery
- [ ] SMS Integration
    - Grug is able to send and receive texts
- [ ] Google Docs Integration
    - Grug is able to read and answer questions from a Google doc (session notes)
- [ ] Email Integration
    - Grug is able to send Emails
- [ ] create unit tests
- [ ] add metrics
    - track token/openai usage
    - track discord usage (incoming messages, outgoing messages)
    - track event data (attendance, food reminders, etc. for each event instance)
    - high level, want to track anything that has a cost, or potential cost, associated with it
    - track errors or issues that occur (i.e. logged errors, failed requests, etc.)
    - track image generation requests and usage
    - track user logins and admin actions
    - track the scheduler

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
