# Grug Roadmap

> Informal scratch pad for ideas and estimates. When something gets promoted
> to "we're actually doing this", move it to `docs/`.

---

## Phase 1 — Pathbuilder Integration + Character Viewer ✅ IN PROGRESS

**Effort: Small-Medium (~2–3 sessions)**
**Feasibility: High — public unauthenticated API exists**

Instead of building a Pathbuilder competitor, let users link their existing
Pathbuilder character by ID. Grug syncs structured data from Pathbuilder's
JSON endpoint and renders a read-only summary.

- [x] Pathbuilder fetch utility (`grug/character/pathbuilder.py`)
- [x] `pathbuilder_id` column on Character model + Alembic migration
- [x] `/character pathbuilder <id>` and `/character sync` Discord slash commands
- [x] Character API routes (list, detail, update, delete, link-pathbuilder, sync)
- [x] Web Characters tab in guild layout
- [x] Web character list page (card grid with Pathbuilder badge + sync button)
- [x] Web character detail/sheet page (system-aware rendering of structured_data)
- [x] Keep existing upload path — `/character upload` still works for non-Pathbuilder chars
- [ ] Test with real Pathbuilder characters (need live validation)
- [ ] Mobile responsiveness pass on sheet page

---

## Phase 2 — Mutable State Overlay + DM Tools

**Effort: Medium (~2–3 sessions)**
**Feasibility: High — builds on Phase 1 data**

Pathbuilder handles the *character build*. Grug handles *session state* — the
stuff that changes during play and that Pathbuilder doesn't track in real time.

- **`mutable_state` column:** New JSON column on Character for session deltas:
  current HP, temp HP, active conditions (with values), spent spell slots,
  used focus points, hero points, custom notes.
- **Web interactive state:** On the character detail page, HP is editable
  (quick +/- buttons), conditions are chips (add/remove from a PF2e conditions
  list), spell slots are checkboxes.
- **State reset:** "Long rest" / "Full reset" button clears mutable_state.
- **DM console:** Campaign view showing all linked characters with quick-action
  buttons (apply damage, add condition, heal). Admin-only.
- **Agent awareness:** `update_character_field` routes HP/condition changes
  through mutable_state. Agent can say "Grug takes 15 damage" and Grug updates
  the character's current HP.

### Open questions
- PF2e has 42+ conditions, many with values (Frightened 2, Persistent Damage).
  Ship a built-in conditions reference list, or freeform entry?
- Concurrent mutations from web + Discord — last-write-wins is probably fine
  for a TTRPG tool, but worth noting.

---

## Phase 3 — Dice Roller + Discord Posting

**Effort: Medium (~2–3 sessions)**
**Feasibility: High**

A web-based dice roller that optionally posts results to Discord.

- **Simple roller first:** Generic dice notation input (2d6+4, 1d20+8,
  4d6kh3). Shows result breakdown (individual dice, total, modifiers).
- **Discord posting:** Select a channel, post a formatted embed with the roll
  result. Uses bot token REST API.
- **Roll-from-sheet (smart roller):** "Roll" buttons next to skills, saves,
  attacks on the character sheet. Pre-fills the expression with the correct
  modifier pulled from structured_data/Pathbuilder data.
- **PF2e modifier awareness (stretch):** Apply condition penalties from
  mutable_state automatically. Handle MAP for sequential attacks.

### Open questions
- Use an existing dice library (`d20` for Python, `@dice-roller/rpg-dice-roller`
  for TS) or roll our own? Library saves effort but adds a dependency.
- Should roll history be persisted or fire-and-forget?

---

## Phase 4 — Read-Only Shareable Links

**Effort: Small (~1 session)**
**Feasibility: High**

- **Share token:** UUID column on Character. Owner generates a shareable link.
- **Public route:** `/shared/characters/:token` renders the sheet without auth.
- **Uses existing PublicLayout component.**

---

## Phase 5 — Discord Bridge Enhancements

**Effort: Medium (~2 sessions)**
**Feasibility: High — extends Phase 2 + 3**

- DM can apply conditions/damage from Discord slash commands.
- Dice rolls from Discord reference live character data (modifiers, conditions).
- Grug AI references mutable_state (current HP, active conditions) when
  answering questions mid-session.

---

## Deferred / Exploring

These are ideas that aren't planned yet but worth capturing.

- **Web-based Grug AI chat:** Requires a new streaming endpoint (SSE/WebSocket),
  web auth → agent deps mapping, conversation persistence outside Discord.
  Significant new capability — defer until core character features are solid.
- **D&D Beyond integration:** No public API. Would require per-user auth cookie
  proxying, which is fragile and arguably a security concern. Probably not viable.
- **Wanderer's Guide integration:** Open-source PF2e builder, but has no public
  API yet. Monitor for upstream API development.
- **HeroLab Online integration:** Closed, commercial, no API. Not viable.
- **5e character builder integration:** No good public APIs exist in the 5e
  ecosystem. The existing upload-and-parse path is the best option for 5e.
- **Plug-in system model for rendering:** A component registry keyed by
  `character.system` for system-specific sheet rendering. Only worth building
  if we support 3+ systems.
