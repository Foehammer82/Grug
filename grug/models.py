"""SQLModel classes for the bot's database."""

from datetime import datetime, time, timedelta, timezone
from enum import StrEnum, auto

import pytz
import sqlalchemy as sa
from apscheduler.triggers.cron import CronTrigger
from pydantic import computed_field, field_validator
from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel._compat import SQLModelConfig

from grug.settings import TimeZone, settings


class SQLModelValidation(SQLModel):
    """
    Helper class to allow for validation in SQLModel classes with table=True
    """

    model_config = SQLModelConfig(from_attributes=True, validate_assignment=True)


class RepeatInterval(StrEnum):
    WEEKLY = auto()
    MONTHLY = auto()


class UserGroupLink(SQLModelValidation, table=True):
    __tablename__ = "users_groups_link"
    group_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="groups.id", primary_key=True)


class UserEventOccurrenceRsvpYesLink(SQLModelValidation, table=True):
    __tablename__ = "user_game_session_event_rsvp_yes_link"
    user_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    event_attendance_id: int | None = Field(default=None, foreign_key="game_session_event.id", primary_key=True)


class UserEventOccurrenceRsvpNoLink(SQLModelValidation, table=True):
    __tablename__ = "user_game_session_event_rsvp_no_link"
    user_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    event_attendance_id: int | None = Field(default=None, foreign_key="game_session_event.id", primary_key=True)


