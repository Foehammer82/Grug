"""Shared pytest fixtures for Grug's test suite."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Inject required env vars and reset the _settings singleton for every test.

    All tests in the suite need at minimum DISCORD_TOKEN and ANTHROPIC_API_KEY.
    This fixture supplies those so individual tests only need to override the
    specific vars they care about.
    """
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    import grug.config.settings as s

    s._settings = None
    yield
    s._settings = None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db_session():
    """Return a (mock_factory, mock_session) pair wired for async context-manager use.

    The mock_session exposes:
    - ``add``   – plain MagicMock (synchronous)
    - ``commit``  – AsyncMock
    - ``refresh`` – AsyncMock (no-op by default; override with side_effect to set IDs)
    - ``execute`` – AsyncMock (override return_value per-test)

    Usage::

        mock_factory, mock_session = mock_db_session
        mock_session.refresh.side_effect = lambda obj: setattr(obj, "id", 42)
        with patch("my.module.get_session_factory", return_value=mock_factory):
            ...
    """
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_factory, mock_session


# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_chromadb():
    """Patch ``chromadb.PersistentClient`` and yield the mock client instance.

    The yielded object is the *instance* returned by the patched constructor,
    so tests can configure ``get_or_create_collection``, ``query``, etc. on it.
    Also resets the vector store singleton so each test gets a fresh instance
    backed by the mock client.
    """
    import grug.rag.vector_store as vs

    mock_client = MagicMock()
    vs._store = None  # reset singleton before patching
    with patch("chromadb.PersistentClient", return_value=mock_client):
        yield mock_client
    vs._store = None  # clean up after the test


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_anthropic():
    """Patch ``anthropic.AsyncAnthropic`` and yield the mock client instance.

    The mock is pre-configured so that ``messages.create`` returns a response
    whose first content block has ``text = "Test summary."``.  Tests that need
    a different response text should reassign ``mock_anthropic.messages.create``
    after receiving the fixture.
    """
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test summary.")]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# Conversation-message factory
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_messages():
    """Return a factory that creates lists of fake conversation message dicts.

    Usage::

        def test_something(make_messages):
            msgs = make_messages(4)   # 4 alternating user/assistant dicts
    """

    def _factory(n: int = 3) -> list[dict]:
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

    return _factory
