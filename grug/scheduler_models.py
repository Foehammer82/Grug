# Get SQLAlchemy Base models for the scheduler to surface in the admin interface
from sqlalchemy.orm import declarative_base

from grug.scheduler import _scheduler_data_store

# noinspection PyProtectedMember
_Base = declarative_base(metadata=_scheduler_data_store._metadata)


class ApschedulerSchedule(_Base):  # type: ignore
    """ApScheduler schedules model for use in the admin interface."""

    # noinspection PyProtectedMember
    __table__ = _scheduler_data_store._metadata.tables["apscheduler.schedules"]


class ApSchedulerJob(_Base):  # type: ignore
    """ApScheduler jobs model for use in the admin interface."""

    # noinspection PyProtectedMember
    __table__ = _scheduler_data_store._metadata.tables["apscheduler.jobs"]


class ApSchedulerTask(_Base):  # type: ignore
    """ApScheduler tasks model for use in the admin interface."""

    # noinspection PyProtectedMember
    __table__ = _scheduler_data_store._metadata.tables["apscheduler.tasks"]


class ApSchedulerJobResult(_Base):  # type: ignore
    """ApScheduler job results model for use in the admin interface."""

    # noinspection PyProtectedMember
    __table__ = _scheduler_data_store._metadata.tables["apscheduler.job_results"]