class User(SQLModelValidation, table=True):
    """
    SQLModel class for a user in the system.

    NOTE: the email is intentionally not required, to make it so that a discord user can auto create a user, we
          don't get an email from discord.  so we allow the email to be null and can later set up account linking
          features as needed in the even a multiple user accounts are create for the same person.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    discord_member_id: int | None = Field(default=None, sa_column=sa.Column(sa.BigInteger(), index=True))

    username: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    disabled: bool = False
    is_admin: bool = False

    assistant_thread_id: str | None = None

    groups: list["Group"] = Relationship(
        back_populates="users",
        link_model=UserGroupLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # Event Tracking
    brought_food_for: list["GameSessionEvent"] = Relationship(back_populates="user_assigned_food")
    game_session_event_rsvp_yes: list["GameSessionEvent"] = Relationship(
        back_populates="users_rsvp_yes", link_model=UserEventOccurrenceRsvpYesLink
    )
    game_session_event_rsvp_no: list["GameSessionEvent"] = Relationship(
        back_populates="users_rsvp_no", link_model=UserEventOccurrenceRsvpNoLink
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


class Group(SQLModelValidation, table=True):
    """
    SQLModel class for a group in the system.
    """

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    discord_guild_id: int = Field(sa_column=sa.Column(sa.BigInteger(), index=True))

    name: str
    timezone: TimeZone = Field(default=settings.timezone)
    discord_bot_channel_id: int | None = Field(sa_column=sa.Column(sa.BigInteger(), nullable=True, default=None))

    # Game Session Tracking
    game_session_cron_schedule: str | None = None
    game_session_reminder_days_before_event: int = 3
    game_session_reminder_time: time = time(hour=11)
    game_session_track_food: bool = True
    game_session_track_attendance: bool = True
    game_session_events: list["GameSessionEvent"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    users: list["User"] = Relationship(
        back_populates="groups",
        link_model=UserGroupLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    discord_text_channels: list["DiscordTextChannel"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    @property
    def game_session_cron_trigger(self) -> CronTrigger | None:
        if self.game_session_cron_schedule:
            return CronTrigger.from_crontab(self.game_session_cron_schedule)
        else:
            return None

    @computed_field
    @property
    def next_game_session_event(self) -> datetime | None:
        """Get the next game session datetime."""
        if self.game_session_cron_trigger:
            return self.game_session_cron_trigger.next()
        else:
            return None

    # noinspection PyNestedDecorators
    @field_validator("game_session_cron_schedule")
    @classmethod
    def name_must_contain_space(cls, v: str | None) -> str | None:
        if v:
            # Validate the cron string by instantiating a CronTrigger object
            trigger = CronTrigger.from_crontab(v)

            if trigger.next() < (datetime.now() + timedelta(days=1)).astimezone(timezone.utc):
                raise ValueError(
                    "The next scheduled event is too soon, shceduled events must be at least 24 hours apart."
                )

        # Return the value if it is valid
        return v

    def __str__(self):
        return self.name


class DiscordTextChannel(SQLModelValidation, table=True):
    """SQLModel class for a Discord text channel."""

    id: int | None = Field(default=None, primary_key=True)

    discord_channel_id: int = Field(sa_column=sa.Column(sa.BigInteger(), index=True))
    assistant_thread_id: str | None = None
    group_id: int = Field(sa_column=sa.Column(sa.BigInteger(), sa.ForeignKey("groups.id")))
    group: Group = Relationship(
        back_populates="discord_text_channels",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    def __str__(self):
        return self.discord_channel_id


class GameSessionEvent(SQLModelValidation, table=True):
    """An Occurrence of an event."""

    __tablename__ = "game_session_event"
    __table_args__ = (
        Index(
            "compound_index_game_session_event_event_id_date",
            "group_id",
            "timestamp",
            unique=True,
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    group_id: int = Field(foreign_key="groups.id", index=True)
    group: "Group" = Relationship(
        back_populates="game_session_events",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # Food Tracking
    food_name: str | None
    food_description: str | None
    user_assigned_food_id: int | None = Field(default=None, foreign_key="users.id")
    user_assigned_food: User | None = Relationship(
        back_populates="brought_food_for",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    food_reminder_discord_messages: list["EventFoodReminderDiscordMessage"] = Relationship(
        back_populates="game_session_event",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    # Attendance Tracking
    users_rsvp_yes: list[User] = Relationship(
        back_populates="game_session_event_rsvp_yes",
        link_model=UserEventOccurrenceRsvpYesLink,
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "save-update, merge"},
    )
    users_rsvp_no: list[User] = Relationship(
        back_populates="game_session_event_rsvp_no",
        link_model=UserEventOccurrenceRsvpNoLink,
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "save-update, merge"},
    )
    attendance_reminder_discord_messages: list["EventAttendanceReminderDiscordMessage"] = Relationship(
        back_populates="game_session_event",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    @computed_field
    @property
    def user_attendance_summary_md(self) -> str:
        event_timestamp = self.timestamp.astimezone(pytz.timezone(self.group.timezone))
        event_timesatmp_str = f"{event_timestamp.strftime('%Y-%m-%d %H:%M')} ({event_timestamp.tzname()})"

        summary_md = f"**{self.group.name}** attendance for {event_timesatmp_str}\n"
        summary_md += "**RSVP Yes**\n"
        summary_md += "\n".join([f"- {user.friendly_name}" for user in self.users_rsvp_yes])
        summary_md += "\n\n"
        summary_md += "**RSVP No**\n"
        summary_md += "\n".join([f"- {user.friendly_name}" for user in self.users_rsvp_no])
        return summary_md

    @computed_field
    @property
    def reminder_datetime(self) -> datetime | None:
        if self.group.next_game_session_event:
            return datetime.combine(
                date=(self.timestamp - timedelta(days=self.group.game_session_reminder_days_before_event)).date(),
                time=self.group.game_session_reminder_time,
            ).astimezone(pytz.timezone(self.group.timezone))

    def __str__(self):
        return f"group-{self.group_id} game session event [{self.timestamp.isoformat()}]"


class EventFoodReminderDiscordMessage(SQLModelValidation, table=True):
    """Model to track discord messages for food events."""

    __tablename__ = "event_food_reminder_discord_messages"

    discord_message_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.BigInteger(), primary_key=True, autoincrement=True),
    )
    game_session_event_id: int = Field(default=None, foreign_key="game_session_event.id", index=True)
    game_session_event: GameSessionEvent = Relationship(
        back_populates="food_reminder_discord_messages",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class EventAttendanceReminderDiscordMessage(SQLModelValidation, table=True):
    """Model to track discord messages for food events."""

    __tablename__ = "event_attendance_reminder_discord_messages"

    discord_message_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.BigInteger(), primary_key=True, autoincrement=True),
    )
    game_session_event_id: int = Field(default=None, foreign_key="game_session_event.id", index=True)
    game_session_event: GameSessionEvent = Relationship(
        back_populates="attendance_reminder_discord_messages",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class DalleImageRequest(SQLModelValidation, table=True):
    """Model for tracking image requests to the DALLE API."""

    __tablename__ = "dalle_image_requests"

    id: int | None = Field(default=None, primary_key=True)
    request_time: datetime = Field(
        default_factory=datetime.now, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False)
    )
    prompt: str
    model: str
    size: str
    quality: str
    revised_prompt: str | None = None
    image_url: str | None = None

    def __str__(self):
        return f"Dall-E Image {self.id} [{self.request_time}]"
