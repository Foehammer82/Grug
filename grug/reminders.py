from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from grug.discord_views.attendance import DiscordAttendanceCheckView
from grug.discord_views.food import DiscordFoodBringerSelectionView
from grug.models import EventAttendanceReminderDiscordMessage, EventFoodReminderDiscordMessage
from grug.models_crud import get_or_create_next_game_session_event
from grug.utils import get_food_assignment_log_text


async def send_attendance_reminder(group_id: int, session: AsyncSession):
    from grug.bot_discord import discord_client

    game_session_event = await get_or_create_next_game_session_event(group_id=group_id, session=session)

    if not game_session_event:
        logger.info("Group ID has no future events, no attendance reminder to send.")
        return

    logger.info(f"Sending attendance reminder for GameSessionEvent ID: {game_session_event.id}")

    # Get the default discord channel
    if game_session_event.group.discord_bot_channel_id is not None:
        guild_channel = discord_client.get_channel(game_session_event.group.discord_bot_channel_id)
    else:
        guild_id = game_session_event.group.discord_guild_id
        guild_channel = discord_client.get_guild(guild_id).system_channel

    # Send the message to discord
    message = await guild_channel.send(
        content=f"{game_session_event.user_attendance_summary_md}\n\nWill you be attending?\n\n",
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
    from grug.bot_discord import discord_client

    # Get the next event
    game_session_event = await get_or_create_next_game_session_event(group_id=group_id, session=session)

    # Validate the event
    if not game_session_event:
        logger.info("Group ID has no future events, no food reminder to send.")
        return
    if game_session_event.group_id is None:
        raise ValueError("Event occurrence ID is required to send a food reminder.")

    # Send the food reminder
    logger.info(f"Sending food reminder for GameSessionEvent ID: {game_session_event.id}")

    # Build the food reminder message
    message_content = "## Food\n"
    message_content += await get_food_assignment_log_text(group_id, session)

    # Expand the messge for select box instructions
    if game_session_event.user_assigned_food is not None:
        message_content += "\n\nSelect from list below to change."
    else:
        message_content += f"\n\nGrug want know, who bring food on {game_session_event.timestamp.date().isoformat()}?"

    # Get the default discord channel
    if game_session_event.group.discord_bot_channel_id is not None:
        guild_channel = discord_client.get_channel(game_session_event.group.discord_bot_channel_id)
    else:
        guild_id = game_session_event.group.discord_guild_id
        guild_channel = discord_client.get_guild(guild_id).system_channel

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
    # TODO: when subsequent reminders are sent, remove all previous reminders for the same event.

    if session is None:
        from grug.db import async_session

        async with async_session() as session:
            # TODO: have a button to make the session as canceld (toggle button that can be toggled back on if needed)
            #       - when a session is canceled, all reminders for that session should be removed
            #       - if the canceled session is uncanceled, the reminders should be re-added
            #       - if canceled, set whoever is assigned to food to null
            await send_attendance_reminder(group_id, session)
            await send_food_reminder(group_id, session)

    else:
        await send_attendance_reminder(group_id, session)
        await send_food_reminder(group_id, session)
