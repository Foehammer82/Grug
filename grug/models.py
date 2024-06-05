"""SQLModel classes for the bot's database."""

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from functools import cached_property
from typing import Optional

import discord
from apscheduler.triggers.calendarinterval import CalendarIntervalTrigger
from pydantic import computed_field
from sqlalchemy import BigInteger, Column
from sqlmodel import Field, Relationship, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


class Rsvp(StrEnum):
    """Enum for RSVP status."""

    YES = "yes"
    NO = "no"
    MAYBE = "maybe"
    NO_RESPONSE = "no_response"


class UserGroupLink(SQLModel, table=True):
    __tablename__ = "users_groups_link"
    group_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="groups.id", primary_key=True)


class UserEventAttendanceLink(SQLModel, table=True):
    __tablename__ = "users_events_attendance_link"
    user_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    event_attendance_id: int | None = Field(default=None, foreign_key="event_attendance.id", primary_key=True)
    rsvp: Rsvp = Field(default=Rsvp.NO_RESPONSE)


class User(SQLModel, table=True):
    """
    SQLModel class for a user in the system.

    NOTE: the email is intentionally not required, to make it so that a discord user can auto create a user, we
          don't get an email from discord.  so we allow the email to be null and can later set up account linking
          features as needed in the even a multiple user accounts are create for the same person.

    TODO: setup an event watcher that if a user account marked as auto-created is not tied to a discord account, it
          should get deleted
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str

    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    disabled: bool = False

    assistant_thread_id: str | None = None
    auto_created: bool = False

    groups: list["Group"] = Relationship(
        back_populates="users",
        link_model=UserGroupLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    discord_accounts: list["DiscordAccount"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    brought_food_for: list["EventFood"] = Relationship(back_populates="user_assigned_food")
    event_attendance: list["EventAttendance"] = Relationship(back_populates="users", link_model=UserEventAttendanceLink)
    secrets: Optional["UserSecrets"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    @computed_field
    @property
    def friendly_name(self) -> str:
        """Get the user's friendly name."""
        if self.first_name is not None:
            return self.first_name
        else:
            return self.username

    def __str__(self):
        return self.friendly_name


