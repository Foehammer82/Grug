import asyncio
from typing import Callable, Optional

from loguru import logger

_background_tasks: set = set()


class BackgroundTaskError(Exception):
    pass


def track_background_task(task: asyncio.Task, on_error_callback: Optional[Callable] = None):
    def on_done_callback(t: asyncio.Task):
        _background_tasks.remove(t)
        if t.exception():
            if on_error_callback:
                logger.error(f"Background task with ID {t.get_name()} crashed with exception: {t.exception()}")
                on_error_callback()
            else:
                raise BackgroundTaskError() from t.exception()
        else:
            logger.debug(f"Background task with ID {t.get_name()} stopped normally")

    _background_tasks.add(task)
    logger.debug(f"Added background task with ID {task.get_name()}")
    task.add_done_callback(on_done_callback)
