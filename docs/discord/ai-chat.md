# Discord — AI Chat

Grug's primary feature is his AI chat interface. Ask him anything, and he'll respond using the full context of your uploaded documents, glossary, conversation history, and any connected MCP tools.

---

## Talking to Grug

**Mention Grug** in any channel he has access to:

```
@Grug what are the rules for flanking in Pathfinder 2e?
```

Grug will:

1. Search indexed documents for relevant passages.
2. Check the glossary for relevant terms.
3. Retrieve relevant archived conversation history.
4. Call any available tools (e.g. MCP servers).
5. Reply with a contextually aware response.

Long responses are automatically split into multiple messages to respect Discord's 2,000 character limit.

---

## Always-on mode

By default, Grug only responds when mentioned. **Always-on mode** makes Grug respond to *every* message in a channel.

| Command | Permission required | Description |
|---|---|---|
| `!chat_here` | Manage Channels | Toggles always-on mode for the current channel. Run again to turn it off. |
| `!always_on` | Manage Channels | Alias for `!chat_here`. |

!!! warning "Choose the channel carefully"
    Always-on mode can generate a lot of API calls. Use it in a dedicated RP or AI channel rather than your general chat.

---

## Clearing history

Grug maintains a per-channel conversation history so he can refer back to earlier parts of a conversation. If a thread goes off the rails (or you just want a clean slate), you can wipe it:

| Command | Permission required | Description |
|---|---|---|
| `!clear_history` | Manage Messages | Deletes all stored conversation history for the current channel. Cannot be undone. |

!!! note "Archived summaries are not affected"
    `!clear_history` removes only the active context window. Older messages that have already been summarised and archived to the vector store remain available unless you explicitly delete the relevant documents.

---

## How context works

Grug's memory has three layers:

```
┌──────────────────────────────────┐
│  Active context window           │  Most recent N messages (default: 20)
│  (fast, always included)         │
├──────────────────────────────────┤
│  Archived summaries              │  Older messages, summarised + stored as
│  (semantic search)               │  vector embeddings; retrieved by relevance
├──────────────────────────────────┤
│  Indexed documents               │  Files you've uploaded with !upload_doc;
│  (semantic search)               │  retrieved by relevance
└──────────────────────────────────┘
```

The archiver runs automatically when the active context exceeds the configured window size. Summaries are stored per-channel so conversations in `#session-notes` and `#rules-questions` stay separate.

---

## Tips

- Give Grug detailed context upfront — "As a level 5 wizard in our homebrew campaign…" yields much better answers than a bare question.
- Upload your campaign documents with [`!upload_doc`](documents.md) so Grug can quote them accurately.
- Add campaign-specific terms to the [glossary](glossary.md) so Grug uses your world's names and lore consistently.
