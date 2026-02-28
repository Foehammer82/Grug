"""Tests for agent tools and pydantic-ai agent setup."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    import grug.config.settings as s
    s._settings = None
    yield
    s._settings = None


def test_base_tool_abc_requires_implementation():
    """BaseTool ABC raises TypeError when abstract methods are missing."""
    from grug.agent.tools.base import BaseTool

    with pytest.raises(TypeError):
        BaseTool()  # type: ignore[abstract]


def test_base_tool_concrete_implementation():
    """A concrete BaseTool subclass can be instantiated and run."""
    from grug.agent.tools.base import BaseTool

    class MyTool(BaseTool):
        @property
        def name(self):
            return "my_tool"

        @property
        def description(self):
            return "A test tool"

        @property
        def parameters(self):
            return {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            }

        async def run(self, **kwargs):
            return "result"

    tool = MyTool()
    assert tool.name == "my_tool"
    assert tool.description == "A test tool"
    assert tool.parameters["type"] == "object"


def test_grug_agent_builds_with_anthropic(monkeypatch):
    """GrugAgent initialises without error given an Anthropic API key."""
    import grug.agent.core as core
    # Reset cached agent
    core._agent = None
    # Patch AgentProvider so no real API call is made
    with patch("pydantic_ai.providers.anthropic.AnthropicProvider.__init__", return_value=None), \
         patch("pydantic_ai.models.anthropic.AnthropicModel.__init__", return_value=None):
        from grug.agent.core import GrugAgent
        agent = GrugAgent()
        assert agent._context_window == 20
    core._agent = None


def test_grug_deps_fields():
    """GrugDeps dataclass has the expected fields."""
    from grug.agent.core import GrugDeps
    import dataclasses

    fields = {f.name for f in dataclasses.fields(GrugDeps)}
    assert fields == {"guild_id", "channel_id", "user_id", "username"}


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
