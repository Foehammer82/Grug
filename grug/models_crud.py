from datetime import datetime

import discord
import pytz
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from grug.db import async_session
from grug.models import DiscordServer, DiscordTextChannel, Event, EventOccurrence, Group, User


async def upsert_discord_user_account(
    member: discord.Member,
    discord_server: DiscordServer | None,
    db_session: AsyncSession,
) -> User:
    user: User | None = (
        (await db_session.execute(select(User).where(User.discord_member_id == member.id))).scalars().one_or_none()
    )

    if user is None:
        # Create a user to assign to the discord account
        user = User(
            username=member.name,
            auto_created=True,
            discord_member_id=member.id,
            discord_username=member.name,
        )
        if discord_server and discord_server.group and discord_server.group not in user.groups:
            user.groups.append(discord_server.group)

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    else:
        if discord_server and discord_server.group and discord_server.group not in user.groups:
            user.groups.append(discord_server.group)

            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

    return user


async def get_or_create_discord_server(
    guild: discord.Guild,
    db_session: AsyncSession,
) -> DiscordServer:
    discord_server: DiscordServer | None = (
        (await db_session.execute(select(DiscordServer).where(DiscordServer.discord_guild_id == guild.id)))
        .scalars()
        .one_or_none()
    )

    if discord_server is None:
        # Create a group to assign to the discord server
        group = Group(name=guild.name, auto_created=True)
        db_session.add(group)
        await db_session.commit()
        await db_session.refresh(group)

        # create the discord server
        discord_server = DiscordServer(
            discord_guild_id=guild.id,
            discord_guild_name=guild.name,
            group_id=group.id,
        )
        db_session.add(discord_server)
        await db_session.commit()
        await db_session.refresh(discord_server)

    return discord_server


async def get_or_create_discord_text_channel(
    channel: discord.TextChannel,
    session: AsyncSession,
) -> DiscordTextChannel:
    discord_channel: DiscordTextChannel | None = (
        (await session.execute(select(DiscordTextChannel).where(DiscordTextChannel.discord_channel_id == channel.id)))
        .scalars()
        .one_or_none()
    )

    if discord_channel is None:
        discord_channel = DiscordTextChannel(
            discord_channel_id=channel.id,
            discord_server_id=(await get_or_create_discord_server(channel.guild, session)).id,
        )
        session.add(discord_channel)
        await session.commit()
        await session.refresh(discord_channel)

    return discord_channel


async def get_or_create_next_event_occurrence(event_id: int, session: AsyncSession = None) -> EventOccurrence:
    logger.info(f"Creating next event if it does not exist for Event_ID: {event_id}")

    # If a session is not provided, create one and close it at the end
    close_session_at_end = False
    if session is None:
        close_session_at_end = True
        session = async_session()

    event: Event = (await session.execute(select(Event).where(Event.id == event_id))).scalars().one_or_none()
    if event is None:
        raise ValueError(f"Event {event_id} not found.")

    # Search through the event occurrences and see if any exist after current datetime, if more than one, return just
    # the next one
    current_datetime = datetime.now(pytz.timezone(event.timezone))
    query = (
        select(EventOccurrence)
        .where(EventOccurrence.event_id == event_id)
        .where(EventOccurrence.event_date >= current_datetime.date())
        .order_by(EventOccurrence.event_date, EventOccurrence.event_time)
    )
    future_event_occurrences: list[EventOccurrence] = (await session.execute(query)).scalars().all()

    # If none exist, create a new event occurrence for the next event
    if len(future_event_occurrences) == 0:
        logger.info(f"No future event occurrences found for Event_ID: {event_id}, creating one now.")

        event_occurrence = EventOccurrence(
            event_id=event_id,
            event_date=event.next_event_datetime.date(),
            event_time=event.next_event_datetime.time(),
        )

        session.add(event_occurrence)
        await session.commit()
        await session.refresh(event_occurrence)

    else:
        event_occurrence = future_event_occurrences[0]

    # Close the session if it was created in this function
    if close_session_at_end:
        await session.close()

    return event_occurrence


async def sync_next_event_occurrence_to_event(event_id: int, session: AsyncSession = None) -> None:
    """Syncs the next event occurrence to the event's food and attendance reminder timestamps."""
    # If a session is not provided, create one and close it at the end
    close_session_at_end = False
    if session is None:
        close_session_at_end = True
        session = async_session()

    # Get or create the next event occurrence
    await get_or_create_next_event_occurrence(event_id, session)

    # Close the session if it was created in this function
    if close_session_at_end:
        await session.close()
