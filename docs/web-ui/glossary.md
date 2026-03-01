# Web UI — Glossary

The Glossary page provides a full CRUD interface for managing your server's campaign terms. Everything you can do with Discord's `/glossary` commands is available here with a richer editing experience.

---

## Accessing the glossary

1. Log in to the [web dashboard](overview.md).
2. Select your server from the dashboard.
3. Click **Glossary** in the sidebar.

---

## Term list

The main view shows all glossary terms for the selected server. Each row displays:

| Column | Description |
|---|---|
| **Term** | The glossary term. |
| **Definition** | Current definition. |
| **Scope** | Server-wide, or the name of the channel it's scoped to. |
| **Source** | 🤖 AI-generated / 👤 Human / 🤖→👤 AI-then-edited. |
| **Actions** | Edit and delete buttons. |

---

## Filtering by channel

Use the **Channel** dropdown at the top of the page to filter the list to terms scoped to a specific channel. Select **All** to show everything.

---

## Adding a term

Click **Add term** to open the creation form:

1. Enter the **term**.
2. Enter the **definition**.
3. Optionally select a **channel** to scope the term to that channel only. Leave blank for a server-wide term.
4. Click **Save**.

---

## Editing a term

Click the **edit** (pencil) icon on any row to open the inline editor. Make your changes and click **Save**.

!!! note "Edit history"
    Saving a change automatically snapshots the old definition into the term's edit history. See [Viewing edit history](#viewing-edit-history) below.

---

## Deleting a term

Click the **delete** (trash) icon on any row to permanently delete the term.

!!! warning
    Term deletion is permanent and cannot be undone via the web UI.

---

## Viewing edit history

Click a term's name to open a detail view that includes its full **edit history** — a chronological list of all previous definitions with timestamps. This is useful for rolling back an accidental edit or reviewing how a definition evolved.

---

## Source badges explained

| Badge | Meaning |
|---|---|
| 🤖 | Grug generated this definition automatically during a conversation. |
| 👤 | A human created or fully replaced the definition. |
| 🤖→👤 | Grug created it, but a human has since edited it. |
