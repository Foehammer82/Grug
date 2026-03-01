"""Tests for the conversation history archiver (RAG-over-history)."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    """Ensure a clean settings instance for every test."""
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    import grug.config.settings as s
    s._settings = None
    yield
    s._settings = None


def _make_messages(n: int) -> list[dict]:
    """Return *n* fake conversation message dicts."""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(
            {
                "role": role,
                "content": f"message {i}",
                "author_name": "Blake" if role == "user" else None,
                "created_at": f"2026-01-{i + 1:02d}T10:00:00",
            }
        )
    return msgs


def _make_archiver(max_summaries: int = 5) -> "ConversationArchiver":  # type: ignore[name-defined]
    """Return a ConversationArchiver with mocked external clients."""
    with patch("grug.rag.history_archiver.get_settings") as mock_get:
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-3-5-sonnet-20241022"
        settings.agent_history_max_summaries = max_summaries
        mock_get.return_value = settings

        with patch("chromadb.PersistentClient"), patch("anthropic.AsyncAnthropic"):
            from grug.rag.history_archiver import ConversationArchiver
            archiver = ConversationArchiver()

    return archiver


# ---------------------------------------------------------------------------
# _history_collection_name
# ---------------------------------------------------------------------------

def test_history_collection_name():
    """History collections use a distinct suffix from document collections."""
    from grug.rag.history_archiver import _history_collection_name

    name = _history_collection_name(42)
    assert name == "guild_42_history"
    assert name != "guild_42"  # must not collide with document collection


def test_history_collection_name_uniqueness():
    """Different guild IDs produce different collection names."""
    from grug.rag.history_archiver import _history_collection_name

    assert _history_collection_name(1) != _history_collection_name(2)


# ---------------------------------------------------------------------------
# _summarise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarise_formats_transcript():
    """_summarise sends a transcript with role/name prefixes to Anthropic."""
    messages = _make_messages(3)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The party slew the dragon.")]

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient"), \
         patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:

        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 100
        mock_get.return_value = settings

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic_cls.return_value = mock_client

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()
        archiver._anthropic = mock_client
        archiver._model = "claude-test"

        result = await archiver._summarise(messages)

    assert result == "The party slew the dragon."
    call_args = mock_client.messages.create.call_args
    assert "Conversation to summarise" in call_args.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_summarise_uses_author_name_for_users():
    """User messages are labelled with author_name, not generic 'user'."""
    messages = [
        {"role": "user", "content": "We attack!", "author_name": "Thorin", "created_at": ""},
        {"role": "assistant", "content": "Roll for initiative.", "author_name": None, "created_at": ""},
    ]

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="summary")]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient"), \
         patch("anthropic.AsyncAnthropic"):
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 100
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()
        archiver._anthropic = mock_client

    await archiver._summarise(messages)
    transcript = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Thorin:" in transcript
    assert "Assistant:" in transcript


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_empty_messages_returns_empty_string():
    """Archiving an empty message list short-circuits and returns ''."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="unused")]

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient"), \
         patch("anthropic.AsyncAnthropic") as mock_cls:
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 100
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        archiver._anthropic = mock_client

        result = await archiver.archive(guild_id=1, channel_id=1, messages=[])

    assert result == ""
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_archive_stores_summary_in_chromadb():
    """archive calls ChromaDB upsert with the summary text and correct metadata."""
    messages = _make_messages(4)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The adventurers explored the dungeon.")]

    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": [], "metadatas": []}

    mock_chroma = MagicMock()
    mock_chroma.get_or_create_collection.return_value = mock_collection

    mock_anthropic_client = AsyncMock()
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient", return_value=mock_chroma), \
         patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 100
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()

        result = await archiver.archive(guild_id=7, channel_id=42, messages=messages)

    assert result == "The adventurers explored the dungeon."
    mock_collection.upsert.assert_called_once()
    upsert_kwargs = mock_collection.upsert.call_args.kwargs
    assert upsert_kwargs["documents"] == ["The adventurers explored the dungeon."]
    meta = upsert_kwargs["metadatas"][0]
    assert meta["guild_id"] == 7
    assert meta["channel_id"] == 42
    assert meta["message_count"] == 4


# ---------------------------------------------------------------------------
# _prune_oldest
# ---------------------------------------------------------------------------

def test_prune_oldest_does_nothing_under_cap():
    """No deletions occur when summary count is within the cap."""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["a", "b", "c"],
        "metadatas": [
            {"channel_id": 1, "start_time": "2026-01-01"},
            {"channel_id": 1, "start_time": "2026-01-02"},
            {"channel_id": 1, "start_time": "2026-01-03"},
        ],
    }

    mock_chroma = MagicMock()
    mock_chroma.get_or_create_collection.return_value = mock_collection

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient", return_value=mock_chroma), \
         patch("anthropic.AsyncAnthropic"):
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 5  # cap=5, have=3 → no pruning
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()
        archiver._prune_oldest(guild_id=1, channel_id=1)

    mock_collection.delete.assert_not_called()


def test_prune_oldest_removes_excess():
    """Oldest summaries are deleted when count exceeds the cap."""
    ids = [f"id_{i}" for i in range(7)]
    metadatas = [{"channel_id": 1, "start_time": f"2026-01-{i + 1:02d}"} for i in range(7)]

    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": ids, "metadatas": metadatas}

    mock_chroma = MagicMock()
    mock_chroma.get_or_create_collection.return_value = mock_collection

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient", return_value=mock_chroma), \
         patch("anthropic.AsyncAnthropic"):
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 5  # have 7, cap 5 → delete 2 oldest
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()
        archiver._prune_oldest(guild_id=1, channel_id=1)

    mock_collection.delete.assert_called_once()
    deleted = mock_collection.delete.call_args.kwargs["ids"]
    assert len(deleted) == 2
    # The two oldest by start_time should be removed
    assert "id_0" in deleted
    assert "id_1" in deleted


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_returns_formatted_results():
    """search returns a list of dicts with expected keys."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["The party found the artifact."]],
        "metadatas": [[{"start_time": "2026-01-01", "end_time": "2026-01-01", "message_count": 5}]],
        "distances": [[0.12]],
    }

    mock_chroma = MagicMock()
    mock_chroma.get_or_create_collection.return_value = mock_collection

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient", return_value=mock_chroma), \
         patch("anthropic.AsyncAnthropic"):
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 100
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()

    results = archiver.search(guild_id=1, channel_id=1, query="artifact", k=1)

    assert len(results) == 1
    assert results[0]["summary"] == "The party found the artifact."
    assert results[0]["message_count"] == 5
    assert results[0]["distance"] == pytest.approx(0.12)


def test_search_returns_empty_list_on_chromadb_error():
    """search returns [] gracefully when ChromaDB raises an exception."""
    mock_collection = MagicMock()
    mock_collection.query.side_effect = RuntimeError("ChromaDB exploded")

    mock_chroma = MagicMock()
    mock_chroma.get_or_create_collection.return_value = mock_collection

    with patch("grug.rag.history_archiver.get_settings") as mock_get, \
         patch("chromadb.PersistentClient", return_value=mock_chroma), \
         patch("anthropic.AsyncAnthropic"):
        settings = MagicMock()
        settings.chroma_persist_dir = ":memory:"
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-test"
        settings.agent_history_max_summaries = 100
        mock_get.return_value = settings

        from grug.rag import history_archiver
        import importlib
        importlib.reload(history_archiver)
        archiver = history_archiver.ConversationArchiver()

    results = archiver.search(guild_id=1, channel_id=1, query="anything", k=3)
    assert results == []
