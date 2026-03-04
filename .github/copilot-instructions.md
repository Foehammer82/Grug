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
- **`docker-compose.yml` is the only compose file** — it is a dev compose with live-reload mounts and a Vite dev server (`web-dev` service). There is no separate `docker-compose.dev.yml` or `docker-compose.prod.yml`. Production deployments live in a separate repo and are out of scope here.

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
- **Never run git commands (commit, push, add, rebase, merge, etc.) unless the user explicitly asks.** Completing a code change does not imply permission to commit it.

## Dual-Surface Development

Every user-facing feature in Grug must work through **both** surfaces:

1. **Discord** — via agent tools (pydantic-ai) and/or slash commands (discord.py cogs)
2. **Web dashboard** — via FastAPI API endpoints and React UI components

When implementing a new feature, always consider both surfaces. A feature that only works in one surface is incomplete. Put shared business logic in a `grug/` service module so both the API route and the agent tool call the same function.

### DM delivery for sensitive data

Character sheets, private notes, and other sensitive data must not be posted publicly in a Discord channel. Agent tools that produce files append them to `ctx.deps._pending_dm_files` and prefix their response with `[DM_FILE:filename]`. The bot's `_deliver_response()` helper strips these sentinels and DMs the files to the requesting user. See the `dual-surface-features` skill (`.github/skills/dual-surface-features/SKILL.md`) for full patterns and checklist.

## Domain Concepts — Context Awareness

Grug passively logs **every** non-bot guild message to `conversation_messages` with `is_passive=True` so he stays context-aware in channels even when not @mentioned. When he actually responds, the message is saved with `is_passive=False` (the default).

### Context Cutoff — Precedence

There is only one configurable cutoff level:

| Level | Model field | Scope |
|---|---|---|
| Per-user (DMs) | `UserProfile.dm_context_cutoff` | DM sessions only |

For guild channels, context history is always bounded by the rolling window `now - AGENT_CONTEXT_LOOKBACK_DAYS` days (default 30, env var, read from `Settings.agent_context_lookback_days`).  This is computed directly in the `on_message` handler — there is no longer a `_get_effective_context_cutoff()` helper.  `_get_dm_context_cutoff()` still exists for DM sessions and falls back to the same rolling window when no per-user cutoff is set.  The resolved cutoff is passed to `GrugAgent.respond()` → `_load_history()`.

### Guild admin authorization

`is_guild_admin()` in `api/deps.py` grants admin access via three paths:
1. **Grug super-admin** — env var `GRUG_SUPER_ADMIN_IDS` or DB `is_super_admin` flag.
2. **Discord guild owner** — live Discord API check against the guild's `owner_id` (cached 5 min in `_GUILD_OWNER_CACHE`).
3. **Grug-admin role** — live Discord API check against `grug_admin_role_id` in `GuildConfig` (cached 5 min, bounded to 2048 entries via `_BoundedTTLCache`).

**The Discord ADMINISTRATOR permission bit is NOT read from the JWT** for authorization decisions.  JWT guild data no longer includes `permissions` at all.  Discord server admins who are not Grug super-admins must be assigned the `grug-admin` role via guild config.

### OAuth scope and guild membership

The Discord OAuth scope is **`identify` only** — the `guilds` scope is not requested.  The JWT payload never contains the user's guild list.

Guild membership is verified live via the Discord **bot token** instead:

- **`assert_guild_member(guild_id, user)`** — async helper in `api/deps.py`.  Calls `GET /guilds/{id}/members/{user_id}` with the bot token (HTTP 200 = member, 404 = not a member).  Results are cached 5 min in `_MEMBER_CACHE` (plain dict, max 2048 entries, same TTL constant as `_ROLE_CACHE`).  Super-admins bypass the check entirely.  All call sites must `await` it.
- **`GET /api/guilds`** — iterates over all `GuildConfig` rows (guilds Grug is in) and checks membership for each in parallel.  Guild name and icon are fetched from `GET /guilds/{id}` via bot token for confirmed members.

