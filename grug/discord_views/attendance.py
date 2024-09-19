import discord
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from grug.db import async_session
from grug.models import EventAttendanceReminderDiscordMessage, GameSessionEvent
from grug.utils import get_interaction_response


class EventAttendanceConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="I'm in!",
            custom_id="attending_button",
        )

    async def callback(self, interaction: discord.Interaction):
        from grug.models_crud import get_or_create_discord_user_given_interaction

        async with async_session() as session:
            user = await get_or_create_discord_user_given_interaction(interaction, session)
            event_occurrence = await _get_event_attendance_given_interaction(interaction, session)

            # mark the user as attending the event
            if user not in event_occurrence.users_rsvp_yes:
                event_occurrence.users_rsvp_yes.append(user)
                session.add(event_occurrence)

            if user in event_occurrence.users_rsvp_no:
                event_occurrence.users_rsvp_no.remove(user)
                session.add(event_occurrence)

            await session.commit()

        logger.info(
            f"{event_occurrence} ({event_occurrence.timestamp.date().isoformat()}): "
            f"{user.friendly_name} will attend."
        )

        # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
        # noinspection PyUnresolvedReferences
        await get_interaction_response(interaction).edit_message(
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
        from grug.models_crud import get_or_create_discord_user_given_interaction

        async with async_session() as session:
            user = await get_or_create_discord_user_given_interaction(interaction, session)
            event_occurrence = await _get_event_attendance_given_interaction(interaction, session)

            if user not in event_occurrence.users_rsvp_no:
                event_occurrence.users_rsvp_no.append(user)
                session.add(event_occurrence)

            if user in event_occurrence.users_rsvp_yes:
                event_occurrence.users_rsvp_yes.remove(user)
                session.add(event_occurrence)

            await session.commit()

        logger.info(
            f"{event_occurrence} ({event_occurrence.timestamp.isoformat()}): " f"{user.friendly_name} will not attend."
        )

        await get_interaction_response(interaction).edit_message(
            content=f"{event_occurrence.user_attendance_summary_md}\n\nWill you be attending?\n",
        )


class DiscordAttendanceCheckView(discord.ui.View):
    def __init__(self):
        super().__init__()

        self.timeout = None
        self.add_item(EventAttendanceConfirmButton())
        self.add_item(EventAttendanceDenyButton())


async def _get_event_attendance_given_interaction(
    interaction: discord.Interaction, session: AsyncSession
) -> GameSessionEvent:
    """Get the EventAttendance for the interaction."""
    # noinspection Pydantic
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

    return event_attendance_discord_message.game_session_event
