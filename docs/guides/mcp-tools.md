# Guide — MCP Tool Extensions

Grug supports the **Model Context Protocol (MCP)**, an open standard that lets you attach external tool servers to the AI agent. This means you can extend what Grug can *do* — beyond his built-in capabilities — without modifying the core codebase.

---

## What is MCP?

MCP (Model Context Protocol) defines a standard way for AI models to call tools hosted in external processes. An MCP server exposes a set of tools (functions), and Grug's agent can discover and call them during a conversation.

Common uses:

- Querying a custom database or API (e.g. your campaign tracker, encounter builder, or world-map service)
- Running dice-rolling logic with custom rules
- Fetching live data (weather, moon phases, random tables)
- Wrapping an existing script or CLI tool as a Grug capability

---

## Configuration

Set the `MCP_SERVER_CONFIGS` environment variable to a **JSON array** of server config objects.

```dotenv title=".env"
MCP_SERVER_CONFIGS='[{"name":"dice","command":"uv","args":["run","mcp_dice_server.py"]},{"name":"worldmap","url":"http://localhost:9000/mcp"}]'
```

---

## Config schema

Each entry in the array can be one of two forms:

### Stdio server (subprocess)

Grug launches the server as a local subprocess and communicates over stdin/stdout.

```json
{
  "name": "my-tool-server",
  "command": "uv",
  "args": ["run", "my_mcp_server.py"],
  "env": {
    "SOME_API_KEY": "secret"
  }
}
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | A unique name for this server (used in logs). |
| `command` | Yes | Executable to run (e.g. `python`, `node`, `uv`). |
| `args` | No | List of arguments passed to the command. |
| `env` | No | Extra environment variables for the subprocess. |

### HTTP/SSE server (remote)

Grug connects to an already-running MCP server over HTTP.

```json
{
  "name": "remote-tools",
  "url": "http://my-mcp-server.local:9000/mcp"
}
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | A unique name for this server. |
| `url` | Yes | Full URL of the MCP endpoint. |

---

## Example: adding a custom dice roller

1. Write (or download) an MCP-compatible dice server. A minimal example using the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk):

```python title="mcp_dice_server.py"
from mcp.server.fastmcp import FastMCP
import random

mcp = FastMCP("dice")

@mcp.tool()
def roll_dice(sides: int = 6, count: int = 1) -> str:
    """Roll one or more dice with the given number of sides."""
    rolls = [random.randint(1, sides) for _ in range(count)]
    return f"Rolled {count}d{sides}: {rolls} (total: {sum(rolls)})"

if __name__ == "__main__":
    mcp.run()
```

2. Add the server to your `.env`:

```dotenv
MCP_SERVER_CONFIGS='[{"name":"dice","command":"uv","args":["run","mcp_dice_server.py"]}]'
```

3. Restart Grug. He will now be able to call `roll_dice` as a tool when relevant.

---

## Discovering available tools

Ask Grug directly:

```
@Grug what tools do you have available?
```

He'll list all tools from built-in sources and any connected MCP servers.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| MCP tools don't appear | Grug failed to connect to the server at startup — check logs with `docker compose logs grug` |
| `command not found` in logs | The executable in `command` isn't available in the container's PATH |
| Tool calls time out | The MCP server process is slow to start; consider using an HTTP server instead of stdio |