### ChannelConfig model

`ChannelConfig` (table `channel_configs`) stores per-channel settings:
- `always_respond: bool` — replaces the old in-memory `_ALWAYS_RESPOND_CHANNELS` set; persists across restarts
- `guild_id` FK → `guild_configs.guild_id`
- `channel_id` unique index

The `/chat_here` slash command now reads/writes this table instead of an in-memory set.

## Domain Concepts — Rule Sources

Grug can look up TTRPG rules on demand via the `lookup_ttrpg_rules` agent tool (`grug/agent/tools/rules_tools.py`).  Only built-in sources are supported — there are no custom guild-configured sources.

### Built-in sources
Defined as a static list in `grug/rules/sources.py`.  Two are built-in:

- **`aon_pf2e`** — Archives of Nethys (PF2e).  Official Paizo-partnered SRD with near-complete PF2e coverage (all rulebooks, supplements, Adventure Paths, PFS scenarios).  Uses the undocumented Elasticsearch endpoint at `elasticsearch.aonprd.com` for genuine free-text relevance search.  Before searching, `_plan_aon_query` makes a fast claude-haiku call that produces an `_AONQueryPlan` (a curated `search_query` free of conversational preamble, plus optional `preferred_types` to boost in Elasticsearch scoring).  Returns 1 result for agent calls (`size=1` default); the admin test UI passes `size=5` explicitly.  Falls back to the raw query if the planner fails.  Fetch function: `_fetch_aon_pf2e`.
- **`srd_5e`** — D&D 5e SRD via dnd5eapi.co.  Covers the 2014 SRD only (no non-SRD monsters, no 2024 revised content).  Two-phase search: (1) parallel `?name=<substring>` queries across spells, monsters, magic-items, equipment, conditions, and feats — tried with both the full query and individual non-stop-word tokens so "how does grappling work" still matches "Grappled"; (2) the 33 `rule-sections` index entries are fetched and keyword-scored client-side, with top matches fetched in full to cover mechanics (grapple, opportunity attack, bonus action) that have no named entity.  There is **no full-text search endpoint** on dnd5eapi.co — name-substring + rule-sections client filtering is the only available strategy.  Fetch functions: `_fetch_srd_5e`, `_format_srd_entry`, `_detect_srd_type`.

  **LLM routing**: before searching, `_plan_srd_query` makes a fast claude-haiku call that produces a `_SRDQueryPlan` (which entity endpoints to search by name, which entities to fetch by direct slug, which rule-section keywords to score against).  This allows class/race/skill/trait lookups (e.g. `/api/2014/classes/wizard`) that have no `?name=` filter.  Falls back to word-tokenisation if the LLM call fails.  Entity types handled: Spell, Monster, Condition, Magic Item, Equipment, Feature, Background, Class, Race, Subclass, Skill, Trait, Rule Section, Rule.

Open5e was removed: its v2 unified search returns zero results for all queries — it is broken and was replaced by the improved `srd_5e` implementation.

Guild admins can disable any built-in per-server.  Overrides are stored in the `guild_builtin_overrides` table (`GuildBuiltinOverride` model) keyed by `source_id`.  No row = built-in is **enabled** (safe default).


### Web UI
The Config page renders **Server Settings** and **Channel Settings** as stacked sections (no sub-tabs) — a `Typography h6` heading followed by each panel, separated by a `Divider`.

Rule Sources is its own top-level tab in `GuildLayout` (`path: 'rule-sources'`, `adminOnly: true`), implemented in `web/src/pages/RuleSourcesPage.tsx`. It renders the list of built-in sources (fixed order, "Built-in" chip, enabled `Switch`, no delete/reorder controls).

### API
- `GET  /api/guilds/{id}/rule-sources/builtins` — list builtins with effective enabled state
- `PATCH /api/guilds/{id}/rule-sources/builtins/{source_id}` — toggle a builtin
- `POST /api/guilds/{id}/rule-sources/test` — test a built-in source with a query (`source_id` required)

