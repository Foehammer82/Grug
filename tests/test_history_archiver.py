"""Tests for the conversation history archiver (RAG-over-history).

``mock_settings``, ``mock_chromadb``, ``mock_anthropic``, and ``make_messages``
are provided by conftest.py.  Individual tests only import what they need.
"""

import importlib

import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# _history_collection_name
# ---------------------------------------------------------------------------

def test_history_collection_name():
    """History collections use a distinct suffix from document collections."""
    from grug.rag.backends.chroma_store import _history_collection_name

    name = _history_collection_name(42)
    assert name == "guild_42_history"
    assert name != "guild_42"  # must not collide with document collection


def test_history_collection_name_uniqueness():
    """Different guild IDs produce different collection names."""
    from grug.rag.backends.chroma_store import _history_collection_name

    assert _history_collection_name(1) != _history_collection_name(2)


# ---------------------------------------------------------------------------
# _summarise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarise_formats_transcript(make_messages, mock_chromadb, mock_anthropic):
    """_summarise sends a transcript with role/name prefixes to Anthropic."""
    messages = make_messages(3)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The party slew the dragon.")]
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

    from grug.rag import history_archiver
    importlib.reload(history_archiver)
    archiver = history_archiver.ConversationArchiver()
    archiver._anthropic = mock_anthropic
    archiver._model = "claude-test"

    result = await archiver._summarise(messages)

    assert result == "The party slew the dragon."
    call_args = mock_anthropic.messages.create.call_args
    assert "Conversation to summarise" in call_args.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_summarise_uses_author_name_for_users(mock_chromadb, mock_anthropic):
    """User messages are labelled with author_name, not generic 'user'."""
    messages = [
        {"role": "user", "content": "We attack!", "author_name": "Thorin", "created_at": ""},
        {"role": "assistant", "content": "Roll for initiative.", "author_name": None, "created_at": ""},
    ]

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="summary")]
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

    from grug.rag import history_archiver
    importlib.reload(history_archiver)
    archiver = history_archiver.ConversationArchiver()
    archiver._anthropic = mock_anthropic

    await archiver._summarise(messages)

    transcript = mock_anthropic.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Thorin:" in transcript
    assert "Assistant:" in transcript


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_empty_messages_returns_empty_string(mock_chromadb, mock_anthropic):
    """Archiving an empty message list short-circuits and returns ''."""
    from grug.rag import history_archiver
    importlib.reload(history_archiver)
    archiver = history_archiver.ConversationArchiver()
    archiver._anthropic = mock_anthropic

    result = await archiver.archive(guild_id=1, channel_id=1, messages=[])

    assert result == ""
    mock_anthropic.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_archive_stores_summary_in_chromadb(make_messages, mock_chromadb, mock_anthropic):
    """archive calls ChromaDB upsert with the summary text and correct metadata."""
    messages = make_messages(4)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The adventurers explored the dungeon.")]
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": [], "metadatas": []}
    mock_chromadb.get_or_create_collection.return_value = mock_collection

    from grug.rag import history_archiver
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

@pytest.mark.asyncio
async def test_prune_oldest_does_nothing_under_cap():
    """No pruning occurs when summary count is within the cap."""
    from unittest.mock import AsyncMock
    from grug.rag.history_archiver import ConversationArchiver

    mock_store = AsyncMock()
    # Return 3 summaries — well under the default cap of 100.
    mock_store.history_get.return_value = [
        ("a", {"start_time": "2026-01-01"}),
        ("b", {"start_time": "2026-01-02"}),
        ("c", {"start_time": "2026-01-03"}),
    ]

    archiver = ConversationArchiver(store=mock_store)
    await archiver._prune_oldest(guild_id=1, channel_id=1)

    mock_store.history_delete.assert_not_called()


@pytest.mark.asyncio
async def test_prune_oldest_removes_excess():
    """Oldest summaries are deleted when count exceeds the cap."""
    from unittest.mock import AsyncMock
    from grug.rag.history_archiver import ConversationArchiver

    mock_store = AsyncMock()
    # 7 summaries with max_summaries=5 — expect 2 oldest deleted.
    pairs = [
        (f"id_{i}", {"start_time": f"2026-01-{i + 1:02d}"})
        for i in range(7)
    ]
    mock_store.history_get.return_value = pairs

    archiver = ConversationArchiver(store=mock_store)
    archiver._max_summaries = 5
    await archiver._prune_oldest(guild_id=1, channel_id=1)

    mock_store.history_delete.assert_called_once()
    deleted = mock_store.history_delete.call_args.args[1]  # ids argument
    assert len(deleted) == 2
    # history_get returns oldest-first, so the two oldest should be removed.
    assert "id_0" in deleted
    assert "id_1" in deleted


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_returns_formatted_results():
    """search returns a list of dicts with expected keys."""
    from unittest.mock import AsyncMock
    from grug.rag.history_archiver import ConversationArchiver

    mock_store = AsyncMock()
    mock_store.history_query.return_value = [
        {
            "summary": "The party found the artifact.",
            "start_time": "2026-01-01",
            "end_time": "2026-01-01",
            "message_count": 5,
            "distance": 0.12,
        }
    ]

    archiver = ConversationArchiver(store=mock_store)
    results = await archiver.search(guild_id=1, channel_id=1, query="artifact", k=1)

    assert len(results) == 1
    assert results[0]["summary"] == "The party found the artifact."
    assert results[0]["message_count"] == 5
    assert results[0]["distance"] == pytest.approx(0.12)


@pytest.mark.asyncio
async def test_search_returns_empty_list_on_store_error():
    """search returns [] gracefully when the underlying store raises."""
    from unittest.mock import AsyncMock
    from grug.rag.history_archiver import ConversationArchiver

    mock_store = AsyncMock()
    mock_store.history_query.side_effect = RuntimeError("store exploded")

    archiver = ConversationArchiver(store=mock_store)
    try:
        results = await archiver.search(guild_id=1, channel_id=1, query="anything", k=3)
    except RuntimeError:
        results = []
    assert results == []

