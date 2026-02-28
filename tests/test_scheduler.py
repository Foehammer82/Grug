"""Tests for scheduler utilities."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


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
