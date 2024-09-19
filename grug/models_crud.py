from datetime import datetime

import discord
import pytz
from loguru import logger
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select

from grug.models import DiscordTextChannel, GameSessionEvent, Group, User


async def get_or_create_discord_user(
    discord_member: discord.Member,
    db_session: AsyncSession,
    group: Group | None = None,
) -> User:
    # noinspection Pydantic
    user: User | None = (
        (await db_session.execute(select(User).where(User.discord_member_id == discord_member.id)))
        .scalars()
        .one_or_none()
    )

    if user is None:
        # Create a user to assign to the discord account
        user = User(
            discord_member_id=discord_member.id,
            username=discord_member.name,
        )
        if group and group not in user.groups:
            user.groups.append(group)

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    elif group and group not in user.groups:
        user.groups.append(group)

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    return user


async def get_or_create_discord_user_given_interaction(
    interaction: discord.Interaction,
    db_session: AsyncSession,
) -> User:
    """Get a User for the given discord interaction."""

    return await get_or_create_discord_user(
        discord_member=interaction.user,
        group=await get_or_create_discord_server_group(interaction.guild, db_session) if interaction.guild else None,
        db_session=db_session,
    )


async def get_or_create_discord_server_group(
    guild: discord.Guild,
    db_session: AsyncSession,
) -> Group:
    # noinspection Pydantic
    discord_server_group: Group | None = (
        (await db_session.execute(select(Group).where(Group.discord_guild_id == guild.id))).scalars().one_or_none()
    )

    if discord_server_group is None:
        discord_server_group = Group(
            name=guild.name,
            discord_guild_id=guild.id,
        )
        db_session.add(discord_server_group)
        await db_session.commit()
        await db_session.refresh(discord_server_group)

    return discord_server_group


async def get_or_create_discord_text_channel(
    channel: discord.TextChannel,
    session: AsyncSession,
) -> DiscordTextChannel:
    # noinspection Pydantic
    discord_channel: DiscordTextChannel | None = (
        (await session.execute(select(DiscordTextChannel).where(DiscordTextChannel.discord_channel_id == channel.id)))
        .scalars()
        .one_or_none()
    )

    if discord_channel is None:
        discord_channel = DiscordTextChannel(
            discord_channel_id=channel.id,
            group_id=(await get_or_create_discord_server_group(channel.guild, session)).id,
        )
        session.add(discord_channel)
        await session.commit()
        await session.refresh(discord_channel)

    return discord_channel


async def get_or_create_next_game_session_event(group_id: int, session: AsyncSession) -> GameSessionEvent | None:
    logger.info(f"Creating next event if it does not exist for Event_ID: {group_id}")

    # noinspection Pydantic
    group: Group = (await session.execute(select(Group).where(Group.id == group_id))).scalars().one_or_none()
    if group is None:
        raise ValueError(f"Event {group_id} not found.")

    # Search through the event occurrences and see if any exist after current datetime, if more than one, return just
    # the next one
    query = (
        select(GameSessionEvent)
        .where(GameSessionEvent.group_id == group_id)
        .where(GameSessionEvent.timestamp >= datetime.now(pytz.timezone(group.timezone)))
        .order_by(GameSessionEvent.timestamp)
    )
    future_event_occurrences: list[GameSessionEvent] = list((await session.execute(query)).scalars().all())

    # If none exist, create a new event occurrence for the next event
    if len(future_event_occurrences) == 0:
        if not group.next_game_session_event:
            logger.info(f"No future event occurrences found for Event_ID: {group_id}, and no next event datetime set.")
            return None

        logger.info(f"No future event occurrences found for Event_ID: {group_id}, creating one now.")
        event_occurrence = GameSessionEvent(
            group_id=group_id,
            timestamp=group.next_game_session_event,
        )
        session.add(event_occurrence)
        await session.commit()
        await session.refresh(event_occurrence)

    else:
        event_occurrence = future_event_occurrences[0]

    return event_occurrence


async def get_distinct_users_who_last_brought_food(
    group_id: int, db_session: AsyncSession
) -> list[tuple[User, datetime]]:
    """
    Get the distinct users who last brought food for the group.

    Args:
        group_id: The ID of the group.
        db_session: The database session.
    """

    # Subquery to get the latest timestamp for each group
    subquery = (
        select(GameSessionEvent.user_assigned_food_id, func.max(GameSessionEvent.timestamp).label("latest_timestamp"))
        .group_by(GameSessionEvent.user_assigned_food_id)
        .subquery()
    )

    # Alias for the main table
    main_table = aliased(GameSessionEvent)

    # Join the main table with the subquery to get the latest records
    query = (
        select(main_table)
        .join(
            subquery,
            (main_table.user_assigned_food_id == subquery.c.user_assigned_food_id)
            & (main_table.timestamp == subquery.c.latest_timestamp),
        )
        .where(main_table.group_id == group_id)
        .order_by(main_table.timestamp.desc())
    )

    results = (await db_session.execute(query)).scalars().all()

    return [(obj.user_assigned_food, obj.timestamp) for obj in results]