class UserSecrets(SQLModel, table=True):
    __tablename__ = "users_secrets"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    user: User | None = Relationship(
        back_populates="secrets",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    hashed_password: str


class Group(SQLModel, table=True):
    """
    SQLModel class for a group in the system.

    TODO: setup an event watcher that if a group marked as auto-created is not tied to a discord server, it
          should get deleted
    """

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    name: str | None = None
    auto_created: bool = False

    users: list["User"] = Relationship(
        back_populates="groups",
        link_model=UserGroupLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    events: list["Event"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    discord_servers: list["DiscordServer"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    def __str__(self):
        return self.name


class DiscordAccount(SQLModel, table=True):
    """Discord user model."""

    __tablename__ = "discord_accounts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    user: User | None = Relationship(
        back_populates="discord_accounts",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    discord_member_id: str
    discord_member_name: str | None = None

    @classmethod
    async def get_or_create(
        cls,
        member: discord.Member,
        discord_server: Optional["DiscordServer"],
        db_session: AsyncSession,
    ):
        discord_account: DiscordAccount | None = (
            (await db_session.execute(select(DiscordAccount).where(DiscordAccount.discord_member_id == str(member.id))))
            .scalars()
            .one_or_none()
        )

        if discord_account is None:
            # Create a user to assign to the discord account
            user = User(username=member.name, auto_created=True)
            if discord_server and discord_server.group and discord_server.group not in user.groups:
                user.groups.append(discord_server.group)
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

            # create the discord account
            discord_account = DiscordAccount(
                discord_member_id=str(member.id),
                discord_member_name=member.name,
                user=user,
            )
            db_session.add(discord_account)
            await db_session.commit()
            await db_session.refresh(discord_account)

        return discord_account

    def __str__(self):
        return f"{self.discord_member_name} ({self.discord_member_id})"


class DiscordServer(SQLModel, table=True):
    """SQLModel class for a Discord server."""

    __tablename__ = "discord_servers"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(default=None, foreign_key="groups.id")
    group: Group = Relationship(
        back_populates="discord_servers",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    discord_guild_id: str
    discord_guild_name: str | None = None
    discord_text_channels: list["DiscordTextChannel"] = Relationship(
        back_populates="discord_server",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    @classmethod
    async def get_or_create(cls, guild: discord.Guild, db_session: AsyncSession):
        discord_server: DiscordServer | None = (
            (await db_session.execute(select(DiscordServer).where(DiscordServer.discord_guild_id == str(guild.id))))
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
                discord_guild_id=str(guild.id),
                discord_guild_name=guild.name,
                group=group,
            )
            db_session.add(discord_server)
            await db_session.commit()
            await db_session.refresh(discord_server)

        return discord_server

    def __str__(self):
        return f"{self.discord_guild_name} ({self.discord_guild_id})"


class DiscordTextChannel(SQLModel, table=True):
    """SQLModel class for a Discord text channel."""

    id: int | None = Field(default=None, primary_key=True)

    discord_channel_id: str = Field(index=True)
    assistant_thread_id: str | None = None
    discord_server_id: int = Field(default=None, foreign_key="discord_servers.id")
    discord_server: DiscordServer | None = Relationship(
        back_populates="discord_text_channels",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    @classmethod
    async def get_or_create(cls, channel: discord.TextChannel, session: AsyncSession):
        discord_channel: DiscordTextChannel | None = (
            (
                await session.execute(
                    select(DiscordTextChannel).where(DiscordTextChannel.discord_channel_id == str(channel.id))
                )
            )
            .scalars()
            .one_or_none()
        )

        if discord_channel is None:
            discord_channel = DiscordTextChannel(
                discord_channel_id=str(channel.id),
                discord_server=await DiscordServer.get_or_create(channel.guild, session),
            )
            session.add(discord_channel)
            await session.commit()
            await session.refresh(discord_channel)

        return discord_channel

    def __str__(self):
        return self.discord_channel_id


class EventFood(SQLModel, table=True):
    """Model for tracking food."""

    __tablename__ = "event_food"

    id: int | None = Field(default=None, primary_key=True)
    event_date: date
    event_id: int = Field(default=None, foreign_key="event.id", index=True)
    event: "Event" = Relationship(
        back_populates="food",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user_assigned_food_id: int | None = Field(default=None, foreign_key="users.id")
    user_assigned_food: User | None = Relationship(
        back_populates="brought_food_for",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    food_name: str | None
    food_description: str | None

    discord_messages: list["EventFoodDiscordMessage"] = Relationship(
        back_populates="event_food",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    def __str__(self):
        return f"{self.event.name} on {self.event_date.isoformat()}"


class EventFoodDiscordMessage(SQLModel, table=True):
    """Model to track discord messages for food events."""

    __tablename__ = "event_food_discord_messages"

    discord_message_id: str | None = Field(
        default=None, sa_column=Column(BigInteger(), primary_key=True, autoincrement=True)
    )
    event_food_id: int = Field(default=None, foreign_key="event_food.id", index=True)
    event_food: EventFood = Relationship(
        back_populates="discord_messages",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class EventAttendance(SQLModel, table=True):
    """Model for tracking attendance."""

    __tablename__ = "event_attendance"

    id: int | None = Field(default=None, primary_key=True)
    event_date: date
    event_id: int = Field(default=None, foreign_key="event.id", index=True)
    event: "Event" = Relationship(
        back_populates="attendance",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    users: list[User] = Relationship(
        back_populates="event_attendance",
        link_model=UserEventAttendanceLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    discord_messages: list["EventAttendanceDiscordMessage"] = Relationship(
        back_populates="event_attendance",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class EventAttendanceDiscordMessage(SQLModel, table=True):
    """Model to track discord messages for food events."""

    __tablename__ = "event_attendance_discord_messages"

    discord_message_id: int | None = Field(default=None, primary_key=True)
    event_attendance_id: int = Field(default=None, foreign_key="event_attendance.id", index=True)
    event_attendance: EventAttendance = Relationship(
        back_populates="discord_messages",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class RepeatInterval(StrEnum):
    """Enum for Repeat Interval."""

    DAYS = "Days"
    WEEKS = "Weeks"
    MONTHS = "Months"
    YEARS = "Years"


class Event(SQLModel, table=True):
    """Model for an event."""

    __tablename__ = "event"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    group_id: int | None = Field(default=None, foreign_key="groups.id")
    group: Group | None = Relationship(
        back_populates="events",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # Event Schedule
    event_schedule_start_datetime: datetime = Field(
        description=(
            "The first date and time of the event schedule.  If event is non-recurring, this should be the date of "
            "the event."
        ),
    )
    event_schedule_end_date: date | None = Field(default=None, description="latest possible date the event can occur")
    event_schedule_repeat_count: int | None = Field(default=None, description="number of times to repeat the event")
    event_schedule_repeat_interval: RepeatInterval | None = Field(
        default=None, description="interval to repeat the event"
    )

    # Food Tracking
    track_food: bool = True
    food_reminder_time: time = Field(default=time(hour=11), description="time to send the reminder at")
    food_reminder_days_before_event: int = Field(
        default=3, description="days before the event to send the food reminder"
    )
    food: list[EventFood] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # Attendance Tracking
    track_attendance: bool = True
    attendance_reminder_time: time = Field(default=time(hour=11), description="time to send the reminder at")
    attendance_reminder_days_before_event: int = Field(
        default=2, description="days before the event to send the attendance reminder"
    )
    attendance: list["EventAttendance"] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    @computed_field
    @property
    def users(self) -> list[User]:
        """Get all users tied to the event."""
        return self.group.users

    @computed_field
    @cached_property
    def distinct_food_history(self) -> list[EventFood]:
        # get distinct set of people who last brought food
        distinct_food_bringers: dict[str, EventFood] = {}
        for food_event in self.food:
            if food_event.user_assigned_food:
                user_friendly_name = food_event.user_assigned_food.friendly_name
                if (
                    user_friendly_name not in distinct_food_bringers
                    or food_event.event_date > distinct_food_bringers[user_friendly_name].event_date
                ):
                    distinct_food_bringers[user_friendly_name] = food_event

        distinct_food_bringers_sorted = dict(
            sorted(
                distinct_food_bringers.items(),
                key=lambda item: item[1].event_date,
                reverse=True,
            )
        )

        return list(distinct_food_bringers_sorted.values())

    async def get_next_food_event(self, session: AsyncSession) -> EventFood:
        """Get the next food event."""
        if len(self.distinct_food_history) > 0 and self.distinct_food_history[0].event_date < date.today():
            return self.distinct_food_history[0]
        else:
            event_food = EventFood(
                event_id=self.id,
                event=self,
                event_date=self.get_event_calendar_interval_trigger().next(),
            )

            session.add(event_food)
            await session.commit()
            await session.refresh(event_food)
            return event_food

    def get_event_calendar_interval_trigger(self) -> CalendarIntervalTrigger:
        return CalendarIntervalTrigger(
            start_date=self.event_schedule_start_datetime,
            end_date=self.event_schedule_end_date,
            weeks=(
                self.event_schedule_repeat_count if self.event_schedule_repeat_interval is RepeatInterval.WEEKS else 0
            ),
            days=self.event_schedule_repeat_count if self.event_schedule_repeat_interval is RepeatInterval.DAYS else 0,
            months=(
                self.event_schedule_repeat_count if self.event_schedule_repeat_interval is RepeatInterval.MONTHS else 0
            ),
            minute=self.event_schedule_start_datetime.minute,
            hour=self.event_schedule_start_datetime.hour,
        )

    def get_food_reminder_calendar_interval_trigger(self) -> CalendarIntervalTrigger:
        food_reminder_calendar_interval_trigger = self.get_attendance_reminder_calendar_interval_trigger()
        food_reminder_calendar_interval_trigger.start_date -= timedelta(days=self.food_reminder_days_before_event)
        food_reminder_calendar_interval_trigger.minute = self.food_reminder_time.minute
        food_reminder_calendar_interval_trigger.hour = self.food_reminder_time.hour
        return food_reminder_calendar_interval_trigger

    def get_attendance_reminder_calendar_interval_trigger(self) -> CalendarIntervalTrigger:
        attendance_reminder_calendar_interval_trigger = self.get_event_calendar_interval_trigger()
        attendance_reminder_calendar_interval_trigger.start_date -= timedelta(
            days=self.attendance_reminder_days_before_event
        )
        attendance_reminder_calendar_interval_trigger.minute = self.attendance_reminder_time.minute
        attendance_reminder_calendar_interval_trigger.hour = self.attendance_reminder_time.hour
        return attendance_reminder_calendar_interval_trigger

    def __str__(self):
        return self.name
