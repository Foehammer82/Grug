"""MCP (Model Context Protocol) helpers for Grug.

pydantic-ai natively supports MCP via MCPServerStdio toolsets, so this module
provides a convenience factory used by the agent core.
"""

import logging
from typing import Any

from grug.config.settings import get_settings

logger = logging.getLogger(__name__)


def build_mcp_servers(configs: list[dict[str, Any]] | None = None):
    """Return a list of MCPServerStdio instances from the provided configs.

    If *configs* is None the value from Settings is used.
    Returns an empty list when pydantic-ai-slim[mcp] is not installed or no
    configs are provided.
    """
    if configs is None:
        configs = get_settings().mcp_server_configs
    if not configs:
        return []

    try:
        from pydantic_ai.mcp import MCPServerStdio
    except ImportError:
        logger.warning(
            "pydantic-ai MCP support not available. "
            "Install 'pydantic-ai-slim[mcp]' to enable MCP servers."
        )
        return []

    servers = []
    for cfg in configs:
        try:
            servers.append(
                MCPServerStdio(
                    cfg["command"],
                    args=cfg.get("args", []),
                    env=cfg.get("env"),
                )
            )
            logger.info(
                "Configured MCP server: %s %s", cfg["command"], cfg.get("args", [])
            )
        except Exception as exc:
            logger.error("Failed to create MCP server from config %s: %s", cfg, exc)
    return servers
