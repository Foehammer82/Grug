from datetime import date, datetime

import discord
from croniter import croniter
from loguru import logger
from sqlalchemy.orm import selectinload
from sqlmodel import select

from grug.db import async_session
from grug.models import BroughtFood, DndSession, FoodSelectionMessage, Player
from grug.settings import settings


async def get_food_history(show_only_active_players: bool = True) -> list[BroughtFood]:
    """
    returns a list of who brought food over the past several sessions, based on the history stored in the database.
    And, will return who is scheduled to bring food for the next session if they have signed up, or null if no one has.

    Args:
        show_only_active_players (bool): If True, only players who are active will be shown. Defaults to True.

    Returns:
        List[BroughtFood]: A list of objects that store who brought food on a given date.

    Raises:
        Exception: If any error occurs during the database session or while fetching the food history.
    """
    async with async_session() as session:
        dnd_session_result = await session.execute(
            select(DndSession)
            .where(DndSession.discord_guild_id == str(settings.discord_server_id))
            .order_by(DndSession.session_start_datetime.desc())  # type: ignore
            .options(selectinload(DndSession.food_bringer))
        )

    dnd_sessions: list[DndSession] = list(dnd_session_result.scalars().all())

    output = []
    player_ids_in_output = []
    for dnd_session in dnd_sessions:
        player = dnd_session.food_bringer
        if (
            player is not None
            and (player.is_active or not show_only_active_players)
            and player.brings_food
            and player.id not in player_ids_in_output
        ):
            player_ids_in_output.append(player.id)

            output.append(
                BroughtFood(
                    by_player=player,
                    on_date=dnd_session.session_start_datetime.date(),
                )
            )

    return output


async def send_discord_food_reminder():
    """Sends a food reminder to the Discord server."""

    from grug.assistant_interfaces.discord_interface import (
        discord_bot,
        wait_for_discord_to_start,
    )

    await wait_for_discord_to_start()

    next_session_datetime: datetime = croniter(
        expr_format=settings.dnd_session_schedule_cron,
        start_time=datetime.now(),
    ).get_next(datetime)

    food_history = await get_food_history()

    logger.info(f"Sending food reminder for {next_session_datetime.date().isoformat()}")

    async with async_session() as session:
        player_result = await session.execute(
            select(Player)
            .where(Player.discord_guild_id == str(settings.discord_server_id))
            .where(Player.is_active == True)  # noqa: E712
            .where(Player.brings_food == True)  # noqa: E712
        )
        players: list[Player] = player_result.scalars().all()
        view = DiscordFoodBringerSelectionView(players=players)

        message_content = "Last people to bring food were:\n"
        for brought_food in food_history:
            message_content += f"\n- [{brought_food.on_date.isoformat()}] {brought_food.by_player.friendly_name}"

        if next_up := (food_history[0] if len(food_history) > 0 and food_history[0].on_date >= date.today() else None):
            message_content += (
                f"\n\n{next_up.by_player.friendly_name} volunteered to bring food next.  "
                "Select from list below to change."
            )
        else:
            message_content += f"\n\nGrug want know, who bring food {next_session_datetime.date().isoformat()}?"

        dnd_session: DndSession | None = (
            (
                await session.execute(
                    select(DndSession).where(DndSession.session_start_datetime == next_session_datetime)
                )
            )
            .scalars()
            .one_or_none()
        )

        if dnd_session is None:
            dnd_session = DndSession(
                discord_guild_id=str(settings.discord_server_id),
                session_start_datetime=next_session_datetime,
            )
            session.add(dnd_session)
            await session.commit()
            await session.refresh(dnd_session)

        if settings.discord_bot_channel_id is not None:
            guild_channel = discord_bot.get_channel(settings.discord_bot_channel_id)
        else:
            guild_channel = discord_bot.get_guild(settings.discord_server_id).system_channel

        message = await guild_channel.send(
            content=message_content,
            view=view,
        )

        session.add(FoodSelectionMessage(discord_message_id=str(message.id), dnd_session_id=dnd_session.id))
        await session.commit()


class DiscordFoodBringerDropdown(discord.ui.Select):
    """A dropdown for selecting the player who is bringing food."""

    def __init__(self, players: list[Player]):
        menu_options = []

        for player in players:
            menu_options.append(
                discord.SelectOption(
                    label=player.friendly_name,
                    description=player.friendly_name,
                    value=str(player.id),
                    emoji=None,
                )
            )

        menu_options.append(discord.SelectOption(label="nobody", description="No food this week", value="none"))

        super().__init__(
            placeholder="Select a player...",
            min_values=1,
            max_values=1,
            options=menu_options,
            custom_id="food_bringer_selection",
        )

    async def callback(self, interaction: discord.Interaction):
        """
        Callback for the food bringer dropdown.

        Args:
            interaction (discord.Interaction): The interaction object.
        """

        player_id: int | None = int(self.values[0]) if self.values[0] != "none" else None
        player_name = {option.value: option.label for option in self.options}[self.values[0]]

        async with async_session() as session:
            food_selection_message: FoodSelectionMessage | None = (
                (
                    await session.execute(
                        select(FoodSelectionMessage).where(
                            FoodSelectionMessage.discord_message_id == str(interaction.message.id)
                        )
                    )
                )
                .scalars()
                .one_or_none()
            )

            if food_selection_message is None:
                raise Exception("food_selection_message should have been instantiated when the " "message was sent")

            if player_id is not None:
                dnd_session: DndSession | None = (
                    (
                        await session.execute(
                            select(DndSession).where(DndSession.id == food_selection_message.dnd_session_id)
                        )
                    )
                    .scalars()
                    .one_or_none()
                )

                dnd_session.food_bringer_player_id = player_id  # type: ignore

                session.add(dnd_session)
                await session.commit()

        if dnd_session:
            logger.info(
                f"Player {player_name} selected to bring food for {dnd_session.session_start_datetime.date().isoformat()}"
            )

            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                f"Grug hear {player_name} bring food " f"{dnd_session.session_start_datetime.date().isoformat()}"
            )


class DiscordFoodBringerSelectionView(discord.ui.View):
    """A view for selecting the player who is bringing food."""

    def __init__(self, players: list[Player]):
        super().__init__()

        self.timeout = None
        self.add_item(DiscordFoodBringerDropdown(players))
