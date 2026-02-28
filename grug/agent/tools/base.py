"""Base class for Grug agent tools."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """A callable tool that the agent can invoke."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (used as function name in OpenAI tool call)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description shown to the LLM."""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema object for the tool parameters."""

    @abstractmethod
    async def run(self, **kwargs: Any) -> str:
        """Execute the tool and return a string result."""

    def to_openai_tool(self) -> dict[str, Any]:
        """Return the OpenAI tool definition dict."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
