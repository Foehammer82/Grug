"""Tests for scheduler utilities."""

import pytest
import calendar
from datetime import datetime, timedelta, timezone


def test_add_cron_job_valid():
    """A valid 5-field cron expression schedules a job successfully."""
    from grug.scheduler.manager import get_scheduler, add_cron_job

    scheduler = get_scheduler()

    async def dummy():
        pass

    job_id = add_cron_job(dummy, "0 9 * * 5", "test_job_1")
    assert job_id == "test_job_1"
    scheduler.remove_job("test_job_1")


def test_add_cron_job_invalid_expression():
    """Invalid cron expression raises ValueError."""
    from grug.scheduler.manager import add_cron_job

    async def dummy():
        pass

    with pytest.raises(ValueError, match="5-field"):
        add_cron_job(dummy, "* * *", "bad_job")


def test_remove_nonexistent_job():
    """Removing a non-existent job returns False without raising."""
    from grug.scheduler.manager import remove_job

    result = remove_job("does_not_exist_xyz")
    assert result is False


def test_add_date_job():
    """A date-triggered one-time job can be added and removed."""
    from grug.scheduler.manager import add_date_job, get_scheduler

    scheduler = get_scheduler()

    async def dummy():
        pass

    run_at = datetime.now(timezone.utc) + timedelta(hours=1)
    job_id = add_date_job(dummy, run_date=run_at, job_id="test_date_job_1")
    assert job_id == "test_date_job_1"
    scheduler.remove_job("test_date_job_1")


# ---------------------------------------------------------------------------
# DOW conversion tests
# ---------------------------------------------------------------------------


def test_unix_cron_to_trigger_friday():
    """Cron '0 8 * * 5' (Unix: Friday) fires on Friday, not Saturday."""
    from grug.scheduler.manager import unix_cron_to_trigger

    # Wednesday March 4, 2026 at 18:26 UTC
    now = datetime(2026, 3, 4, 18, 26, tzinfo=timezone.utc)
    trigger = unix_cron_to_trigger("0 8 * * 5")
    next_fire = trigger.get_next_fire_time(None, now)
    assert next_fire is not None
    # Should be Friday (weekday() == 4 in Python: Mon=0 ... Fri=4)
    assert next_fire.weekday() == 4, (
        f"Expected Friday (weekday=4), got weekday={next_fire.weekday()} "
        f"({calendar.day_name[next_fire.weekday()]}) on {next_fire.date()}"
    )
    # Should fire at 08:00 UTC
    assert next_fire.hour == 8
    assert next_fire.minute == 0


def test_unix_cron_to_trigger_sunday():
    """Cron '0 8 * * 0' (Unix: Sunday) fires on Sunday."""
    from grug.scheduler.manager import unix_cron_to_trigger

    now = datetime(2026, 3, 4, 18, 26, tzinfo=timezone.utc)  # Wednesday
    trigger = unix_cron_to_trigger("0 8 * * 0")
    next_fire = trigger.get_next_fire_time(None, now)
    assert next_fire is not None
    assert next_fire.weekday() == 6  # Sunday in Python (Mon=0 ... Sun=6)


def test_unix_cron_to_trigger_monday():
    """Cron '0 9 * * 1' (Unix: Monday) fires on Monday."""
    from grug.scheduler.manager import unix_cron_to_trigger

    now = datetime(2026, 3, 4, 18, 26, tzinfo=timezone.utc)  # Wednesday
    trigger = unix_cron_to_trigger("0 9 * * 1")
    next_fire = trigger.get_next_fire_time(None, now)
    assert next_fire is not None
    assert next_fire.weekday() == 0  # Monday


