"""APScheduler manager for Grug."""

import logging
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

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
) -> str:
    """Schedule a recurring job using a cron expression (5-field)."""
    trigger = CronTrigger.from_crontab(cron_expression)
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
