# Web UI — Scheduled Tasks

The Scheduled Tasks page lets you view and manage all automated tasks Grug runs for your server.

---

## Accessing tasks

1. Log in to the [web dashboard](overview.md).
2. Select your server from the dashboard.
3. Click **Scheduled Tasks** in the sidebar.

---

## Task table

Each row represents one scheduled task and shows:

| Column | Description |
|---|---|
| **Name** | A short description of what the task does. |
| **Schedule** | The cron expression that controls when the task runs (e.g. `0 18 * * 5` = every Friday at 6 PM). |
| **Enabled** | Checkbox — toggle to enable or disable the task without deleting it. |
| **Last Run** | When the task last executed successfully. |
| **Actions** | Delete button to permanently remove the task. |

---

## Enabling / disabling a task

Click the **Enabled** checkbox on any row to toggle the task on or off immediately. Disabled tasks remain in the list but will not run until re-enabled.

---

## Deleting a task

Click the **delete** (trash icon) button on a row to permanently remove the task.

!!! warning
    Deleting a task is permanent. If you only want to pause it temporarily, use the **Enabled** toggle instead.

---

## Managing tasks from Discord

You can also view tasks with [`!list_tasks`](../discord/admin.md#list-tasks) and permanently remove them with [`!cancel_task <id>`](../discord/admin.md#cancel-task).