def test_unix_cron_to_trigger_all_days():
    """Verify that all Unix cron DOW values 0-6 map to the correct weekday."""
    from grug.scheduler.manager import unix_cron_to_trigger

    # Wednesday March 4, 2026
    now = datetime(2026, 3, 4, 0, 0, tzinfo=timezone.utc)

    # Unix DOW -> expected Python weekday (Mon=0 ... Sun=6)
    unix_dow_to_python_weekday = {
        0: 6,  # Sunday
        1: 0,  # Monday
        2: 1,  # Tuesday
        3: 2,  # Wednesday (next occurrence is March 11)
        4: 3,  # Thursday
        5: 4,  # Friday
        6: 5,  # Saturday
    }

    for unix_dow, expected_weekday in unix_dow_to_python_weekday.items():
        trigger = unix_cron_to_trigger(f"0 8 * * {unix_dow}")
        next_fire = trigger.get_next_fire_time(None, now)
        assert next_fire is not None
        assert next_fire.weekday() == expected_weekday, (
            f"Unix DOW {unix_dow}: expected weekday {expected_weekday} "
            f"({calendar.day_name[expected_weekday]}), "
            f"got {next_fire.weekday()} ({calendar.day_name[next_fire.weekday()]})"
        )


def test_unix_cron_to_trigger_sunday_alt():
    """Unix cron DOW 7 is also Sunday (alternate notation)."""
    from grug.scheduler.manager import unix_cron_to_trigger

    now = datetime(2026, 3, 4, 18, 26, tzinfo=timezone.utc)
    trigger = unix_cron_to_trigger("0 8 * * 7")
    next_fire = trigger.get_next_fire_time(None, now)
    assert next_fire is not None
    assert next_fire.weekday() == 6  # Sunday


def test_unix_cron_to_trigger_invalid():
    """Non-5-field expression raises ValueError."""
    from grug.scheduler.manager import unix_cron_to_trigger

    with pytest.raises(ValueError, match="5-field"):
        unix_cron_to_trigger("0 8 * *")


def test_next_run_schema_friday():
    """ScheduledTaskOut.next_run returns a Friday for cron '0 8 * * 5'."""
    from api.schemas import ScheduledTaskOut
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    task = ScheduledTaskOut(
        id=1,
        guild_id=123,
        channel_id=456,
        type="recurring",
        name="Test",
        prompt="Tell a joke",
        fire_at=None,
        cron_expression="0 8 * * 5",
        user_id=None,
        enabled=True,
        last_run=None,
        source="web",
        created_by=789,
        created_at=now,
    )
    next_run = task.next_run
    assert next_run is not None
    assert next_run.weekday() == 4, (
        f"Expected Friday (weekday=4), got {next_run.weekday()} "
        f"({calendar.day_name[next_run.weekday()]})"
    )


def test_upcoming_runs_schema_recurring():
    """ScheduledTaskOut.upcoming_runs returns multiple Friday occurrences."""
    from api.schemas import ScheduledTaskOut
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    task = ScheduledTaskOut(
        id=1,
        guild_id=123,
        channel_id=456,
        type="recurring",
        name="Test",
        prompt="Tell a joke",
        fire_at=None,
        cron_expression="0 8 * * 5",
        user_id=None,
        enabled=True,
        last_run=None,
        source="web",
        created_by=789,
        created_at=now,
    )
    runs = task.upcoming_runs
    assert len(runs) == 60
    # All should be Fridays at 08:00 UTC
    for run in runs:
        assert run.weekday() == 4, f"Expected Friday, got {calendar.day_name[run.weekday()]}"
        assert run.hour == 8
        assert run.minute == 0


def test_upcoming_runs_schema_once():
    """ScheduledTaskOut.upcoming_runs is empty for once tasks."""
    from api.schemas import ScheduledTaskOut
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    task = ScheduledTaskOut(
        id=2,
        guild_id=123,
        channel_id=456,
        type="once",
        name="One-off",
        prompt="Do something",
        fire_at=now + timedelta(days=1),
        cron_expression=None,
        user_id=None,
        enabled=True,
        last_run=None,
        source="web",
        created_by=789,
        created_at=now,
    )
    assert task.upcoming_runs == []
