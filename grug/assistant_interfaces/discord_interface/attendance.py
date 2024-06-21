import discord
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.assistant_interfaces.discord_interface.utils import get_user_given_interaction
from grug.db import async_session
from grug.models import EventAttendanceReminderDiscordMessage, EventOccurrence


class EventAttendanceConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="I'm in!",
            custom_id="attending_button",
        )

    async def callback(self, interaction: discord.Interaction):
        async with async_session() as session:
            user = await get_user_given_interaction(interaction, session)
            event_occurrence = await _get_event_attendance_given_interaction(interaction, session)

            # mark the user as attending the event
            if user not in event_occurrence.users_rsvp_yes:
                event_occurrence.users_rsvp_yes.append(user)
                session.add(event_occurrence)
                await session.commit()

        logger.info(
            f"{event_occurrence.event.name} ({event_occurrence.event_date.isoformat()}): "
            f"{user.friendly_name} will attend."
        )

        # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
        # noinspection PyUnresolvedReferences
        await interaction.response.edit_message(
            content=f"{event_occurrence.user_attendance_summary_md}\n\nWill you be attending?\n",
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
            user = await get_user_given_interaction(interaction, session)
            event_occurrence = await _get_event_attendance_given_interaction(interaction, session)

            # mark the user as not attending the event
            if user in event_occurrence.users_rsvp_yes:
                event_occurrence.users_rsvp_yes.remove(user)
                session.add(event_occurrence)
                await session.commit()

        logger.info(
            f"{event_occurrence.event.name} ({event_occurrence.event_date.isoformat()}): "
            f"{user.friendly_name} will not attend."
        )

        # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
        # noinspection PyUnresolvedReferences
        await interaction.response.edit_message(
            content=f"{event_occurrence.user_attendance_summary_md}\n\nWill you be attending?\n",
        )


class DiscordAttendanceCheckView(discord.ui.View):
    def __init__(self):
        super().__init__()

        self.timeout = None
        self.add_item(EventAttendanceConfirmButton())
        self.add_item(EventAttendanceDenyButton())


async def send_discord_attendance_reminder(event_occurrence: EventOccurrence, session: AsyncSession) -> None:
    from grug.assistant_interfaces.discord_interface import wait_for_discord_to_start
    from grug.assistant_interfaces.discord_interface.bot import discord_bot

    await wait_for_discord_to_start()

    for discord_server in event_occurrence.event.group.discord_servers:
        # Get the default discord channel
        if discord_server.discord_bot_channel_id is not None:
            guild_channel = discord_bot.get_channel(
                event_occurrence.event.group.discord_servers[0].discord_bot_channel_id
            )
        else:
            guild_id = discord_server.discord_guild_id
            guild_channel = discord_bot.get_guild(guild_id).system_channel

        # Send the message to discord
        message = await guild_channel.send(
            content=f"{event_occurrence.user_attendance_summary_md}\n\nWill you be attending?\n",
            view=DiscordAttendanceCheckView(),
        )

        session.add(
            EventAttendanceReminderDiscordMessage(
                discord_message_id=message.id,
                event_occurrence=event_occurrence,
            )
        )
        await session.commit()


async def _get_event_attendance_given_interaction(
    interaction: discord.Interaction, session: AsyncSession
) -> EventOccurrence:
    """Get the EventAttendance for the interaction."""
    event_attendance_discord_message: EventAttendanceReminderDiscordMessage = (
        (
            await session.execute(
                select(EventAttendanceReminderDiscordMessage).where(
                    EventAttendanceReminderDiscordMessage.discord_message_id == interaction.message.id
                )
            )
        )
        .scalars()
        .one_or_none()
    )

    if event_attendance_discord_message is None:
        raise ValueError("No attendance message found for this interaction.")

    return event_attendance_discord_message.event_occurrence
