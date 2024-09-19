import datetime
import logging

import discord
import pytz
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from grug.models import Group
from grug.models_crud import get_distinct_users_who_last_brought_food


class InterceptLogHandler(logging.Handler):
    """
    Default log handler from examples in loguru documentaion.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord):
        """Intercept standard logging records."""
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
                depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def get_interaction_response(interaction: discord.Interaction) -> discord.InteractionResponse:
    """
    Get the interaction response object from the interaction object.  Used to help with type hinting.
    """
    # noinspection PyTypeChecker
    return interaction.response


async def get_food_history_message(group_id: int, db_session: AsyncSession) -> str:
    # noinspection Pydantic
    group: Group = (await db_session.execute(select(Group).where(Group.id == group_id))).scalars().one_or_none()
    food_history = await get_distinct_users_who_last_brought_food(group_id, db_session)

    message = "## Food\n- "

    food_log: list[str] = []
    for user, timestamp in food_history:
        list_item = f"{timestamp.astimezone(pytz.timezone(group.timezone)).date().isoformat()}: {user.friendly_name}"

        if timestamp > datetime.datetime.now(tz=pytz.utc):
            list_item = f"**{list_item} (Assigned)**"

        food_log.append(list_item)

    message += "\n- ".join(food_log)

    return message
