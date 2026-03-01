"""Tests for scheduling and calendar tool classes.

``mock_settings`` and ``mock_db_session`` are provided by conftest.py.
"""

from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(mock_session, object_id: int):
    """Configure mock_session.refresh to stamp a primary-key ID onto the object."""

    async def _set_id(obj):
        obj.id = object_id

    mock_session.refresh = AsyncMock(side_effect=_set_id)


# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------

def test_tool_names_and_required_params():
    """Each scheduling tool reports its expected name and required parameters."""
    with patch("grug.agent.tools.scheduling_tools._ensure_guild"), \
         patch("grug.agent.tools.scheduling_tools.get_session_factory"), \
         patch("grug.agent.tools.scheduling_tools.add_cron_job"), \
         patch("grug.agent.tools.scheduling_tools.add_date_job"):
        from grug.agent.tools.scheduling_tools import (
            CreateCalendarEventTool,
            CreateReminderTool,
            CreateScheduledTaskTool,
            ListCalendarEventsTool,
        )

    assert CreateCalendarEventTool(1, 2).name == "create_calendar_event"
    assert "title" in CreateCalendarEventTool(1, 2).parameters["required"]
    assert ListCalendarEventsTool(1).name == "list_calendar_events"
    assert CreateReminderTool(1, 2, 3).name == "create_reminder"
    assert CreateScheduledTaskTool(1, 2, 3).name == "create_scheduled_task"


# ---------------------------------------------------------------------------
# CreateCalendarEventTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_calendar_event_tool_persists_record(mock_db_session):
    """run() inserts a CalendarEvent row with the correct field values."""
    from grug.db.models import CalendarEvent

    mock_factory, mock_session = mock_db_session
    _make_db(mock_session, object_id=99)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory), \
         patch("grug.agent.tools.scheduling_tools._ensure_guild"):
        from grug.agent.tools.scheduling_tools import CreateCalendarEventTool

        tool = CreateCalendarEventTool(guild_id=1, user_id=2)
        result = await tool.run(
            title="Session Zero",
            start_time="2026-03-01T19:00:00",
            description="Our first session",
        )

    mock_session.add.assert_called_once()
    event_arg = mock_session.add.call_args[0][0]
    assert isinstance(event_arg, CalendarEvent)
    assert event_arg.title == "Session Zero"
    assert event_arg.guild_id == 1
    assert event_arg.description == "Our first session"
    assert "Session Zero" in result
    assert "99" in result  # event ID from refresh


@pytest.mark.asyncio
async def test_create_calendar_event_tool_commits(mock_db_session):
    """run() commits the session after adding the event."""
    mock_factory, mock_session = mock_db_session
    _make_db(mock_session, object_id=1)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory), \
         patch("grug.agent.tools.scheduling_tools._ensure_guild"):
        from grug.agent.tools.scheduling_tools import CreateCalendarEventTool

        tool = CreateCalendarEventTool(guild_id=1, user_id=2)
        await tool.run(title="Test Event", start_time="2026-04-01T12:00:00")

    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# ListCalendarEventsTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_calendar_events_tool_formats_output(mock_db_session):
    """run() lists upcoming events by title."""
    from grug.db.models import CalendarEvent

    mock_factory, mock_session = mock_db_session
    now = datetime.now(timezone.utc)

    fake_events = [
        MagicMock(
            spec=CalendarEvent,
            title="Dragon Hunt",
            start_time=now + timedelta(days=1),
            end_time=None,
        ),
        MagicMock(
            spec=CalendarEvent,
            title="Inn Gathering",
            start_time=now + timedelta(days=3),
            end_time=None,
        ),
    ]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = fake_events
    mock_session.execute = AsyncMock(return_value=result_mock)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory):
        from grug.agent.tools.scheduling_tools import ListCalendarEventsTool

        tool = ListCalendarEventsTool(guild_id=1)
        result = await tool.run()

    assert "Dragon Hunt" in result
    assert "Inn Gathering" in result


