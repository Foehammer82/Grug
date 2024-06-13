import discord
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.assistant_interfaces.discord_interface.utils import get_discord_account_given_interaction
from grug.db import async_session
from grug.models import Event, EventAttendance, EventAttendanceDiscordMessage


class EventAttendanceConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="I'm in!",
            custom_id="attending_button",
        )

    async def callback(self, interaction: discord.Interaction):
        async with async_session() as session:
            discord_account = await get_discord_account_given_interaction(interaction, session)
            event_attendance = await _get_event_attendance_given_interaction(interaction, session)

            # mark the user as attending the event
            if discord_account.user and discord_account.user not in event_attendance.users_attended:
                event_attendance.users_attended.append(discord_account.user)
                session.add(event_attendance)
                await session.commit()

        logger.info(
            f"{event_attendance.event.name} ({event_attendance.event_date.isoformat()}): "
            f"{discord_account.user.friendly_name if discord_account.user else interaction.user.name} will attend."
        )

        # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
        # noinspection PyUnresolvedReferences
        await interaction.response.edit_message(
            content=f"{event_attendance.user_attendance_summary_md}\n\nWill you be attending?\n",
        )


class EventAttendanceDenyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.red,
            label="I'm out",
            custom_id="not_attending_button",
        )

    async def callback(self, interaction: discord.Interaction):
        async with async_session() as session:
            discord_account = await get_discord_account_given_interaction(interaction, session)
            event_attendance = await _get_event_attendance_given_interaction(interaction, session)

            # mark the user as not attending the event
            if discord_account.user in event_attendance.users_attended:
                event_attendance.users_attended.remove(discord_account.user)
                session.add(event_attendance)
                await session.commit()

        logger.info(
            f"{event_attendance.event.name} ({event_attendance.event_date.isoformat()}): "
            f"{discord_account.user.friendly_name if discord_account.user else interaction.user.name} will not attend."
        )

        # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
        # noinspection PyUnresolvedReferences
        await interaction.response.edit_message(
            content=f"{event_attendance.user_attendance_summary_md}\n\nWill you be attending?\n",
        )


class DiscordAttendanceCheckView(discord.ui.View):
    def __init__(self):
        super().__init__()

        self.timeout = None
        self.add_item(EventAttendanceConfirmButton())
        self.add_item(EventAttendanceDenyButton())


async def send_discord_attendance_reminder(event: Event, session: AsyncSession) -> EventAttendance:
    from grug.assistant_interfaces.discord_interface import wait_for_discord_to_start
    from grug.assistant_interfaces.discord_interface.bot import discord_bot

    await wait_for_discord_to_start()

    next_attendance_event = await event.get_next_attendance_event(session)

    if next_attendance_event is None:
        raise ValueError("No attendance events found for this group.")

    for discord_server in event.group.discord_servers:
        # Get the default discord channel
        if discord_server.discord_bot_channel_id is not None:
            guild_channel = discord_bot.get_channel(event.group.discord_servers[0].discord_bot_channel_id)
        else:
            guild_id = discord_server.discord_guild_id
            guild_channel = discord_bot.get_guild(guild_id).system_channel

        # Send the message to discord
        message = await guild_channel.send(
            content=f"{next_attendance_event.user_attendance_summary_md}\n\nWill you be attending?\n",
            view=DiscordAttendanceCheckView(),
        )

        # Update the event with the message id
        if next_attendance_event is None:
            raise ValueError("No attendance events found for this group.")

        session.add(
            EventAttendanceDiscordMessage(
                discord_message_id=message.id,
                event_attendance_id=next_attendance_event.id,
            )
        )
        await session.commit()

    return next_attendance_event


async def _get_event_attendance_given_interaction(
    interaction: discord.Interaction, session: AsyncSession
) -> EventAttendance:
    """Get the EventAttendance for the interaction."""
    event_attendance_discord_message: EventAttendanceDiscordMessage = (
        (
            await session.execute(
                select(EventAttendanceDiscordMessage).where(
                    EventAttendanceDiscordMessage.discord_message_id == interaction.message.id
                )
            )
        )
        .scalars()
        .one_or_none()
    )

    if event_attendance_discord_message is None:
        raise ValueError("No attendance message found for this interaction.")

    return event_attendance_discord_message.event_attendance
