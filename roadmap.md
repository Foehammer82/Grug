# Grug Roadmap — Ideas & Brainstorming

> **Note:** This is an informal scratch pad for pitching ideas and spitballing future directions.
> It is intentionally loose — nothing here is committed to.
> For the official planned roadmap, see [docs/changelog.md](docs/changelog.md) or the docs site.

---

## How to Use This File

- Dump ideas here freely, no matter how half-baked.
- Group by rough theme when it makes sense.
- Ideas can be promoted to the official docs roadmap once they're fleshed out and agreed on.

---

## Ideas

### Agent & AI

<!-- e.g. smarter context window management, multi-agent support, model switching -->

### TTRPG Features

<!-- e.g. dice rolling, initiative tracker, encounter builder, NPC generator, loot tables -->

- **Rules Lookup Tools — Pathfinder 2e & D&D 5e:** Give Grug agent tools to look up rules, spells, monsters, feats, etc. for Pathfinder 2e and D&D 5e on demand. Leverage open-source online resources (e.g. [Archives of Nethys / Pathfinder 2e API](https://github.com/foundryvtt/pf2e), [2e.aonprd.com](https://2e.aonprd.com), [5e SRD API](https://www.dnd5eapi.co/), [Open5e](https://open5e.com/)). Could be implemented as agent tools that query these APIs and return formatted results, and/or as a RAG ingest of SRD content for richer context.

### Discord Bot

<!-- e.g. new cogs, slash command improvements, per-server config UX -->

### Web UI

<!-- e.g. dashboard improvements, character sheet viewer, campaign manager -->

- **Character Sheet Manager (Pathfinder 2e first):** A full mobile-friendly character sheet web UI so players can manage characters from the Grug app instead of a third-party phone app. Target Pathfinder 2e as the initial system, then expand.
  - Full PF2e character sheet UI (stats, skills, feats, spells, inventory, conditions/effects)
  - DM console: apply conditions, buffs, debuffs, damage, or other effects to any player character in the guild
  - Integrated dice roller — roll attacks, saves, skill checks, etc. with results optionally posted to a Discord channel (configurable per roll or as a session default)
  - Grug AI embedded contextually throughout the sheet: explain a feat, look up a rule, narrate a roll, suggest actions in combat, or make character changes via chat ("level me up", "what should I take for my next skill feat?")
  - Characters linked to Discord guild + user so Grug can reference live sheet data during Discord chat (e.g. auto-resolve "do I succeed on a DC 18 Perception check?" using actual modifiers)
  - Share a character sheet with the table as a read-only link
  - Stretch: plug-in model to support D&D 5e and other systems alongside PF2e

- **Events — RSVP & Attendance Tracking:** Add an RSVP model (`event_id`, `user_id`, `status: attending|maybe|declined`, `note`) so group members can confirm attendance for each event/occurrence. Show RSVP status in the EventDetailModal.
- **Events — Per-Occurrence Overrides:** Allow rescheduling or cancelling individual occurrences of a recurring event without touching the series. Requires an `event_exceptions` table (keyed on `event_id` + `original_start`) storing overrides like a different time, a cancellation flag, or a note.
- **Events — Item/Planning Notes:** Let users attach notes or items to an event (e.g. "Blake is bringing snacks", "need to prep encounter maps"). Could be a simple `event_notes` table or a JSON column.
- **Events — Scheduling / Availability Polling Engine:** Rallly-style scheduling polls — propose multiple date/time options for a session, let members vote on availability, auto-pick the best slot. Similar to [Rallly](https://github.com/lukevella/rallly). Needs a `scheduling_poll` model with `poll_options` and `poll_votes` tables. Surface in the web UI and optionally via Discord slash commands.
- **Events — iCal Export/Import:** Export guild events as an `.ics` feed (subscribe from Google Calendar / Outlook). RRULE storage already uses iCal standard, so export is straightforward.
- **Events — Drag & Drop Rescheduling:** Wire FullCalendar's `eventDrop` and `eventResize` callbacks to PATCH the event's start/end times inline.

### Infrastructure & DevOps

<!-- e.g. easier self-hosting, one-click deploy, better Docker ergonomics -->

### Integrations

<!-- e.g. VTT integrations (Foundry, Roll20), external rule databases, character importers -->

- **Character Sheet ↔ Discord Bridge:** Tie the Character Sheet Manager (see Web UI) to Discord — post dice rolls to the session channel, allow the DM to apply effects from Discord, and let Grug reference live character data mid-conversation without the player having to spell out their modifiers.

### Auth & Access Control

<!-- e.g. non-Discord login, guest access, invite links -->

- **Guest Invites — Non-Discord Users:** Server admins should be able to invite people who aren't on Discord to access certain parts of the web UI (at minimum, the events/calendar view). Needs a full auth design: options include magic-link email invites, a simple username+password guest account, or OAuth with a non-Discord provider. Would need a `guild_invites` or `guest_users` table to track who has been granted access and to what scope (e.g. read-only calendar, RSVP only). Scope/permissions per invite are important — not everyone needs access to everything.

### Misc / Wild Ideas

<!-- anything that doesn't fit above -->
