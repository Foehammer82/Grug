"""MCP (Model Context Protocol) tool wrappers for Grug."""

import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from grug.agent.tools.base import BaseTool
from grug.config.settings import get_settings

logger = logging.getLogger(__name__)


class MCPTool(BaseTool):
    """Wraps a single MCP tool as a Grug BaseTool."""

    def __init__(
        self,
        tool_name: str,
        tool_description: str,
        tool_parameters: dict[str, Any],
        session: "ClientSession",
    ) -> None:
        self._name = tool_name
        self._description = tool_description
        self._parameters = tool_parameters
        self._session = session

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def run(self, **kwargs: Any) -> str:
        result = await self._session.call_tool(self._name, arguments=kwargs)
        # MCP returns a list of content blocks; join text blocks
        parts = [
            block.text
            for block in result.content
            if hasattr(block, "text")
        ]
        return "\n".join(parts) if parts else "(no output)"


class MCPToolLoader:
    """Loads tools from one or more MCP servers."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def load_all(self) -> list[MCPTool]:
        """Connect to all configured MCP servers and return their tools."""
        tools: list[MCPTool] = []
        for config in self._settings.mcp_server_configs:
            try:
                server_tools = await self._load_from_config(config)
                tools.extend(server_tools)
                logger.info(
                    "Loaded %d tools from MCP server: %s",
                    len(server_tools),
                    config.get("command"),
                )
            except Exception as exc:
                logger.error("Failed to load MCP server %s: %s", config, exc)
        return tools

    async def _load_from_config(self, config: dict[str, Any]) -> list[MCPTool]:
        params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
        )
        tools: list[MCPTool] = []
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
                for tool in response.tools:
                    schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}
                    tools.append(
                        MCPTool(
                            tool_name=tool.name,
                            tool_description=tool.description or "",
                            tool_parameters=schema,
                            session=session,
                        )
                    )
        return tools