@pytest.mark.asyncio
async def test_list_calendar_events_tool_empty(mock_db_session):
    """run() returns a helpful message when there are no upcoming events."""
    mock_factory, mock_session = mock_db_session
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory):
        from grug.agent.tools.scheduling_tools import ListCalendarEventsTool

        tool = ListCalendarEventsTool(guild_id=1)
        result = await tool.run()

    assert "no" in result.lower() or "upcoming" in result.lower()


# ---------------------------------------------------------------------------
# CreateReminderTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_reminder_tool_schedules_date_job(mock_db_session):
    """run() persists a Reminder row and schedules a one-time job with the correct ID."""
    from grug.db.models import Reminder

    mock_factory, mock_session = mock_db_session
    _make_db(mock_session, object_id=7)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory), \
         patch("grug.agent.tools.scheduling_tools._ensure_guild"), \
         patch("grug.agent.tools.scheduling_tools.add_date_job") as mock_add_date:
        from grug.agent.tools.scheduling_tools import CreateReminderTool

        tool = CreateReminderTool(guild_id=1, user_id=2, channel_id=3)
        result = await tool.run(message="Bring snacks!", remind_at="2026-05-01T18:00:00")

    mock_session.add.assert_called_once()
    reminder_arg = mock_session.add.call_args[0][0]
    assert isinstance(reminder_arg, Reminder)
    assert reminder_arg.message == "Bring snacks!"

    mock_add_date.assert_called_once()
    assert mock_add_date.call_args.kwargs["job_id"] == "reminder_7"
    assert "7" in result


@pytest.mark.asyncio
async def test_create_reminder_tool_default_user(mock_db_session):
    """run() targets the tool owner when no explicit user_id is given."""
    from grug.db.models import Reminder

    mock_factory, mock_session = mock_db_session
    _make_db(mock_session, object_id=1)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory), \
         patch("grug.agent.tools.scheduling_tools._ensure_guild"), \
         patch("grug.agent.tools.scheduling_tools.add_date_job"):
        from grug.agent.tools.scheduling_tools import CreateReminderTool

        tool = CreateReminderTool(guild_id=1, user_id=42, channel_id=3)
        await tool.run(message="Meeting tonight", remind_at="2026-06-01T20:00:00")

    reminder_arg = mock_session.add.call_args[0][0]
    assert reminder_arg.user_id == 42  # defaults to the tool's user_id


# ---------------------------------------------------------------------------
# CreateScheduledTaskTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_scheduled_task_tool_schedules_cron(mock_db_session):
    """run() persists a ScheduledTask row and schedules a cron job."""
    from grug.db.models import ScheduledTask

    mock_factory, mock_session = mock_db_session
    _make_db(mock_session, object_id=3)

    with patch("grug.agent.tools.scheduling_tools.get_session_factory", return_value=mock_factory), \
         patch("grug.agent.tools.scheduling_tools._ensure_guild"), \
         patch("grug.agent.tools.scheduling_tools.add_cron_job") as mock_add_cron:
        from grug.agent.tools.scheduling_tools import CreateScheduledTaskTool

        tool = CreateScheduledTaskTool(guild_id=1, channel_id=2, user_id=5)
        result = await tool.run(
            name="Weekly recap",
            prompt="Summarize this week's adventures",
            cron_expression="0 9 * * 1",
        )

    mock_session.add.assert_called_once()
    task_arg = mock_session.add.call_args[0][0]
    assert isinstance(task_arg, ScheduledTask)
    assert task_arg.name == "Weekly recap"
    assert task_arg.cron_expression == "0 9 * * 1"

    mock_add_cron.assert_called_once()
    assert mock_add_cron.call_args.kwargs["cron_expression"] == "0 9 * * 1"
    assert mock_add_cron.call_args.kwargs["job_id"] == "task_3"

    assert "Weekly recap" in result
    assert "0 9 * * 1" in result
