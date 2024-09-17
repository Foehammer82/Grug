from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from grug.discord_views.attendance import DiscordAttendanceCheckView
from grug.discord_views.food import DiscordFoodBringerSelectionView
from grug.models import EventAttendanceReminderDiscordMessage, EventFoodReminderDiscordMessage
from grug.models_crud import get_distinct_users_who_last_brought_food, get_or_create_next_game_session_event


async def send_attendance_reminder(group_id: int, session: AsyncSession):
    from grug.bot_discord import client

    game_session_event = await get_or_create_next_game_session_event(group_id=group_id, session=session)

    if not game_session_event:
        logger.info("Group ID has no future events, no attendance reminder to send.")
        return

    logger.info(f"Sending attendance reminder for GameSessionEvent ID: {game_session_event.id}")

    # Get the default discord channel
    if game_session_event.group.discord_bot_channel_id is not None:
        guild_channel = client.get_channel(game_session_event.group.discord_bot_channel_id)
    else:
        guild_id = game_session_event.group.discord_guild_id
        guild_channel = client.get_guild(guild_id).system_channel

    # Send the message to discord
    message = await guild_channel.send(
        content=f"{game_session_event.user_attendance_summary_md}\n\nWill you be attending?\n",
        view=DiscordAttendanceCheckView(),
    )

    session.add(
        EventAttendanceReminderDiscordMessage(
            discord_message_id=message.id,
            game_session_event_id=game_session_event.id,
        )
    )
    await session.commit()


async def send_food_reminder(group_id: int, session: AsyncSession):
    from grug.bot_discord import client

    game_session_event = await get_or_create_next_game_session_event(group_id=group_id, session=session)

    if not game_session_event:
        logger.info("Group ID has no future events, no food reminder to send.")
        return

    logger.info(f"Sending food reminder for GameSessionEvent ID: {game_session_event.id}")

    if game_session_event.group_id is None:
        raise ValueError("Event occurrence ID is required to send a food reminder.")

    # Build the food reminder message
    message_content = "The last people to bring food were:"
    for user_assigned_food, event_date in await get_distinct_users_who_last_brought_food(
        group_id=game_session_event.group_id,
        session=session,
    ):
        message_content += f"\n- [{event_date.isoformat()}] " f"{user_assigned_food.friendly_name}"

    # if there is a user assigned to bring food, add that to the message
    if game_session_event.user_assigned_food is not None:
        message_content += (
            f"\n\n{game_session_event.user_assigned_food.friendly_name} volunteered to bring food next.  "
            "Select from list below to change."
        )
    else:
        message_content += f"\n\nGrug want know, who bring food {game_session_event.timestamp.isoformat()}?"

    # Get the default discord channel
    if game_session_event.group.discord_bot_channel_id is not None:
        guild_channel = client.get_channel(game_session_event.group.discord_bot_channel_id)
    else:
        guild_id = game_session_event.group.discord_guild_id
        guild_channel = client.get_guild(guild_id).system_channel

    # Send the message to discord
    message = await guild_channel.send(
        content=message_content,
        view=DiscordFoodBringerSelectionView(group=game_session_event.group),
    )

    # Update the food_event with the message_id
    session.add(
        EventFoodReminderDiscordMessage(
            discord_message_id=message.id,
            game_session_event_id=game_session_event.id,
        )
    )
    await session.commit()


async def game_session_reminder(group_id: int, session: AsyncSession | None = None):
    # TODO: either remove previous reminders from discord when a new one is made for the same event, or have a
    #       way to update all existing reminders.

    if session is None:
        from grug.db import async_session

        async with async_session() as session:
            await send_food_reminder(group_id, session)
            await send_attendance_reminder(group_id, session)

    else:
        await send_food_reminder(group_id, session)
        await send_attendance_reminder(group_id, session)
