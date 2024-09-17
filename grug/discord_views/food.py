import discord
from discord import SelectOption
from loguru import logger
from sqlmodel import select

from grug.db import async_session
from grug.models import EventFoodReminderDiscordMessage, Group


class EventFoodAssignedUserDropDown(discord.ui.Select):
    """A dropdown for selecting the user who is assigned to bring food."""

    def __init__(self, group: Group):
        options: list[SelectOption] = [
            discord.SelectOption(
                label=user.friendly_name,
                description=user.friendly_name,
                value=str(user.id),
                emoji=None,
            )
            for user in group.users
        ]
        options.append(discord.SelectOption(label="nobody", description="No food this week", value="none"))

        super().__init__(
            placeholder="Select a user...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="food_bringer_selection",
        )

    async def callback(self, interaction: discord.Interaction):
        selected_user_id = int(self.values[0]) if self.values[0] != "none" else None

        async with async_session() as session:
            # noinspection Pydantic
            event_food_reminder_discord_message = (
                (
                    await session.execute(
                        select(EventFoodReminderDiscordMessage).where(
                            EventFoodReminderDiscordMessage.discord_message_id == interaction.message.id
                        )
                    )
                )
                .scalars()
                .one_or_none()
            )
            if event_food_reminder_discord_message is None:
                raise ValueError("EventFoodReminderDiscordMessage not found")

            event_occurrence = event_food_reminder_discord_message.game_session_event

            # Handle when a user is selected
            if selected_user_id:
                event_occurrence.user_assigned_food_id = selected_user_id
                session.add(event_occurrence)
                await session.commit()
                await session.refresh(event_occurrence)

                logger.info(
                    f"Player {event_occurrence.user_assigned_food.friendly_name} selected to bring food for "
                    f"event {event_occurrence.group.name} on {event_occurrence.timestamp.isoformat()}"
                )

                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"{event_occurrence.user_assigned_food.friendly_name} scheduled to bring food for "
                    f"{event_occurrence.group.name} on {event_occurrence.timestamp.isoformat()}",
                )

            # Handle when no user is selected
            else:
                event_occurrence.user_assigned_food_id = None
                session.add(event_occurrence)
                await session.commit()

                logger.info(
                    f"No player selected to bring food for {event_occurrence.group.name} "
                    f"on {event_occurrence.timestamp.isoformat()}"
                )

                # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"No player selected to bring food for {event_occurrence.group.name} "
                    f"on {event_occurrence.timestamp.isoformat()}",
                )


class DiscordFoodBringerSelectionView(discord.ui.View):
    """A view for selecting the player who is bringing food."""

    def __init__(self, group: Group):
        super().__init__()

        self.timeout = None
        self.add_item(EventFoodAssignedUserDropDown(group))
