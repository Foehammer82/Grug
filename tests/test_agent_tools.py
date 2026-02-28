"""Tests for agent tool definitions."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import grug.config.settings as s
    s._settings = None
    yield
    s._settings = None


def test_base_tool_openai_schema():
    """BaseTool.to_openai_tool() returns correct schema structure."""
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

    schema = MyTool().to_openai_tool()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "my_tool"
    assert "q" in schema["function"]["parameters"]["properties"]


def test_rag_tools_have_correct_names():
    """RAG tools are named as expected."""
    from grug.agent.tools.rag_tools import SearchDocumentsTool, ListDocumentsTool
    assert SearchDocumentsTool(1).name == "search_documents"
    assert ListDocumentsTool(1).name == "list_documents"


def test_scheduling_tools_have_correct_names():
    """Scheduling tools are named as expected."""
    from grug.agent.tools.scheduling_tools import (
        CreateCalendarEventTool,
        ListCalendarEventsTool,
        CreateReminderTool,
        CreateScheduledTaskTool,
    )
    assert CreateCalendarEventTool(1, 1).name == "create_calendar_event"
    assert ListCalendarEventsTool(1).name == "list_calendar_events"
    assert CreateReminderTool(1, 1, 1).name == "create_reminder"
    assert CreateScheduledTaskTool(1, 1, 1).name == "create_scheduled_task"


def test_all_tools_have_valid_openai_schema():
    """All built-in tools produce valid OpenAI tool schema dicts."""
    from grug.agent.tools.rag_tools import SearchDocumentsTool, ListDocumentsTool
    from grug.agent.tools.scheduling_tools import (
        CreateCalendarEventTool,
        ListCalendarEventsTool,
        CreateReminderTool,
        CreateScheduledTaskTool,
    )

    tools = [
        SearchDocumentsTool(1),
        ListDocumentsTool(1),
        CreateCalendarEventTool(1, 1),
        ListCalendarEventsTool(1),
        CreateReminderTool(1, 1, 1),
        CreateScheduledTaskTool(1, 1, 1),
    ]
    for tool in tools:
        schema = tool.to_openai_tool()
        assert schema["type"] == "function"
        fn = schema["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"
