"""Tests for configuration settings."""

import os
import pytest
from unittest.mock import patch


def test_settings_defaults():
    """Settings load correctly with required fields provided."""
    with patch.dict(
        os.environ,
        {
            "DISCORD_TOKEN": "test-discord-token",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
        },
        clear=False,
    ):
        # Reset cached settings
        import grug.config.settings as s
        s._settings = None
        from grug.config.settings import get_settings
        settings = get_settings()
        assert settings.discord_token == "test-discord-token"
        assert settings.anthropic_api_key == "test-anthropic-key"
        assert settings.anthropic_model == "claude-3-5-sonnet-20241022"
        assert settings.discord_prefix == "!"
        assert settings.agent_max_iterations == 10
        assert settings.agent_context_window == 20
        assert settings.mcp_server_configs == []
        s._settings = None  # reset for other tests


def test_settings_mcp_config_json_parsing():
    """MCP server configs can be provided as a JSON string."""
    import json
    mcp_config = json.dumps([{"command": "npx", "args": ["-y", "some-server"]}])
    with patch.dict(
        os.environ,
        {
            "DISCORD_TOKEN": "tok",
            "ANTHROPIC_API_KEY": "key",
            "MCP_SERVER_CONFIGS": mcp_config,
        },
        clear=False,
    ):
        import grug.config.settings as s
        s._settings = None
        from grug.config.settings import get_settings
        settings = get_settings()
        assert len(settings.mcp_server_configs) == 1
        assert settings.mcp_server_configs[0]["command"] == "npx"
        s._settings = None


def test_settings_custom_model():
    """Custom model can be set via environment."""
    with patch.dict(
        os.environ,
        {
            "DISCORD_TOKEN": "tok",
            "ANTHROPIC_API_KEY": "key",
            "ANTHROPIC_MODEL": "claude-3-opus-20240229",
        },
        clear=False,
    ):
        import grug.config.settings as s
        s._settings = None
        from grug.config.settings import get_settings
        settings = get_settings()
        assert settings.anthropic_model == "claude-3-opus-20240229"
        s._settings = None