## Domain Concepts — Campaigns & Characters

Characters are a sub-concept of campaigns — they only exist within a campaign. There is no standalone Characters tab or route.

### Campaign model (`campaigns` table)

Key fields: `id`, `guild_id`, `channel_id` (unique), `name`, `system`, `is_active`, `created_by`, `created_at`, `deleted_at`.

`deleted_at` is the soft-delete column. `NULL` = active; non-NULL = deleted but recoverable.  Hard-deletes never happen via the soft-delete trigger — only `DELETE .../permanent` issues an actual `db.delete()`.

### Character model (`characters` table)

Characters belong to a campaign via a nullable FK `campaign_id → campaigns.id`.  No many-to-many.  A character can be unlinked (`campaign_id IS NULL`) — e.g. Pathbuilder-linked characters created before being assigned to a campaign.

### API routes (campaigns)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/guilds/{id}/campaigns` | member | `?include_deleted=true` for admins fetches deleted too. Non-admins filtered to campaigns where they own a character. |
| `POST` | `.../campaigns` | admin | |
| `PATCH` | `.../campaigns/{cid}` | admin | |
| `DELETE` | `.../campaigns/{cid}` | admin | **Soft-delete** — sets `deleted_at`. Never hard-deletes. |
| `POST` | `.../campaigns/{cid}/restore` | admin | Clears `deleted_at`. |
| `DELETE` | `.../campaigns/{cid}/permanent` | admin | Hard-delete + cascade characters. |
| `GET/POST/PATCH/DELETE` | `.../campaigns/{cid}/characters/…` | admin | Full character CRUD scoped to a campaign. |
| `POST` | `.../campaigns/{cid}/characters/{chid}/copy` | admin | Deep-copies character (all fields) to `target_campaign_id` in same guild. |
| `POST` | `.../campaigns/{cid}/characters/{chid}/upload` | admin | Parse + index character sheet. |

Transfer (move) a character between campaigns uses the existing `PATCH /api/guilds/{id}/characters/{chid}` with `{ campaign_id: targetId }`.

### Web UI

- **Campaigns tab** — `adminOnly: false`.  Non-admins see a filtered read-only view (only campaigns they have a character in, no edit controls).  Admins get full CRUD.
- **Characters tab** — **removed**.  `CharactersPage.tsx` is deleted; all character management lives inside each campaign card.
- Layout: card-per-campaign (`CampaignCard`) with an always-visible `CharacterTable` underneath the header bar.  No accordions.
- Each character row opens a combined `CharacterDialog` with three tabs: **Details** (name, owner, sheet upload, Pathbuilder import ID, move/copy), **Sheet** (parsed stats via `CharacterStatCard`), **Notes** (auto-saving textarea).
- Batch delete via checkbox selection in `CharacterTable`; no per-row delete icon button.
- **Pathbuilder is import-only.** There is no standalone "Sync from Pathbuilder" button. Pathbuilder ID is set during character create/edit and the sheet is fetched client-side via `fetchPathbuilderClientSide()` at that time. The `CharacterSheetPage` sync button has been removed.
- Soft-delete shows an 8-second **Undo snackbar** allowing instant restore.
- A collapsed **"Deleted campaigns"** section (admin-only) lists soft-deleted campaigns with per-row **Restore** and **Delete permanently** actions. Permanent delete has a separate confirmation dialog.
- Each character row has a 3-dot menu with **Move to campaign…** and **Copy to campaign…** items (only shown when other campaigns exist).  Both open a dialog with an `Autocomplete` to pick the target campaign.
- `CharacterSheetPage` back button navigates to `/guilds/:guildId/campaigns` (previously pointed to the removed `/characters` route).

#### Component structure (`web/src/components/campaigns/`)

