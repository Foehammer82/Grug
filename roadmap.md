# Grug Roadmap

## TTRPG Features

- **Rules Lookup — Pathfinder 2e & D&D 5e:** Agent tools to look up rules, spells, monsters, feats, etc. on demand. Leverage open-source resources like [Archives of Nethys](https://2e.aonprd.com), the [5e SRD API](https://www.dnd5eapi.co/), and [Open5e](https://open5e.com/) — either as live API queries or RAG-ingested SRD content.

## Web UI

- **Character Sheet Manager (Pathfinder 2e first):** A mobile-friendly character sheet web UI so players can manage characters from the Grug app instead of a third-party app. Target PF2e first, then expand.
  - Full PF2e character sheet (stats, skills, feats, spells, inventory, conditions/effects)
  - DM console: apply conditions, buffs, debuffs, and damage to any player character in the guild
  - Integrated dice roller — roll attacks, saves, skill checks, etc. with results optionally posted to a Discord channel
  - Grug AI embedded throughout the sheet: explain feats, look up rules, narrate rolls, suggest actions, or make character changes via chat
  - Characters linked to Discord guild + user so Grug can reference live sheet data mid-conversation
  - Read-only shareable link for each character sheet
  - Stretch: plug-in model to support D&D 5e and other systems

## Integrations

- **Character Sheet ↔ Discord Bridge:** Post dice rolls to the session channel, let the DM apply effects from Discord, and let Grug reference live character data mid-conversation without players spelling out their modifiers.

## Auth & Access Control

- **Guest Invites — Non-Discord Users:** Admins can invite people without Discord to access parts of the web UI (at minimum, the events calendar). Needs a full auth design — magic-link email, username+password guest accounts, or a non-Discord OAuth provider. Scoped access per invite (e.g. read-only calendar, RSVP only).

## Misc / Wild Ideas
