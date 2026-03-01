# Grug

**Grug** is a self-hosted AI companion built for TTRPGs. Powered by Claude (Anthropic), Grug lives in your Discord server and helps your table with lore tracking, rules lookups, world-building, scheduling, and whatever else you throw at him.

---

## What can Grug do?

| Feature | Where |
|---|---|
| 💬 AI chat with full context awareness | Discord — mention `@Grug` |
| 📖 Server & channel glossaries | Discord slash commands + Web UI |
| 📄 Document upload & RAG retrieval | Discord commands + Web UI |
| 📅 Scheduled reminders & events | Discord commands + Web UI |
| ⚙️ Per-server configuration | Web UI |
| 🔌 Extensible via MCP tool servers | Config file |

---

## Quick links

<div class="grid cards" markdown>

- :material-rocket-launch: **[Get started](getting-started/installation.md)**
  Install and run Grug in minutes with Docker Compose.

- :material-discord: **[Discord commands](discord/ai-chat.md)**
  Everything you can ask Grug to do right from your server.

- :material-monitor: **[Web UI](web-ui/overview.md)**
  Manage documents, glossaries, tasks, and config in your browser.

- :material-help-circle: **[FAQ](faq.md)**
  Answers to common questions and troubleshooting tips.

</div>

---

## Architecture overview

Grug runs as three cooperating services behind Docker Compose:

```
Discord ──► grug (bot process)  ──► sqlite / postgres
               │                         │
               ▼                         ▼
           api (FastAPI)  ◄──────  web (React UI)
```

All three services share the same database. The bot and the web UI are both first-class — anything you can do in Discord you can usually also do from the web dashboard.

---

!!! tip "Self-hosted and private"
    Grug stores all data locally. Your conversation history, glossary, documents, and configuration never leave your own infrastructure.