| Component | Purpose |
|---|---|
| `CampaignCard` | Header bar + tabbed panel: **Characters** tab (embeds `CharacterTable`) and **Session Notes** tab (embeds `SessionNotesTab`) |
| `CharacterTable` | MUI Table with checkbox column, batch toolbar, "Add character" button; opens `CharacterDialog` |
| `CharacterDialog` | Combined tabbed dialog (Details · Sheet · Notes); handles create, edit, delete, move, copy |
| `CharacterStatCard` | Compact parsed-stats card (headline, AC/HP/Speed, ability scores) |
| `OwnerAutocomplete` | Autocomplete for picking a guild member or free-text owner; exports `UNASSIGNED_MEMBER` sentinel and `resolveOwnerPayload()` |
| `GuildMemberCell` | Renders guild member avatar + display name with loading/error states |
| `SessionNotesTab` | Lists session notes (expand-to-read), exposes "Add Notes" button with text paste + file upload; polls every 5 s while any note is pending/processing |

Shared constants live in `web/src/constants/character.ts` (`SYSTEM_OPTIONS`, `SYSTEM_LABELS`, `ABILITY_KEYS`, `SHEET_ACCEPTED`, `MAX_SHEET_MB`, `abilityMod()`).

### Agent tools (campaigns & characters)

Campaign and character tools are registered by `register_campaign_tools()` in `grug/agent/tools/campaign_tools.py`. Two tools:

| Tool | What it does | Access |
|---|---|---|
| `get_campaign_info` | Returns campaign name, system, status, and party roster | Everyone |
| `get_party_character` | Looks up a specific character by name in the current campaign | Own character → full sheet; other's character → public summary only; admin → full access |

Admin detection uses `_is_admin()` helper that checks (1) `GRUG_SUPER_ADMIN_IDS` env, (2) `GrugUser.is_super_admin` DB flag, (3) Discord `grug-admin` role via bot cache.

The existing `register_character_tools()` (`character_tools.py`) handles `get_character_sheet` and `search_character_knowledge` — both read-only, scoped to the requesting user's **active character** via `UserProfile.active_character_id`. Character data is never modified by Grug; it is ingested on upload or Pathbuilder sync and queried for context.

### Session Notes

Session notes allow any campaign member (or guild admin) to submit raw notes (text paste or `.txt`/`.md`/`.rst` upload) for a campaign. An LLM (`claude-haiku-4-5`) synthesizes them into a clean prose summary in the background. Clean notes are indexed into the RAG vector store so Grug can search them.

**ORM model**: `SessionNote` (table `session_notes`, `grug/db/models.py`) — `id`, `campaign_id` (FK → `campaigns.id`), `guild_id`, `session_date`, `title`, `raw_notes`, `clean_notes`, `synthesis_status` (`pending`|`processing`|`done`|`failed`), `synthesis_error`, `rag_document_id`, `submitted_by`, `created_at`, `updated_at`.

**Service**: `grug/session_notes.py` — `create_session_note()`, `synthesize_note(note_id)` (background-safe, own DB sessions), `delete_session_note(note_id, guild_id)`.

**API routes**: `api/routes/session_notes.py` — full CRUD under `/api/guilds/{guild_id}/campaigns/{campaign_id}/session-notes`. Any campaign member may read/create; only the submitter or an admin may update/delete/re-synthesize.

**Agent tool**: `search_session_notes` registered in `grug/agent/tools/session_notes_tools.py`. Uses `DocumentRetriever` scoped to `ctx.deps.campaign_id`. Returns a friendly message if no campaign is linked. Registered in `_build_agent()` via `register_session_notes_tools(agent)`.

**`CallType`**: `SESSION_NOTE_SYNTHESIS` — add to the `CallType` enum in `grug/llm_usage.py` if it's missing.

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

### Campaign creation — duplicate channel 409
`campaigns.channel_id` has a `unique=True` DB constraint (one channel → one campaign).  The POST `/api/guilds/{id}/campaigns` handler wraps `db.commit()` in a `try/except IntegrityError`, rolls back, and raises `HTTPException(status_code=409)`.  Never remove this guard.

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
