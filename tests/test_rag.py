"""Tests for RAG text chunking."""

import pytest


def test_chunk_text_basic():
    """Text shorter than chunk_size is returned as a single chunk."""
    from grug.rag.indexer import _chunk_text
    text = "Hello, world!"
    chunks = _chunk_text(text, chunk_size=100, overlap=10)
    assert chunks == ["Hello, world!"]


def test_chunk_text_splits_long_text():
    """Long text is split into multiple overlapping chunks."""
    from grug.rag.indexer import _chunk_text
    text = "A" * 2500
    chunks = _chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) >= 3
    # Each chunk should be at most chunk_size chars
    for chunk in chunks:
        assert len(chunk) <= 1000


def test_chunk_text_overlap():
    """Consecutive chunks share overlapping content."""
    from grug.rag.indexer import _chunk_text
    text = "x" * 1500
    chunks = _chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) == 2
    # The overlap means the second chunk starts 800 chars in (not 1000)
    assert len(chunks[0]) == 1000
    assert len(chunks[1]) == 700  # 1500 - 800


def test_chunk_empty_text():
    """Empty text returns an empty list."""
    from grug.rag.indexer import _chunk_text
    assert _chunk_text("") == []


def test_collection_name():
    """Collection names are guild-scoped."""
    from grug.rag.indexer import _collection_name
    assert _collection_name(12345) == "guild_12345"
    assert _collection_name(99999) != _collection_name(12345)
