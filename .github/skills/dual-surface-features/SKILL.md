---
name: dual-surface-features
description: Guide for implementing features that span both the web UI and the Discord bot. Use this skill whenever the user asks to build a new feature that users interact with through both surfaces — e.g. character sheets, campaigns, scheduled tasks, rule lookups, PDF exports.
compatibility: Requires the Grug monorepo with grug/ (Python bot + agent) and web/ (React frontend).
metadata:
  author: blake
  version: "1.0"
---

# Dual-Surface Feature Development — Grug Project

## Context

Grug exposes every major feature through **two surfaces**:

| Surface | Stack | How users reach it |
|---|---|---|
| **Discord bot** | discord.py cogs + pydantic-ai agent tools | @mention, slash commands, DMs |
| **Web dashboard** | React 18 + MUI v7 + React Query | Browser at the Grug web URL |

When building or modifying any feature, **always consider both surfaces**. A feature that only works in one surface is incomplete.

---

## Architecture Overview

### Discord → Agent → Tools

```
User message → ai_chat.py (on_message)
  → GrugAgent.respond()
    → pydantic-ai Agent with registered tools
    → Tool functions query DB / call services
  ← AgentResponse (text + dm_files)
  → channel.send() + optional DM delivery
```

### Web → API → DB

```
React component → React Query hook
  → FastAPI endpoint (api/routes/*.py)
    → SQLAlchemy queries / service functions
  ← JSON response
  → Component re-renders
```

### Shared layers
- **ORM models**: `grug/db/models.py` — single source of truth for both surfaces
- **Service functions**: Business logic in `grug/` packages (e.g. `grug/character/indexer.py`) is called by both API routes and agent tools
- **Config**: `grug/config/settings.py` — env-var-driven settings used everywhere

---

## Checklist for New Features

### 1. Data layer
- [ ] Add/modify ORM model in `grug/db/models.py`
- [ ] Generate Alembic migration (Postgres only, see `alembic-migrations` skill)
- [ ] Add Pydantic schemas in `api/schemas.py` if the web API needs them

### 2. Service / business logic
- [ ] Put reusable logic in a `grug/` module (not in routes or tools)
- [ ] Both the API route and the agent tool should call the same service function

### 3. Discord surface
- [ ] **Agent tool** in `grug/agent/tools/` — register via `register_*_tools(agent)` in `core.py`
- [ ] Tool docstrings must be clear — the LLM reads them to decide when to call
- [ ] If the feature produces files, use `ctx.deps._pending_dm_files.append((filename, bytes))` and prefix the response with `[DM_FILE:filename]`
- [ ] Update system prompt in `grug/agent/prompt.py` if the agent needs new behavioral rules
- [ ] **Slash command** (optional) in `grug/bot/cogs/` — for actions that benefit from Discord UI (autocomplete, modals, etc.)

### 4. Web surface
- [ ] **API endpoint** in `api/routes/` — RESTful, guild-scoped
- [ ] **React page or component** in `web/src/` — follow MUI v7 patterns (see `web.instructions.md`)
- [ ] Use React Query for data fetching; mutations invalidate relevant query keys
- [ ] File downloads: fetch as blob, create object URL, trigger `<a>` click

### 5. Permissions
- [ ] Discord: agent tools check ownership via `ctx.deps.user_id` + admin via `_is_admin()` helper
- [ ] Web: API routes use `is_guild_admin()` or `is_guild_member()` from `api/deps.py`
- [ ] Same permission logic in both surfaces — a user who can do X on the web can do X in Discord and vice versa

### 6. Privacy / DM delivery
- [ ] Sensitive data (full character sheets, private notes) should be DM'd in Discord, not posted publicly
- [ ] Agent tools that produce files store them on `ctx.deps._pending_dm_files`
- [ ] The `_deliver_response()` helper in `ai_chat.py` strips `[DM_FILE:...]` sentinels and sends files via DM
- [ ] Web API returns files directly (the browser is already private to the user)

---

## Patterns

### Agent tool that produces a file for DM delivery

```python
@agent.tool
async def export_thing(ctx: RunContext[GrugDeps], name: str) -> str:
    # ... generate file_bytes ...
    ctx.deps._pending_dm_files.append((filename, file_bytes))
    return f"[DM_FILE:{filename}] Grug made the thing! Check DMs!"
```

The bot's `_deliver_response()` in `ai_chat.py` automatically:
1. Strips `[DM_FILE:...]` from the public channel message
2. Sends each file in `agent_resp.dm_files` to the user's DM channel

### Shared service function called by both surfaces

```python
# grug/character/indexer.py  (service layer)
class CharacterIndexer:
    async def index_character(self, character_id: int, raw_text: str) -> None:
        ...

# api/routes/campaigns.py  (web surface)
@router.post("/{campaign_id}/characters/{character_id}/upload")
async def upload_character_sheet(...):
    indexer = CharacterIndexer()
    await indexer.index_character(character.id, raw_text)

# grug/bot/cogs/characters.py  (Discord surface)
class CharacterCog(commands.Cog):
    self._indexer = CharacterIndexer()
    await self._indexer.index_character(character_id, raw_text)
```

---

## Common Mistakes

1. **Building a feature for only one surface** — always implement both the API endpoint and the agent tool.
2. **Duplicating business logic** — put it in a `grug/` service module, call from both surfaces.
3. **Posting sensitive data in the channel** — use DM delivery for character sheets, private notes, etc.
4. **Different permission models** — keep Discord agent permissions and web API permissions consistent.
5. **Forgetting to update the system prompt** — when adding new agent tools, tell Grug about them in `prompt.py`.
