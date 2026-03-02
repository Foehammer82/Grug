# Web UI — Overview

Grug's web dashboard lets you manage your server's configuration, documents, glossary, scheduled tasks, and events from a browser — no Discord client required.

---

## Accessing the dashboard

Open **`http://localhost:3000`** (or whatever host/port you've configured).

!!! note "Running on a remote server?"
    If you deployed Grug on a VPS or home server rather than your local machine, replace `localhost` with your server's IP address or domain name.

---

## Logging in

The web UI uses **Discord OAuth2** for authentication. You do not create a separate account.

1. Click **Login with Discord** on the login page.
2. You'll be redirected to Discord to authorise the application.
3. After authorising, you're redirected back and logged in automatically.

Only users who share at least one Discord server with Grug can access the dashboard. Access is scoped per-server — you can only manage servers where both you and Grug are members.

---

## Dashboard — server list

After logging in you land on the **Dashboard**, which lists every Discord server where:

- You are a member, **and**
- Grug is also a member.

Click a server's card to open its management pages.

---

## Navigation

Once you've selected a server, the sidebar (or top nav on smaller screens) provides links to:

| Page | What you can do |
|---|---|
| [Guild Config](guild-config.md) | Update server timezone and bot channel |
| [Events](events.md) | View upcoming calendar events |
| [Scheduled Tasks](tasks.md) | View, enable/disable, or delete tasks |
| [Documents](documents.md) | View and delete indexed documents |
| [Glossary](glossary.md) | Full CRUD for glossary terms |

---

## Logging out

Click your avatar or username in the top-right corner and select **Logout**.
