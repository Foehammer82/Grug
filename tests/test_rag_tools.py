"""Tests for RAG tool classes: SearchDocumentsTool and ListDocumentsTool.

``mock_settings`` and ``mock_db_session`` are provided by conftest.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# SearchDocumentsTool
# ---------------------------------------------------------------------------

def test_search_documents_tool_metadata():
    """SearchDocumentsTool has the expected name and parameter schema."""
    with patch("grug.agent.tools.rag_tools.DocumentRetriever"):
        from grug.agent.tools.rag_tools import SearchDocumentsTool

        tool = SearchDocumentsTool(guild_id=1)
        assert tool.name == "search_documents"
        assert "query" in tool.parameters["required"]


@pytest.mark.asyncio
async def test_search_documents_tool_returns_formatted_results():
    """run() formats retrieved chunks as a numbered list with filename and text."""
    fake_chunks = [
        {"filename": "rulebook.pdf", "chunk_index": 0, "text": "Attack rolls use d20."},
        {"filename": "rulebook.pdf", "chunk_index": 1, "text": "Saving throws are contested."},
    ]

    with patch("grug.agent.tools.rag_tools.DocumentRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = fake_chunks
        mock_retriever_cls.return_value = mock_retriever

        from grug.agent.tools.rag_tools import SearchDocumentsTool

        tool = SearchDocumentsTool(guild_id=42)
        result = await tool.run(query="combat rules")

    assert "[1]" in result
    assert "[2]" in result
    assert "rulebook.pdf" in result
    assert "Attack rolls use d20." in result
    assert "Saving throws are contested." in result


@pytest.mark.asyncio
async def test_search_documents_tool_returns_empty_message():
    """run() returns a descriptive message when the retriever finds nothing."""
    with patch("grug.agent.tools.rag_tools.DocumentRetriever") as mock_retriever_cls:
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = []
        mock_retriever_cls.return_value = mock_retriever

        from grug.agent.tools.rag_tools import SearchDocumentsTool

        tool = SearchDocumentsTool(guild_id=42)
        result = await tool.run(query="orc lore")

    assert "No relevant documents found" in result


# ---------------------------------------------------------------------------
# ListDocumentsTool
# ---------------------------------------------------------------------------

def test_list_documents_tool_metadata():
    """ListDocumentsTool has the expected name."""
    from grug.agent.tools.rag_tools import ListDocumentsTool

    tool = ListDocumentsTool(guild_id=1)
    assert tool.name == "list_documents"


@pytest.mark.asyncio
async def test_list_documents_tool_returns_documents(mock_db_session):
    """run() lists every indexed document with filename and chunk count."""
    from grug.db.models import Document

    mock_factory, mock_session = mock_db_session

    fake_docs = [
        MagicMock(spec=Document, filename="spellbook.pdf", chunk_count=5, description=None),
        MagicMock(spec=Document, filename="map.pdf", chunk_count=3, description="World map"),
    ]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = fake_docs
    mock_session.execute = AsyncMock(return_value=result_mock)

    with patch("grug.agent.tools.rag_tools.get_session_factory", return_value=mock_factory):
        from grug.agent.tools.rag_tools import ListDocumentsTool

        tool = ListDocumentsTool(guild_id=42)
        result = await tool.run()

    assert "spellbook.pdf" in result
    assert "map.pdf" in result
    assert "World map" in result
    assert "5" in result  # chunk count


@pytest.mark.asyncio
async def test_list_documents_tool_empty_guild(mock_db_session):
    """run() returns a helpful message when no documents are indexed yet."""
    mock_factory, mock_session = mock_db_session

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    with patch("grug.agent.tools.rag_tools.get_session_factory", return_value=mock_factory):
        from grug.agent.tools.rag_tools import ListDocumentsTool

        tool = ListDocumentsTool(guild_id=99)
        result = await tool.run()

    assert "no" in result.lower() or "not" in result.lower()
