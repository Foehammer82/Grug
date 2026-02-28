"""Base class for Grug agent tools."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """A callable tool that the agent can invoke.

    Note: built-in Grug tools are registered directly on the pydantic-ai Agent
    using the ``@agent.tool`` decorator in ``grug.agent.core``.  This ABC is
    kept for any custom tool implementations or future utility use.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""

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
