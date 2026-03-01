# Discord — Admin Commands

These commands help server admins manage Grug's configuration, scheduled tasks, and calendar events.

---

## Server status

### `!grug_status`

**Permission required:** None

Displays a status embed showing:
- The AI model Grug is currently using
- Whether the scheduler is running
- Number of active scheduled jobs

Useful for a quick sanity check that everything is working.

---

## Timezone

### `!set_timezone <tz>`

**Permission required:** Manage Guild

Sets the timezone Grug uses when displaying times for scheduled tasks and events in this server.

```
!set_timezone America/New_York
!set_timezone Europe/London
!set_timezone Australia/Sydney
```

Use [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). The timezone affects all event and task times displayed in Discord for your server.

!!! tip
    You can also update the timezone from the [Web UI Guild Config page](../web-ui/guild-config.md).

---

## Scheduled tasks

### `!list_tasks`

**Permission required:** None

Lists all scheduled tasks for the server, including:
- Task ID and name
- Cron expression (schedule)
- Whether the task is enabled
- Last time it ran

---

### `!cancel_task <id>`

**Permission required:** Manage Guild

Disables and removes a scheduled task by its ID.

```
!cancel_task 7
```

Use `!list_tasks` to find the task ID first.

!!! note
    You can also manage tasks from the [Web UI Tasks page](../web-ui/tasks.md), where you can toggle tasks on/off without permanently deleting them.

---

## Calendar events

### `!upcoming`

**Permission required:** None

Shows the next 10 upcoming calendar events for the server — title, description, and start/end times formatted in the server's configured timezone.

---

## Permissions reference

| Command | Required Permission |
|---|---|
| `!grug_status` | None (any member) |
| `!set_timezone` | Manage Guild |
| `!list_tasks` | None (any member) |
| `!cancel_task` | Manage Guild |
| `!upcoming` | None (any member) |
