"""Tests for campaign agent tools and the AgentResponse / DM delivery flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AgentResponse dataclass
# ---------------------------------------------------------------------------


def test_agent_response_defaults():
    """AgentResponse has sensible defaults."""
    from grug.agent.core import AgentResponse

    resp = AgentResponse(text="Grug help!")
    assert resp.text == "Grug help!"
    assert resp.dm_files == []


def test_agent_response_with_dm_files():
    """AgentResponse carries DM file attachments."""
    from grug.agent.core import AgentResponse

    resp = AgentResponse(text="Check DMs!", dm_files=[("sheet.pdf", b"%PDF-1.4")])
    assert len(resp.dm_files) == 1
    assert resp.dm_files[0][0] == "sheet.pdf"
    assert resp.dm_files[0][1] == b"%PDF-1.4"


# ---------------------------------------------------------------------------
# GrugDeps._pending_dm_files
# ---------------------------------------------------------------------------


def test_grug_deps_pending_dm_files_default():
    """_pending_dm_files defaults to an empty list and is mutable."""
    from grug.agent.core import GrugDeps

    deps = GrugDeps(guild_id=1, channel_id=2, user_id=3, username="test")
    assert deps._pending_dm_files == []

    # Simulate a tool appending a file.
    deps._pending_dm_files.append(("foo.pdf", b"data"))
    assert len(deps._pending_dm_files) == 1


def test_grug_deps_instances_have_separate_dm_files():
    """Each GrugDeps instance gets its own list (no shared state)."""
    from grug.agent.core import GrugDeps

    a = GrugDeps(guild_id=1, channel_id=2, user_id=3, username="alice")
    b = GrugDeps(guild_id=1, channel_id=2, user_id=4, username="bob")
    a._pending_dm_files.append(("a.pdf", b"a"))
    assert b._pending_dm_files == []


# ---------------------------------------------------------------------------
# DM_FILE sentinel stripping (ai_chat._deliver_response helpers)
# ---------------------------------------------------------------------------


def test_dm_file_regex_strips_sentinels():
    """The _DM_FILE_RE pattern strips [DM_FILE:...] sentinels."""
    from grug.bot.cogs.ai_chat import _DM_FILE_RE

    text = "[DM_FILE:sheet.pdf] Grug made pretty PDF!"
    cleaned = _DM_FILE_RE.sub("", text).strip()
    assert cleaned == "Grug made pretty PDF!"


def test_dm_file_regex_strips_multiple_sentinels():
    """Multiple DM_FILE sentinels are all stripped."""
    from grug.bot.cogs.ai_chat import _DM_FILE_RE

    text = "[DM_FILE:a.pdf] [DM_FILE:b.pdf] Here you go!"
    cleaned = _DM_FILE_RE.sub("", text).strip()
    assert cleaned == "Here you go!"


def test_dm_file_regex_no_sentinel():
    """Normal text without sentinels is unchanged."""
    from grug.bot.cogs.ai_chat import _DM_FILE_RE

    text = "Grug love adventurers!"
    cleaned = _DM_FILE_RE.sub("", text).strip()
    assert cleaned == text


# ---------------------------------------------------------------------------
# _is_admin helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_super_admin(monkeypatch):
    """User in GRUG_SUPER_ADMIN_IDS is detected as admin."""
    monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "123,456")
    import grug.config.settings as s

    s.get_settings.cache_clear()

    from grug.agent.core import GrugDeps
    from grug.agent.tools.campaign_tools import _is_admin

    deps = GrugDeps(guild_id=99, channel_id=1, user_id=123, username="admin")
    ctx = MagicMock()
    ctx.deps = deps

    assert await _is_admin(ctx) is True


@pytest.mark.asyncio
async def test_is_admin_not_admin(monkeypatch):
    """A regular user is not an admin."""
    monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
    import grug.config.settings as s

    s.get_settings.cache_clear()

    from grug.agent.core import GrugDeps
    from grug.agent.tools.campaign_tools import _is_admin

    deps = GrugDeps(guild_id=99, channel_id=1, user_id=999, username="normie")
    ctx = MagicMock()
    ctx.deps = deps

    # Mock DB queries to return no user / no guild config.
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("grug.db.session.get_session_factory", return_value=mock_factory):
        assert await _is_admin(ctx) is False
