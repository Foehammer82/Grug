# Web UI — Guild Configuration

The Guild Config page lets server admins update Grug's per-server settings.

---

## Accessing guild config

1. Log in to the [web dashboard](overview.md).
2. Select your server from the dashboard.
3. Click **Guild Config** in the sidebar.

---

## Settings

### Timezone

Controls how Grug displays times for scheduled tasks and calendar events in your server.

- Enter a valid [IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) — e.g. `America/New_York`, `Europe/London`, `Australia/Sydney`.
- Click **Save** to apply.

The same timezone can be set via the Discord command [`!set_timezone`](../discord/admin.md#timezone).

---

### Announce channel

The channel ID (a number) where Grug will post automated announcements — scheduled task outputs, reminders, and event notifications.

1. Right-click the target channel in Discord → **Copy Channel ID** (Developer Mode must be enabled in Discord settings).
2. Paste the ID into the **Announce Channel** field.
3. Click **Save**.

!!! tip "Enabling Developer Mode in Discord"
    Go to **User Settings → Advanced** and toggle **Developer Mode** on. This lets you right-click channels, users, and messages to copy their IDs.

---

## Read-only fields

The Guild Config page also shows the server's **Guild ID** — a non-editable field you may need when troubleshooting or configuring integrations.
