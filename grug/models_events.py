from anyio.from_thread import start_blocking_portal
from loguru import logger
from sqlalchemy import Connection, event
from sqlalchemy.orm import Mapper

from grug import models
from grug.scheduler import update_group_schedules


def _update_group_schedules(mapper: Mapper, connection: Connection, target: models.Group):
    """Update the group schedules when a group or game session event is updated."""
    logger.info(f"sqlalchemy upsert event for model `{target}` triggering `update_group_schedules`")
    with start_blocking_portal() as portal:
        portal.start_task_soon(update_group_schedules, None, target)


event.listen(models.Group, "after_insert", _update_group_schedules)
event.listen(models.Group, "after_update", _update_group_schedules)
event.listen(models.GameSessionEvent, "after_insert", _update_group_schedules)
event.listen(models.GameSessionEvent, "after_update", _update_group_schedules)
