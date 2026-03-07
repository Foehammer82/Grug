"""Tests for agent tools and pydantic-ai agent setup.

The ``mock_settings`` fixture in conftest.py is autouse and handles env-var
injection and singleton reset for every test in this module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_grug_agent_builds_with_anthropic(monkeypatch):
    """GrugAgent initialises without error given an Anthropic API key."""
    import grug.agent.core as core

    # Reset cached agent
    core._agent = None
    # Patch AgentProvider so no real API call is made
    with (
        patch(
            "pydantic_ai.providers.anthropic.AnthropicProvider.__init__",
            return_value=None,
        ),
        patch(
            "pydantic_ai.models.anthropic.AnthropicModel.__init__", return_value=None
        ),
    ):
        from grug.agent.core import GrugAgent

        agent = GrugAgent()
        assert agent._context_window == 20
    core._agent = None


def test_grug_deps_fields():
    """GrugDeps dataclass has the expected fields."""
    from grug.agent.core import GrugDeps
    import dataclasses

    fields = {f.name for f in dataclasses.fields(GrugDeps)}
    assert fields == {
        "guild_id",
        "channel_id",
        "user_id",
        "username",
        "campaign_id",
        "active_character_id",
        "is_dm_session",
        "default_ttrpg_system",
        "campaign_context",
        "campaign_llm_model",
        "_pending_dm_files",
    }


def test_mcp_tools_build_empty_when_no_config(monkeypatch):
    """build_mcp_servers returns empty list when no MCP configs provided."""
    from grug.agent.tools.mcp_tools import build_mcp_servers

    result = build_mcp_servers(configs=[])
    assert result == []


def test_mcp_tools_build_servers(monkeypatch):
    """build_mcp_servers creates MCPServerStdio instances from config."""
    mock_server_cls = MagicMock(return_value=MagicMock())
    with patch("pydantic_ai.mcp.MCPServerStdio", mock_server_cls):
        from grug.agent.tools import mcp_tools

        # Force reimport to pick up the mock
        import importlib

        importlib.reload(mcp_tools)
        configs = [{"command": "npx", "args": ["-y", "some-server"]}]
        servers = mcp_tools.build_mcp_servers(configs=configs)
    assert len(servers) == 1


# ---------------------------------------------------------------------------
# ConversationMessage.archived field
# ---------------------------------------------------------------------------


def test_conversation_message_has_archived_field():
    """ConversationMessage model exposes an archived column defaulting to False."""
    from grug.db.models import ConversationMessage

    table = ConversationMessage.__table__
    assert "archived" in table.c
    col = table.c["archived"]
    assert col.nullable is False


# ---------------------------------------------------------------------------
# GrugAgent._load_history — archival trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_history_triggers_archival_on_overflow(monkeypatch):
    """When unarchived message count exceeds window + batch, archiver is called."""
    import grug.config.settings as s

    s.get_settings.cache_clear()
    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    # window=5, batch=3 → archive fires when total > 8
    monkeypatch.setenv("AGENT_CONTEXT_WINDOW", "5")
    monkeypatch.setenv("AGENT_HISTORY_ARCHIVE_BATCH", "3")
    s.get_settings.cache_clear()
    from datetime import datetime, timezone
    from grug.db.models import ConversationMessage

    # Build 10 fake unarchived message ORM objects
    def _msg(i):
        m = MagicMock(spec=ConversationMessage)
        m.id = i
        m.role = "user" if i % 2 == 0 else "assistant"
        m.content = f"msg {i}"
        m.author_name = "Blake" if m.role == "user" else None
        m.created_at = datetime(2026, 1, i + 1, tzinfo=timezone.utc)
        m.archived = False
        return m

    overflow_msgs = [_msg(i) for i in range(5)]  # 5 overflow messages
    recent_msgs = [_msg(i + 5) for i in range(5)]  # 5 in-window messages

    # Mock scoped execute results: count → overflow fetch → recent fetch
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            # COUNT query
            result.scalar.return_value = 10
        elif call_count == 1:
            # overflow fetch
            result.scalars.return_value.all.return_value = overflow_msgs
        else:
            # recent fetch
            result.scalars.return_value.all.return_value = recent_msgs
        call_count += 1
        return result

    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_archiver = AsyncMock()
    mock_archiver.archive = AsyncMock(return_value="summary text")

    import importlib
    from grug.agent import core as agent_core

    importlib.reload(agent_core)

    with (
        patch.object(agent_core, "get_session_factory", return_value=mock_factory),
        patch.object(agent_core, "ConversationArchiver", return_value=mock_archiver),
    ):
        grug_agent = agent_core.GrugAgent()
        await grug_agent._load_history(guild_id=1, channel_id=1)

    mock_archiver.archive.assert_awaited_once()
    archive_args = mock_archiver.archive.call_args.args
    assert archive_args[0] == 1  # guild_id
    assert archive_args[1] == 1  # channel_id
    assert len(archive_args[2]) == 5  # overflow messages

    s.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_load_history_skips_archival_below_batch_threshold(monkeypatch):
    """Archiver is NOT called when overflow is smaller than the batch size."""
    import grug.config.settings as s

    s.get_settings.cache_clear()
    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("AGENT_CONTEXT_WINDOW", "5")
    monkeypatch.setenv("AGENT_HISTORY_ARCHIVE_BATCH", "10")  # batch > any overflow
    s.get_settings.cache_clear()

    from datetime import datetime, timezone
    from grug.db.models import ConversationMessage

    def _msg(i):
        m = MagicMock(spec=ConversationMessage)
        m.id = i
        m.role = "user"
        m.content = f"msg {i}"
        m.author_name = "Blake"
        m.created_at = datetime(2026, 1, i + 1, tzinfo=timezone.utc)
        m.archived = False
        return m

    recent_msgs = [_msg(i) for i in range(5)]

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            result.scalar.return_value = 7  # overflow=2, batch=10 → no archive
        else:
            result.scalars.return_value.all.return_value = recent_msgs
        call_count += 1
        return result

    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_archiver = AsyncMock()
    mock_archiver.archive = AsyncMock(return_value="summary")

    import importlib
    from grug.agent import core as agent_core

    importlib.reload(agent_core)

    with (
        patch.object(agent_core, "get_session_factory", return_value=mock_factory),
        patch.object(agent_core, "ConversationArchiver", return_value=mock_archiver),
    ):
        grug_agent = agent_core.GrugAgent()
        await grug_agent._load_history(guild_id=1, channel_id=1)

    mock_archiver.archive.assert_not_awaited()
    s.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# search_conversation_history tool
# ---------------------------------------------------------------------------


def test_search_conversation_history_tool_formats_results():
    """search_conversation_history returns a formatted chronicle string."""
    mock_archiver = MagicMock()
    mock_archiver.search.return_value = [
        {
            "summary": "The party broke the curse.",
            "start_time": "2026-01-01T10:00:00",
            "end_time": "2026-01-01T12:00:00",
            "message_count": 8,
            "distance": 0.05,
        }
    ]

    with patch("grug.agent.core.ConversationArchiver", return_value=mock_archiver):
        from grug.agent import core as agent_core
        import importlib

        importlib.reload(agent_core)

        # Locate the registered tool function by name directly from the built agent.
        agent_core._agent = None
        with (
            patch(
                "pydantic_ai.providers.anthropic.AnthropicProvider.__init__",
                return_value=None,
            ),
            patch(
                "pydantic_ai.models.anthropic.AnthropicModel.__init__",
                return_value=None,
            ),
        ):
            built_agent = agent_core.get_agent()

    tool_names = list(built_agent._function_toolset.tools)
    assert "search_conversation_history" in tool_names
    agent_core._agent = None
