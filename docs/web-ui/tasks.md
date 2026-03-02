# Web UI — Scheduled Tasks

The Scheduled Tasks page lets you view and manage all tasks Grug runs for your server.
Tasks cover both one-off reminders (fire once at a specific time) and recurring automated
prompts (fire on a cron schedule) — they are the same concept.

---

## Accessing tasks

1. Log in to the [web dashboard](overview.md).
2. Select your server from the dashboard.
3. Click **Tasks** in the tab bar.

---

## Task table

Each row represents one scheduled task and shows:

| Column | Description |
|---|---|
| **Type** | `Once` — fires once at a specific time.  `Recurring` — fires on a cron schedule. |
| **Name / Prompt** | The task name, or the first 60 characters of the prompt if no name is set. |
| **Schedule** | For `Once` tasks: the fire date/time.  For `Recurring` tasks: the cron expression (e.g. `0 18 * * 5` = every Friday at 6 PM). |
| **Enabled** | Toggle to enable or disable the task without deleting it. |
| **Status** | For `Once` tasks: `Pending` or `Fired`.  For `Recurring` tasks: when the task last ran. |
| **Next Run** | The next scheduled trigger time.  For `Once` tasks: the fire time (while pending).  For `Recurring` tasks: computed from the cron expression. Shows `—` when disabled or already fired. |
| **Actions** | Delete button to permanently remove the task. |

---

## Creating tasks

Ask Grug in chat — there is no web UI creation form.

Examples:

- One-off: *"remind me to check my spell slots in 30 minutes"*
- Recurring: *"every Friday morning, post the weekly session recap"*

---

## Enabling / disabling a task

Click the **Enabled** toggle on any row to pause or resume a task immediately.

For one-shot (`Once`) tasks, disabling before the fire time cancels the reminder.

---

## Deleting a task

Click the **Delete** button on a row to permanently remove it.

!!! warning
    Deleting a task is permanent. If you only want to pause it temporarily, use the **Enabled** toggle instead.

---

## Managing tasks from Discord

You can also view tasks with `/list_tasks` and cancel them with `/cancel_task <id>`.
See [Discord admin commands](../discord/admin.md) for details.
