# Discord — Glossary

The glossary lets your table build a shared reference of campaign terms — house rules, place names, NPC nicknames, homebrew mechanics, and anything else you want Grug to remember consistently.

All glossary commands are **Discord app (slash) commands** and return **ephemeral responses** visible only to you.

---

## Commands

### `/glossary lookup`

Search for a term by name (partial match supported).

| Parameter | Required | Description |
|---|---|---|
| `term` | Yes | The term (or partial term) to search for. |

Returns the definition, its scope (server or channel), and its source (see [Sources](#term-sources) below).

---

### `/glossary add`

Add a new term to the glossary.

| Parameter | Required | Description |
|---|---|---|
| `term` | Yes | The term to define. |
| `definition` | Yes | The definition. |
| `channel` | No | If supplied, the term is scoped to that channel only; otherwise it's server-wide. |

---

### `/glossary edit`

Update an existing term's definition. The original definition is saved to edit history before being replaced.

| Parameter | Required | Description |
|---|---|---|
| `term` | Yes | The exact term to update. |
| `definition` | Yes | The new definition. |

Editing a term clears its AI ownership (see [Sources](#term-sources)) and marks it as human-authored.

---

### `/glossary remove`

Delete a term from the glossary. This is permanent.

| Parameter | Required | Description |
|---|---|---|
| `term` | Yes | The exact term to delete. |

---

### `/glossary list`

List all glossary terms, 10 per page.

| Parameter | Required | Description |
|---|---|---|
| `channel` | No | If supplied, only shows terms scoped to that channel. |
| `page` | No | Page number (default: 1). |

---

## Channel vs server scope

Terms can be **server-wide** (visible in every channel) or **channel-scoped** (visible only in a specific channel). When Grug looks up a term during a conversation, **channel-scoped terms take precedence** over server-wide ones with the same name.

This lets you override a general definition for a specific channel — for example, having a different meaning for "the Tower" in your `#session-notes` channel vs. server-wide lore.

---

## Term sources

Each glossary term carries a **source badge** indicating its origin:

| Badge | Meaning |
|---|---|
| 🤖 AI-generated | Grug created this definition automatically based on context. |
| 👤 Human | A human added or fully replaced the definition. |
| 🤖→👤 Edited | Originally AI-generated, then edited by a human. |

---

## Edit history

Every time a term's definition is changed via `/glossary edit`, a snapshot of the previous definition is stored. You can browse a term's full history from the [Web UI Glossary page](../web-ui/glossary.md).

---

## Tips

- Use channel-scoped terms for session-specific shorthand or spoiler-heavy lore that shouldn't spill into other channels.
- After a session, use `/glossary add` to log new NPCs, locations, or rulings so Grug remembers them next time.
