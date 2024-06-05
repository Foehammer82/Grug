import discord
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grug.assistant_interfaces.discord_interface.bot import discord_bot
from grug.assistant_interfaces.discord_interface.utils import wait_for_discord_to_start
from grug.db import async_session
from grug.models import Event, EventFood, EventFoodDiscordMessage


class EventFoodAssignedUserDropDown(discord.ui.Select):
    """A dropdown for selecting the user who is assigned to bring food."""

    def __init__(self, food_event: EventFood):
        options = [
            discord.SelectOption(
                label=user.friendly_name,
                description=user.friendly_name,
                value=str(user.id),
                emoji=None,
            )
            for user in food_event.event.group.users
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
            event_food = (
                (
                    await session.execute(
                        select(EventFoodDiscordMessage).where(
                            EventFoodDiscordMessage.discord_message_id == interaction.message.id
                        )
                    )
                )
                .scalars()
                .one_or_none()
            ).event_food

            # Handle when a user is selected
            if selected_user_id:
                event_food.user_assigned_food_id = selected_user_id
                session.add(event_food)
                await session.commit()
                await session.refresh(event_food)

                logger.info(
                    f"Player {event_food.user_assigned_food.friendly_name} selected to bring food for "
                    f"event {event_food.event.id} on {event_food.event_date}"
                )

                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"{event_food.user_assigned_food.friendly_name} scheduled to bring food for "
                    f"{event_food.event.name} on {event_food.event_date.isoformat()}",
                )

            # Handle when no user is selected
            else:
                event_food.user_assigned_food_id = None
                session.add(event_food)
                await session.commit()

                logger.info(
                    f"No player selected to bring food for event {event_food.event.id} " f"on {event_food.event_date}"
                )

                # noinspection PyUnresolvedReferences
                await interaction.response.send_message(
                    f"No player selected to bring food for {event_food.event.name} "
                    f"on {event_food.event_date.isoformat()}",
                )


class DiscordFoodBringerSelectionView(discord.ui.View):
    """A view for selecting the player who is bringing food."""

    def __init__(self, food_event: EventFood):
        super().__init__()

        self.timeout = None
        self.add_item(EventFoodAssignedUserDropDown(food_event))


async def send_discord_food_reminder(event: Event, session: AsyncSession) -> EventFood:
    await wait_for_discord_to_start()

    # TODO: this will DEFINITELY break if there is more than one discord server assigned to the group.
    #       instead, we should link events to a specific discord server
    guild_channel = discord_bot.get_channel(int(event.group.discord_servers[0].discord_guild_id))

    # Build the food reminder message
    message_content = "The last people to bring food were:"
    for brought_food in event.distinct_food_history:
        message_content += (
            f"\n- [{brought_food.event_date.isoformat()}] {brought_food.user_assigned_food.friendly_name}"
        )

    # Get the next food event
    next_food_event = await event.get_next_food_event(session)

    # if there is a user assigned to bring food, add that to the message
    if next_food_event.user_assigned_food is not None:
        message_content += (
            f"\n\n{next_food_event.user_assigned_food.friendly_name} volunteered to bring food next.  "
            "Select from list below to change."
        )
    else:
        message_content += f"\n\nGrug want know, who bring food {next_food_event.event_date.isoformat()}?"

    discord_bot.add_view(DiscordFoodBringerSelectionView(next_food_event))

    # Send the message to discord
    message = await guild_channel.send(
        content=message_content,
        view=DiscordFoodBringerSelectionView(food_event=next_food_event),
    )

    # Update the food_event with the message_id
    session.add(
        EventFoodDiscordMessage(
            discord_message_id=message.id,
            event_food_id=next_food_event.id,
            event_food=next_food_event,
        )
    )
    await session.commit()

    return next_food_event
