import datetime

import discord
import pytz
from loguru import logger

from grug.bot_discord import discord_client
from grug.db import async_session
from grug.models import DiscordInteractionAudit, Group
from grug.models_crud import (
    get_distinct_users_who_last_brought_food,
    get_or_create_discord_server_group,
    get_or_create_discord_user,
    get_or_create_discord_user_given_interaction,
)
from grug.reminders import game_session_reminder
from grug.utils import get_interaction_response


@discord_client.tree.command()
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def get_group_settings(interaction: discord.Interaction):
    """Get current group settings."""
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)

        await get_interaction_response(interaction).send_message(
            content=(
                "# Group Settings\n"
                f"**Group Name:** {group.name}\n"
                f"**Group Timezone:** {group.timezone}\n"
                f"**Game Session Schedule:** {group.game_session_cron_schedule}\n"
                f"**Game Session Reminder Time:** {group.game_session_reminder_time}\n"
                f"**Game Session Reminder Days Prior:** {group.game_session_reminder_days_before_event}\n"
                f"**Bot Channel ID:** {group.discord_bot_channel_id}\n"
            ),
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def update_game_session_schedule(interaction: discord.Interaction, cron: str):
    """
    Update the game session event schedule for the group.

    Args:
        interaction (discord.Interaction): The interaction object.
        cron (str): The cron schedule string. (hint: https://crontab.guru/#0_17_*_*_0)
    """
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)

        group.game_session_cron_schedule = cron
        session.add(group)
        await session.commit()

        await get_interaction_response(interaction).send_message(
            content=f"Updated event schedule to: {cron}",
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def trigger_game_session_reminder(interaction: discord.Interaction):
    """Trigger a game session reminder for the group."""
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)

        if not group or not group.id:
            raise ValueError("Group not found.")

        await game_session_reminder(group.id, session)

        await get_interaction_response(interaction).send_message(
            content="Game session reminder triggered",
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_guild=True)
@discord.app_commands.choices(
    time=[discord.app_commands.Choice(name=f"{hour:02d}:00", value=hour) for hour in range(0, 24)]
)
async def update_game_session_reminder(
    interaction: discord.Interaction,
    time: discord.app_commands.Choice[int] | None = None,
    days_prior: int | None = None,
):
    """Update the game session reminder time for the group."""
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)

        session.add(group)
        if time:
            group.game_session_reminder_time = datetime.time(hour=time.value, minute=0)
        if days_prior:
            group.game_session_reminder_days_before_event = days_prior
        await session.commit()
        await session.refresh(group)

        await get_interaction_response(interaction).send_message(
            content=(
                f"Updated reminder time to: {group.game_session_reminder_time} and days "
                f"prior to: {group.game_session_reminder_days_before_event}"
            ),
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def set_bot_channel_id(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the bot channel id for the current group."""
    async with async_session() as session:
        group = await get_or_create_discord_server_group(interaction.guild, session)

        session.add(group)
        group.discord_bot_channel_id = channel.id
        await session.commit()

        await get_interaction_response(interaction).send_message(
            content=f"Updated bot channel to: {channel.name} [{channel.id}]",
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
@discord.app_commands.guild_only()
async def get_food_history(interaction: discord.Interaction):
    """Get the food log for the group."""
    async with async_session() as session:
        group: Group = await get_or_create_discord_server_group(interaction.guild, session)

        if not group or not group.id:
            raise ValueError("Group not found.")

        food_history = await get_distinct_users_who_last_brought_food(group.id, session)
        message = "\n".join(
            [
                f"**{event.astimezone(pytz.timezone(group.timezone)).date().isoformat()}:** {user.friendly_name}"
                for user, event in food_history
            ]
        )

        if message == "":
            message = "No food history found."

        await get_interaction_response(interaction).send_message(
            content=message,
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def update_user_info(
    interaction: discord.Interaction,
    user: discord.Member,
    first_name: str | None = None,
    last_name: str | None = None,
    phone_number: str | None = None,
    on_food_rotation: bool | None = None,
):
    """Update user information."""
    async with async_session() as session:
        db_user = await get_or_create_discord_user(discord_member=user, db_session=session)

        session.add(db_user)

        if first_name:
            db_user.first_name = first_name
        if last_name:
            db_user.last_name = last_name
        if phone_number:
            db_user.phone = phone_number
        if on_food_rotation is not None:
            # TODO: implement on_food_rotation
            logger.error("on_food_rotation is not implemented yet")

        await session.commit()
        await session.refresh(db_user)

        await get_interaction_response(interaction).send_message(
            content=db_user.user_info_summary,
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()


@discord_client.tree.command()
async def update_my_info(
    interaction: discord.Interaction,
    first_name: str | None = None,
    last_name: str | None = None,
    phone_number: str | None = None,
    on_food_rotation: bool | None = None,
):
    """Edit user information."""
    async with async_session() as session:
        db_user = await get_or_create_discord_user_given_interaction(interaction, session)

        session.add(db_user)

        if first_name:
            db_user.first_name = first_name
        if last_name:
            db_user.last_name = last_name
        if phone_number:
            db_user.phone = phone_number
        if on_food_rotation is not None:
            # TODO: implement on_food_rotation
            logger.error("on_food_rotation is not implemented yet")

        await session.commit()
        await session.refresh(db_user)

        await get_interaction_response(interaction).send_message(
            content=db_user.user_info_summary,
            ephemeral=True,
        )

        # audit interaction
        session.add(DiscordInteractionAudit.from_interaction(interaction))
        await session.commit()
