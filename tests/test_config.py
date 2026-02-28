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
            "OPENAI_API_KEY": "test-openai-key",
        },
        clear=False,
    ):
        # Reset cached settings
        import grug.config.settings as s
        s._settings = None
        from grug.config.settings import get_settings
        settings = get_settings()
        assert settings.discord_token == "test-discord-token"
        assert settings.openai_api_key == "test-openai-key"
        assert settings.openai_model == "gpt-4o"
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
            "OPENAI_API_KEY": "key",
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
            "OPENAI_API_KEY": "key",
            "OPENAI_MODEL": "gpt-4-turbo",
        },
        clear=False,
    ):
        import grug.config.settings as s
        s._settings = None
        from grug.config.settings import get_settings
        settings = get_settings()
        assert settings.openai_model == "gpt-4-turbo"
        s._settings = None
