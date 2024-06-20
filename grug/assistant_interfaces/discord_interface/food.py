import discord
from discord import SelectOption
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.assistant_interfaces.discord_interface.utils import wait_for_discord_to_start
from grug.db import async_session
from grug.models import EventFoodReminderDiscordMessage, EventOccurrence, Group
from grug.utils.food import get_distinct_event_occurrence_food_history


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

            event_occurrence = event_food_reminder_discord_message.event_occurrence

            # Handle when a user is selected
            if selected_user_id:
                event_occurrence.user_assigned_food_id = selected_user_id
                session.add(event_occurrence)
                await session.commit()
                await session.refresh(event_occurrence)

                logger.info(
                    f"Player {event_occurrence.user_assigned_food.friendly_name} selected to bring food for "
                    f"event {event_occurrence.event.id} on {event_occurrence.event_date}"
                )

                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"{event_occurrence.user_assigned_food.friendly_name} scheduled to bring food for "
                    f"{event_occurrence.event.name} on {event_occurrence.event_date.isoformat()}",
                )

            # Handle when no user is selected
            else:
                event_occurrence.user_assigned_food_id = None
                session.add(event_occurrence)
                await session.commit()

                logger.info(
                    f"No player selected to bring food for event {event_occurrence.event.id} "
                    f"on {event_occurrence.event_date}"
                )

                # https://discordpy.readthedocs.io/en/latest/interactions/api.html#discord.InteractionResponse.send_message
                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"No player selected to bring food for {event_occurrence.event.name} "
                    f"on {event_occurrence.event_date.isoformat()}",
                )


class DiscordFoodBringerSelectionView(discord.ui.View):
    """A view for selecting the player who is bringing food."""

    def __init__(self, group: Group):
        super().__init__()

        self.timeout = None
        self.add_item(EventFoodAssignedUserDropDown(group))


async def send_discord_food_reminder(event_occurrence: EventOccurrence, session: AsyncSession) -> None:
    from grug.assistant_interfaces.discord_interface.bot import discord_bot

    # TODO: create a function that will let the assistant form the questions and responses below so they fit the
    #       theme of the bot

    await wait_for_discord_to_start()

    if event_occurrence.event.id is None:
        raise ValueError("Event occurrence ID is required to send a food reminder.")

    # Build the food reminder message
    message_content = "The last people to bring food were:"
    for event_occurrence_food in await get_distinct_event_occurrence_food_history(
        event_id=event_occurrence.event.id, session=session
    ):
        message_content += (
            f"\n- [{event_occurrence_food.event_date.isoformat()}] "
            f"{event_occurrence_food.user_assigned_food.friendly_name}"
        )

    # if there is a user assigned to bring food, add that to the message
    if event_occurrence.user_assigned_food is not None:
        message_content += (
            f"\n\n{event_occurrence.user_assigned_food.friendly_name} volunteered to bring food next.  "
            "Select from list below to change."
        )
    else:
        message_content += f"\n\nGrug want know, who bring food {event_occurrence.event_date.isoformat()}?"

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
            content=message_content,
            view=DiscordFoodBringerSelectionView(group=event_occurrence.event.group),
        )

        # Update the food_event with the message_id
        session.add(
            EventFoodReminderDiscordMessage(
                discord_message_id=message.id,
                event_occurrence=event_occurrence,
            )
        )
        await session.commit()
