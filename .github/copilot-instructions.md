# Copilot Instructions for Grug

## Project Overview

Grug is a self-hosted AI agent designed to assist with TTRPGs (Tabletop Role-Playing Games) and generally having a good time. The project aims to provide an interactive, helpful companion for tabletop gaming sessions, world-building, rule lookups, and storytelling.

## Goals and Priorities

- Keep the codebase simple, readable, and maintainable.
- Prioritize features that directly enhance the TTRPG experience (e.g., dice rolling, rule lookups, NPC generation, encounter tables).
- Prefer self-hosted, privacy-respecting solutions over third-party SaaS dependencies where practical.
- Favor user experience: responses should be fun, flavorful, and in the spirit of tabletop gaming.

## Architecture and Tech Stack

- This repository is in early stages; consult the README and any source files for the current stack.
- When adding features, prefer lightweight, dependency-minimal approaches.
- Document any new integrations or external services in the README.

## Coding Standards

- Write clear, self-documenting code with descriptive variable and function names.
- Add docstrings or comments for non-obvious logic, especially for AI/agent behaviour.
- Keep functions small and single-purpose.
- Avoid hardcoding configuration values; use environment variables or config files.

## Tooling and Environment

- This project uses **[uv](https://docs.astral.sh/uv/)** for dependency management and running Python.
- All dependencies are declared in `pyproject.toml` only — there is no `requirements.txt` and one must never be created.
- Dev dependencies (pytest, etc.) live in the `[dependency-groups] dev` section of `pyproject.toml`.
- Always run Python commands with `uv run` (e.g. `uv run pytest tests/`, `uv run python main.py`).
- Add new dependencies with `uv add <package>` (or `uv add --dev <package>` for dev-only).

## Testing

- Use **pytest** for all tests (never `unittest.TestCase` subclasses).
- Use pytest fixtures — shared fixtures go in `tests/conftest.py`.
- Write tests for all new features and bug fixes.
- Tests should cover both happy paths and edge cases.
- Run existing tests before submitting changes: `uv run pytest tests/`.

## Database Migrations (Alembic)

Alembic is used **only for Postgres deployments**. SQLite uses `create_all` and never needs migrations.

### Rules
- **Any time an ORM model changes** (in `grug/db/models.py` or `grug/db/pg_models.py`), a new migration must be generated and committed alongside the model change.
- Never alter the database schema by hand — always go through Alembic.
- Always review auto-generated migration files before committing; autogenerate misses `Vector` columns, `IVFFlat` indexes, and `CREATE EXTENSION` statements — add those manually.
- Use `uv run alembic` for all Alembic commands (never bare `alembic`).

### Workflow for schema changes
1. Update the ORM model in `grug/db/models.py` or `grug/db/pg_models.py`.
2. Auto-generate a migration: `uv run alembic revision --autogenerate -m "brief_description"`
3. Review and edit the generated file in `alembic/versions/`.
4. Apply locally: `uv run alembic upgrade head`
5. Verify: `uv run alembic current`
6. Test round-trip: `uv run alembic downgrade -1` then `uv run alembic upgrade head`
7. Commit both the model change and the migration file together.

### Checking migration state
```bash
uv run alembic current        # what revision the DB is at
uv run alembic history --verbose  # full history
uv run alembic check          # fail if models have un-migrated changes (needs DB)
```

For the full command reference and pgvector-specific patterns, consult the `alembic-migrations` agent skill (`.github/skills/alembic-migrations/SKILL.md`).

## Forbidden Practices

- Do not introduce unnecessary dependencies or frameworks.
- Do not commit secrets, API keys, or credentials to the repository.
- Do not break backward compatibility without a clear migration path and documentation.

## Domain Concepts — Context Awareness

Grug passively logs **every** non-bot guild message to `conversation_messages` with `is_passive=True` so he stays context-aware in channels even when not @mentioned. When he actually responds, the message is saved with `is_passive=False` (the default).

### Context Cutoff — Precedence

Three levels of context cutoff control how far back Grug reads history:

| Level | Model field | Scope |
|---|---|---|
| Per-channel | `ChannelConfig.context_cutoff` | Highest priority; overrides guild |
| Per-guild | `GuildConfig.context_cutoff` | Server-wide default |
| Per-user (DMs) | `UserProfile.dm_context_cutoff` | DM sessions only |

`None` at any level means "no cutoff — load all available history."  The effective cutoff is resolved in `_get_effective_context_cutoff()` in `grug/bot/cogs/ai_chat.py` and passed to `GrugAgent.respond()` → `_load_history()`.

### ChannelConfig model

`ChannelConfig` (table `channel_configs`) stores per-channel settings:
- `always_respond: bool` — replaces the old in-memory `_ALWAYS_RESPOND_CHANNELS` set; persists across restarts
- `context_cutoff: datetime | None` — per-channel cutoff override
- `guild_id` FK → `guild_configs.guild_id`
- `channel_id` unique index

The `/chat_here` slash command now reads/writes this table instead of an in-memory set.

## Domain Concepts — Rule Sources

Grug can look up TTRPG rules on demand via the `lookup_ttrpg_rules` agent tool (`grug/agent/tools/rules_tools.py`).  The data model has two layers:

### Built-in sources
Defined as a static list in `grug/rules/sources.py`.  Three are built-in: `aon_pf2e` (Archives of Nethys — scrapes the search page), `srd_5e` (dnd5eapi.co JSON API), and `open5e` (Open5e JSON API).

Guild admins can disable any built-in per-server.  Overrides are stored in the `guild_builtin_overrides` table (`GuildBuiltinOverride` model) keyed by `source_id`.  No row = built-in is **enabled** (safe default).

### Custom sources
Stored in the `rule_sources` table (`RuleSource` model) with `guild_id`, `name`, `url`, `system` (nullable), `notes` (nullable), and `enabled`.  Custom sources **are not scraped** — Grug cites the URL so players look it up themselves.  A `system` of `None` means "all systems".

### Web UI
The Config page has sub-tabs: **Server** | **Channels** | **Rule Sources**.  Sub-tabs are MUI `<Tabs>` inside `GuildConfigPage.tsx` — they do **not** add a new GuildLayout-level tab.

### API
- `GET  /api/guilds/{id}/rule-sources/builtins` — list builtins with effective enabled state
- `PATCH /api/guilds/{id}/rule-sources/builtins/{source_id}` — toggle a builtin
- `GET  /api/guilds/{id}/rule-sources` — list custom sources
- `POST /api/guilds/{id}/rule-sources` — add a custom source
- `PATCH /api/guilds/{id}/rule-sources/{source_id}` — update a custom source
- `DELETE /api/guilds/{id}/rule-sources/{source_id}` — remove a custom source

## Domain Concepts — Scheduled Tasks

**Reminders and scheduled tasks are the same concept.** There is no separate `Reminder` model. Everything lives in the `ScheduledTask` ORM model (`grug/db/models.py`, table `scheduled_tasks`) with a `type` discriminator:

| `type` | Trigger | Post-fire behaviour |
|---|---|---|
| `'once'` | Fires once at `fire_at` (datetime) | `enabled` set to `False`, `last_run` updated |
| `'recurring'` | Fires on `cron_expression` (5-field UTC cron) | `last_run` updated; keeps running |

Key points:
- The agent creates both types via a **single tool**: `create_scheduled_task` (in `grug/agent/tools/scheduling_tools.py`). Pass `fire_at` for one-shot, `cron_expression` for recurring.
- Execution is handled by a **single callback**: `execute_scheduled_task(task_id)` (in `grug/scheduler/tasks.py`). Never add a second callback function for task execution.
- The scheduler sync (`grug/scheduler/sync.py`) re-registers **both** types on startup so neither type is lost on restart.
- **Never** add a separate `Reminder` model, `send_reminder` function, or `create_reminder` agent tool. Always extend `ScheduledTask`.
- `name` and `cron_expression` are nullable columns; `name` auto-defaults to first 80 chars of `prompt` for one-shot tasks.

## API Patterns (FastAPI)

### PATCH endpoints — nullable field clearing
**Never** gate an optional field update with `if body.field is not None`. This silently swallows intentional null-clears. Use `model_fields_set` instead:

```python
# WRONG — cannot clear a field to null
if body.announce_channel_id is not None:
    cfg.announce_channel_id = body.announce_channel_id

# CORRECT — handles explicit null
if "announce_channel_id" in body.model_fields_set:
    cfg.announce_channel_id = body.announce_channel_id
```

### Discord bot token
The settings object has two token fields: `discord_token` (used by the bot) and `discord_bot_token` (used by the API for Discord proxy calls). In practice they are the same credential. API routes that call the Discord REST API must fall back to `discord_token` when `discord_bot_token` is empty:
```python
bot_token = settings.discord_bot_token or settings.discord_token
```

### Discord system channel
`GET /guilds/{id}` from the Discord API returns `system_channel_id` — the channel the server admin designated for system messages (joins, boosts, etc). Use this as the default `announce_channel_id` when none is configured.

## Capturing Pitched Ideas

There are two roadmap documents with distinct purposes:

- **`roadmap.md`** (repo root) — informal scratch pad for spitballing. Whenever the user pitches an idea, floats a "what if", or mentions a feature they'd like to explore someday, add it to the appropriate section of this file immediately, even if it's rough or half-formed.
- **`docs/` roadmap** — official planned work that has been agreed on and is intended to ship. Do not add speculative ideas here.

When an idea is promoted from brainstorming to "we're actually doing this", move it out of `roadmap.md` and into the appropriate docs page.

## Keeping These Instructions Current

When the user corrects a response, points out a mistake, or shares an important pattern, best practice, or project convention, treat it as a signal to update this file and/or the relevant customization artifact (see section below). Specifically:

- If the correction represents a **standing rule, preference, or project context** (e.g. "we always use X", "never do Y in this codebase"), add it to the appropriate section of this file immediately.
- If the correction describes a **repeatable task or workflow** (e.g. "here is how we scaffold a new cog"), consider creating or updating a prompt file under `.github/prompts/` instead.
- If the correction defines a **reusable capability with scripts or multi-step logic** (e.g. "here is our full deploy workflow"), consider creating or updating an agent skill under `.github/skills/`.
- After applying the update, briefly confirm what was changed so the user knows the knowledge has been captured.

**Self-reminder:** At the natural end of any substantial working session — or when the user explicitly asks — proactively review what was built, fixed, or learned and update these instructions and/or path-scoped instruction files (`.github/instructions/*.instructions.md`) without waiting to be asked. The goal is for this file and its companion artifacts to remain a living, accurate record of how Grug is built — so future Copilot sessions start from the right context without re-explaining the same things.

## Instructions vs. Prompt Files vs. Agent Skills

Use the right artifact for the right job. The VS Code customization docs ([code.visualstudio.com/docs/copilot/copilot-customization](https://code.visualstudio.com/docs/copilot/customization/overview)) and the GitHub repository instructions docs ([docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)) define these three layers:

| Artifact | Location | When it applies | Best for |
|---|---|---|---|
| **Repository instructions** | `.github/copilot-instructions.md` (repo-wide) or `.github/instructions/*.instructions.md` (path-scoped) | Automatically included in every relevant request | Coding standards, project context, architectural decisions, standing rules ("always/never do X") |
| **Prompt files** | `.github/prompts/*.prompt.md` | When you invoke the slash command explicitly | Repeatable single tasks: scaffold a component, prep a PR, generate a test skeleton |
| **Agent skills** | `.github/skills/` (per [agentskills.io](https://agentskills.io) open standard) | Loaded on-demand when the task matches the skill description | Multi-step capabilities with scripts and resources; works across VS Code, GitHub Copilot CLI, and the coding agent |

**Decision guide:**
- _"This is just how we always write code here"_ → **instructions file**
- _"I want a slash command to kick off this task"_ → **prompt file**
- _"This is a complex workflow with scripts that multiple tools should share"_ → **agent skill**

## Additional Notes

- TTRPG terminology and flavour text are encouraged in variable names, comments, and log messages where appropriate — this is a fun project!
- If adding support for specific game systems (D&D, Pathfinder, etc.), keep game-system-specific logic isolated in clearly named modules.
