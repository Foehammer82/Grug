"""Tests for configuration settings.

The ``mock_settings`` fixture in conftest.py is autouse and injects
DISCORD_TOKEN + ANTHROPIC_API_KEY and resets the _settings singleton before
and after every test.  Individual tests only need to monkeypatch the specific
environment variable they want to exercise.
"""

import json


def test_settings_defaults():
    """Settings load correctly with required fields provided by conftest."""
    from grug.config.settings import get_settings

    settings = get_settings()
    assert settings.discord_token == "test-token"
    assert settings.anthropic_api_key == "test-key"
    assert settings.anthropic_model == "claude-3-5-sonnet-20241022"
    assert settings.discord_prefix == "!"
    assert settings.agent_max_iterations == 10
    assert settings.agent_context_window == 20
    assert settings.mcp_server_configs == []


def test_settings_mcp_config_json_parsing(monkeypatch):
    """MCP server configs can be provided as a JSON string."""
    mcp_config = json.dumps([{"command": "npx", "args": ["-y", "some-server"]}])
    monkeypatch.setenv("MCP_SERVER_CONFIGS", mcp_config)

    import grug.config.settings as s

    s._settings = None
    from grug.config.settings import get_settings

    settings = get_settings()
    assert len(settings.mcp_server_configs) == 1
    assert settings.mcp_server_configs[0]["command"] == "npx"


def test_settings_custom_model(monkeypatch):
    """Custom model can be set via environment."""
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")

    import grug.config.settings as s

    s._settings = None
    from grug.config.settings import get_settings

    settings = get_settings()
    assert settings.anthropic_model == "claude-3-opus-20240229"


def test_settings_history_archive_defaults():
    """History archive settings have correct defaults."""
    from grug.config.settings import get_settings

    settings = get_settings()
    assert settings.agent_history_archive_batch == 10
    assert settings.agent_history_max_summaries == 100


def test_settings_history_archive_overrides(monkeypatch):
    """History archive settings can be overridden via environment."""
    monkeypatch.setenv("AGENT_HISTORY_ARCHIVE_BATCH", "25")
    monkeypatch.setenv("AGENT_HISTORY_MAX_SUMMARIES", "50")

    import grug.config.settings as s

    s._settings = None
    from grug.config.settings import get_settings

    settings = get_settings()
    assert settings.agent_history_archive_batch == 25
    assert settings.agent_history_max_summaries == 50
