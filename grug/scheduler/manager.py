"""APScheduler manager for Grug."""

import logging
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

# Mapping from standard Unix cron day_of_week numbers (0=Sun, 1=Mon, ..., 6=Sat, 7=Sun)
# to APScheduler's internal convention (0=Mon, 1=Tue, ..., 5=Sat, 6=Sun).
_UNIX_DOW_TO_APSCHEDULER: dict[str, str] = {
    "0": "6",  # Sunday
    "1": "0",  # Monday
    "2": "1",  # Tuesday
    "3": "2",  # Wednesday
    "4": "3",  # Thursday
    "5": "4",  # Friday
    "6": "5",  # Saturday
    "7": "6",  # Sunday (alternate)
}


def _convert_unix_dow_token(token: str) -> str:
    """Convert a single numeric Unix cron DOW token to APScheduler convention.

    Named tokens (e.g. ``mon``, ``fri``) and wildcards are returned unchanged.
    """
    return _UNIX_DOW_TO_APSCHEDULER.get(token, token)


def _convert_unix_dow_field(dow_expr: str) -> str:
    """Convert a full Unix cron ``day_of_week`` field to APScheduler convention.

    Handles ``*``, simple numbers (``5``), comma lists (``1,3,5``), ranges
    (``1-5``), and step expressions (``1-5/2``, ``*/2``).  Named day
    abbreviations (``mon``, ``fri``, etc.) are left unchanged because
    APScheduler resolves them independently of its numeric convention.
    """
    if dow_expr == "*":
        return dow_expr

    result_parts: list[str] = []
    for part in dow_expr.split(","):
        if "/" in part:
            base, step = part.rsplit("/", 1)
            if "-" in base:
                start, end = base.split("-", 1)
                converted = f"{_convert_unix_dow_token(start)}-{_convert_unix_dow_token(end)}/{step}"
            else:
                converted = f"{_convert_unix_dow_token(base)}/{step}"
        elif "-" in part:
            start, end = part.split("-", 1)
            converted = (
                f"{_convert_unix_dow_token(start)}-{_convert_unix_dow_token(end)}"
            )
        else:
            converted = _convert_unix_dow_token(part)
        result_parts.append(converted)

    return ",".join(result_parts)


def unix_cron_to_trigger(cron_expression: str, timezone: str = "UTC") -> CronTrigger:
    """Create an APScheduler :class:`CronTrigger` from a standard 5-field Unix cron expression.

    APScheduler's ``CronTrigger`` uses ``0=Monday`` for ``day_of_week``, while
    the standard Unix/crontab convention uses ``0=Sunday``.  This function
    converts the ``day_of_week`` field before constructing the trigger so that,
    for example, ``0 8 * * 5`` (Friday 8 AM in Unix cron) is correctly
    scheduled on Friday, not Saturday.

    Args:
        cron_expression: A whitespace-separated 5-field cron string
            (``minute hour day month day_of_week``).
        timezone: IANA timezone name for the cron schedule (e.g. ``"America/New_York"``).
            Defaults to ``"UTC"``.  When a guild has a configured timezone the
            cron fields are interpreted in that local time rather than UTC, so
            ``"0 9 * * 5"`` means Friday 9 AM in the guild's local time.

    Returns:
        A configured :class:`CronTrigger` instance.

    Raises:
        ValueError: If *cron_expression* does not contain exactly 5 fields.
    """
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"Expected 5-field cron expression, got {len(parts)} fields: {cron_expression!r}"
        )
    minute, hour, day, month, dow = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=_convert_unix_dow_field(dow),
        timezone=timezone,
    )


_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def add_date_job(
    func: Callable,
    run_date,
    job_id: str,
    args: list | None = None,
    kwargs: dict | None = None,
) -> str:
    """Schedule a one-time job at *run_date*."""
    scheduler = get_scheduler()
    job = scheduler.add_job(
        func,
        trigger=DateTrigger(run_date=run_date),
        id=job_id,
        args=args or [],
        kwargs=kwargs or {},
        replace_existing=True,
        misfire_grace_time=300,
    )
    return job.id


def add_cron_job(
    func: Callable,
    cron_expression: str,
    job_id: str,
    args: list | None = None,
    kwargs: dict | None = None,
    timezone: str = "UTC",
) -> str:
    """Schedule a recurring job using a cron expression (5-field).

    The *cron_expression* must be a standard Unix 5-field cron string where
    ``day_of_week`` uses the ``0=Sunday`` convention (e.g. ``0 8 * * 5`` means
    Friday 8 AM in the given *timezone*).

    Args:
        func: The callable to execute.
        cron_expression: A 5-field Unix cron string.
        job_id: Unique identifier for the APScheduler job.
        args: Positional arguments forwarded to *func*.
        kwargs: Keyword arguments forwarded to *func*.
        timezone: IANA timezone name for interpreting cron fields (default ``"UTC"``).
    """
    trigger = unix_cron_to_trigger(cron_expression, timezone=timezone)
    scheduler = get_scheduler()
    job = scheduler.add_job(
        func,
        trigger=trigger,
        id=job_id,
        args=args or [],
        kwargs=kwargs or {},
        replace_existing=True,
        misfire_grace_time=300,
    )
    return job.id


def remove_job(job_id: str) -> bool:
    """Remove a job by ID. Returns True if removed."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        return True
    except Exception:
        return False
