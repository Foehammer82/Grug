# FAQ & Troubleshooting

---

## General

### Grug isn't responding to messages

1. **Check that he's online.** Run `!grug_status` — if there's no response, the bot process may have crashed. Run `docker compose logs grug --tail 30` to inspect.
2. **Check permissions.** Grug needs **Send Messages**, **Read Message History**, and **View Channel** in the channel you're testing in.
3. **Check always-on vs mention mode.** By default Grug only replies when mentioned (`@Grug`). If you want him to respond to all messages, use [`!chat_here`](discord/ai-chat.md#always-on-mode).

---

### Grug responds but his answers seem outdated or wrong about my campaign

Grug doesn't know about your campaign unless you tell him. Make sure you've:

- [Uploaded your campaign documents](discord/documents.md) with `!upload_doc`.
- Added key terms to the [glossary](discord/glossary.md) with `/glossary add`.
- Included relevant context directly in your question ("As a level 7 ranger in our homebrew world…").

---

### Grug cuts off mid-response

Grug has a configurable maximum number of tool-calling iterations (`AGENT_MAX_ITERATIONS`, default: 10). For complex multi-step tasks this may be too low. Increase it in your `.env`:

```dotenv
AGENT_MAX_ITERATIONS=20
```

Then restart: `docker compose restart grug`.

---

### I'm getting rate limit errors from Anthropic

You've hit your Anthropic API tier's rate limits. Options:

- Reduce `AGENT_MAX_ITERATIONS` to use fewer tokens per response.
- Reduce `AGENT_CONTEXT_WINDOW` to keep less history in context.
- Upgrade your Anthropic plan or switch to a less expensive model via `ANTHROPIC_MODEL`.

---

## Web UI

### I can't log in to the web dashboard

- Make sure your Discord application has the **OAuth2 redirect URI** set to `http://localhost:3000/auth/discord/callback` (or your server's equivalent). Check the Discord Developer Portal → OAuth2 → Redirects.
- Ensure the `api` service is running: `docker compose ps`.
- Check API logs: `docker compose logs api --tail 30`.

---

### I see "You don't have access to any servers"

Grug must be a member of at least one of your Discord servers. [Invite Grug](getting-started/installation.md#step-1-create-a-discord-bot) using the OAuth URL from the Developer Portal.

---

### The web UI loads but shows error messages

Check that the API service is healthy:

```bash
docker compose ps
docker compose logs api --tail 30
```

Also confirm that the `api` service has the same `DATABASE_URL` as the `grug` bot service in your `.env`.

---

## Documents & RAG

### My uploaded document doesn't seem to affect Grug's answers

- Confirm the upload succeeded: run `!list_docs` and check the chunk count is greater than 0.
- Ask a question that directly references content from the document. Grug retrieves content by semantic similarity — a very different question won't surface the right chunks.
- Very large or poorly structured documents may not chunk well. Try splitting the file into smaller topical sections.

---

### `!upload_doc` returns an error about file type

Only `.txt`, `.md`, and `.rst` files are accepted. Convert PDFs or other formats to plain text first.

---

### `!upload_doc` returns an error about file size

The maximum file size is **10 MB**. Split large files into smaller pieces before uploading.

---

## Scheduler & Events

### Scheduled tasks aren't running

1. Confirm the scheduler is running: `!grug_status` should show the scheduler as active.
2. Check that the task is **enabled** — either in the [Web UI Tasks page](web-ui/tasks.md) or via `!list_tasks`.
3. Verify the server's timezone is configured correctly with [`!set_timezone`](discord/admin.md#timezone).
4. Check bot logs for cron errors: `docker compose logs grug --tail 50`.

---

## Docker & Deployment

### Services won't start — "port already in use"

Another process on your machine is using one of Grug's ports (3000, 5432, 8000, 8080). Edit the `ports:` mapping in `docker-compose.yml` to use a different host port:

```yaml
ports:
  - "3001:80"  # change left side only
```

---

### Grug loses all data when I restart

Data should persist in named Docker volumes (`grug_db`, `grug_chroma`, `grug_files`). Running `docker compose down -v` will **delete** these volumes. Use `docker compose down` (without `-v`) to stop services while preserving data.

---

### The postgres service fails its health check

Check that `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in your `.env` match what the postgres service expects:

```bash
docker compose logs postgres --tail 20
```

A common cause is a stale volume from a previous run with different credentials. Remove the volume and let it reinitialise:

```bash
docker compose down
docker volume rm grug_postgres_data
docker compose up -d
```

!!! warning
    This will delete all data in the postgres volume.

---

## MCP Tools

### MCP tools aren't showing up

Check Grug's startup logs for MCP connection errors:

```bash
docker compose logs grug | grep -i mcp
```

Common causes:

- The `command` in your MCP config isn't available in the container's PATH.
- The subprocess failed to start (exit code, missing dependencies).
- JSON in `MCP_SERVER_CONFIGS` is malformed — validate it at [jsonlint.com](https://jsonlint.com).
