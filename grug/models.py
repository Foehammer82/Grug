"""SQLModel classes for the bot's database."""

from datetime import date, datetime, time, timedelta
from typing import Optional

import pytz
import sqlalchemy as sa
from apscheduler.abc import Trigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from pydantic import computed_field
from sqlalchemy import Index, event
from sqlmodel import Field, Relationship, SQLModel

from grug.settings import TimeZone, settings


class UserGroupLink(SQLModel, table=True):
    __tablename__ = "users_groups_link"
    group_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="groups.id", primary_key=True)


class UserEventAttendanceLink(SQLModel, table=True):
    __tablename__ = "users_events_attendance_link"
    user_id: int | None = Field(default=None, foreign_key="users.id", primary_key=True)
    event_attendance_id: int | None = Field(default=None, foreign_key="event_occurrence.id", primary_key=True)


class User(SQLModel, table=True):
    """
    SQLModel class for a user in the system.

    NOTE: the email is intentionally not required, to make it so that a discord user can auto create a user, we
          don't get an email from discord.  so we allow the email to be null and can later set up account linking
          features as needed in the even a multiple user accounts are create for the same person.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str

    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    disabled: bool = False
    is_admin: bool = False

    assistant_thread_id: str | None = None
    auto_created: bool = False

    groups: list["Group"] = Relationship(
        back_populates="users",
        link_model=UserGroupLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # Discord Account Information
    discord_member_id: int | None = Field(default=None, sa_column=sa.Column(sa.BigInteger(), index=True))
    discord_username: str | None = None

    # Event Tracking
    brought_food_for: list["EventOccurrence"] = Relationship(back_populates="user_assigned_food")
    event_attendance: list["EventOccurrence"] = Relationship(
        back_populates="users_attended", link_model=UserEventAttendanceLink
    )

    # User Secrets
    secrets: Optional["UserSecrets"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    # Communication Preferences
    disable_sms: bool = False
    disable_email: bool = False

    @computed_field
    @property
    def is_owner(self) -> bool:
        return (
            settings.discord and settings.discord.admin_user_id == self.discord_member_id
        ) or settings.admin_user == self.username

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


def handle_changes_to_owning_users(mapper, connection, target: User):
    """Ensure that the owner is always an admin and can't be locked out in any way."""
    if target.is_owner:
        target.is_admin = True
        target.disabled = False


event.listen(User, "before_insert", handle_changes_to_owning_users)
event.listen(User, "before_update", handle_changes_to_owning_users)


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
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )
    discord_servers: list["DiscordServer"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    def __str__(self):
        return self.name


class DiscordServer(SQLModel, table=True):
    """SQLModel class for a Discord server."""

    __tablename__ = "discord_servers"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="groups.id")
    group: Group = Relationship(
        back_populates="discord_servers",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    discord_guild_id: int = Field(sa_column=sa.Column(sa.BigInteger(), index=True))
    discord_guild_name: str | None = None
    discord_bot_channel_id: int | None = Field(sa_column=sa.Column(sa.BigInteger(), nullable=True, default=None))
    discord_text_channels: list["DiscordTextChannel"] = Relationship(
        back_populates="discord_server",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    def __str__(self):
        return f"{self.discord_guild_name} [{self.discord_guild_id}]"


class DiscordTextChannel(SQLModel, table=True):
    """SQLModel class for a Discord text channel."""

    id: int | None = Field(default=None, primary_key=True)

    discord_channel_id: int = Field(sa_column=sa.Column(sa.BigInteger(), index=True))
    assistant_thread_id: str | None = None
    discord_server_id: int = Field(sa_column=sa.Column(sa.BigInteger(), sa.ForeignKey("discord_servers.id")))
    discord_server: DiscordServer = Relationship(
        back_populates="discord_text_channels",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    def __str__(self):
        return self.discord_channel_id


class EventOccurrence(SQLModel, table=True):
    """An Occurrence of an event."""

    __tablename__ = "event_occurrence"
    __table_args__ = (
        Index(
            "compound_index_event_occurrence_event_id_date",
            "event_id",
            "event_date",
            unique=True,
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_date: date
    event_time: time
    event_id: int = Field(default=None, foreign_key="event.id", index=True)
    event: "Event" = Relationship(
        back_populates="event_occurrences",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # Food Tracking
    food_reminder: datetime | None = Field(
        default=None,
        description="The scheduled timestamp to send the food reminder.  If null, no reminder is scheduled.",
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    food_name: str | None
    food_description: str | None
    user_assigned_food_id: int | None = Field(default=None, foreign_key="users.id")
    user_assigned_food: User | None = Relationship(
        back_populates="brought_food_for",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    food_reminder_discord_messages: list["EventFoodReminderDiscordMessage"] = Relationship(
        back_populates="event_occurrence",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    # Attendance Tracking
    attendance_reminder: datetime | None = Field(
        default=None,
        description="The scheduled timestamp to send the attendance reminder.  If null, no reminder is scheduled.",
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    users_attended: list[User] = Relationship(
        back_populates="event_attendance",
        link_model=UserEventAttendanceLink,
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "save-update, merge"},
    )
    attendance_reminder_discord_messages: list["EventAttendanceReminderDiscordMessage"] = Relationship(
        back_populates="event_occurrence",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    @computed_field
    @property
    def timestamp(self) -> datetime:
        """Get the timestamp of the event.  always in the event's timezone."""
        return datetime.combine(self.event_date, self.event_time).astimezone(pytz.timezone(self.event.timezone))

    @computed_field
    @property
    def localized_food_reminder(self) -> datetime | None:
        return self.food_reminder.astimezone(pytz.timezone(self.event.timezone)) if self.food_reminder else None

    @computed_field
    @property
    def localized_attendance_reminder(self) -> datetime | None:
        return (
            self.attendance_reminder.astimezone(pytz.timezone(self.event.timezone))
            if self.attendance_reminder
            else None
        )

    @computed_field
    @property
    def user_attendance_summary_md(self) -> str:
        summary_md = f"**{self.event.name}** attendance for {self.event_date.isoformat()}\n"
        summary_md += "\n".join([f"- {user.friendly_name}" for user in self.users_attended])
        return summary_md

    @computed_field
    @property
    def food_reminder_schedule_id(self) -> str:
        return f"event_occurrence_{self.id}_food_reminder"

    @property
    def food_reminder_trigger(self) -> Trigger | None:
        return DateTrigger(run_time=self.food_reminder) if self.food_reminder else None

    @computed_field
    @property
    def attendance_reminder_schedule_id(self) -> str:
        return f"event_occurrence_{self.id}_attendance_reminder"

    @property
    def attendance_reminder_trigger(self) -> Trigger | None:
        return DateTrigger(run_time=self.attendance_reminder) if self.attendance_reminder else None

    def __str__(self):
        return f"{self.event.name} food [{self.timestamp.isoformat()}]"


class EventFoodReminderDiscordMessage(SQLModel, table=True):
    """Model to track discord messages for food events."""

    __tablename__ = "event_food_reminder_discord_messages"

    discord_message_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.BigInteger(), primary_key=True, autoincrement=True),
    )
    event_occurrence_id: int = Field(default=None, foreign_key="event_occurrence.id", index=True)
    event_occurrence: EventOccurrence = Relationship(
        back_populates="food_reminder_discord_messages",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class EventAttendanceReminderDiscordMessage(SQLModel, table=True):
    """Model to track discord messages for food events."""

    __tablename__ = "event_attendance_reminder_discord_messages"

    discord_message_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.BigInteger(), primary_key=True, autoincrement=True),
    )
    event_occurrence_id: int = Field(default=None, foreign_key="event_occurrence.id", index=True)
    event_occurrence: EventOccurrence = Relationship(
        back_populates="attendance_reminder_discord_messages",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class Event(SQLModel, table=True):
    """Model for an event."""

    __tablename__ = "event"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    group_id: int = Field(default=None, foreign_key="groups.id")
    group: Group = Relationship(
        back_populates="events",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    # Event Schedule
    start_date: date = Field(
        default_factory=date.today,
        description=(
            "The first date the event scheduled for.  If event is non-recurring, this should be the date of the event."
        ),
    )
    default_start_time: time = Field(
        default=time(hour=17), description="time the event starts, this can be overridden by the event occurrence"
    )
    timezone: TimeZone = Field(default=settings.timezone)
    cron_schedule: str | None = Field(
        default=None,
        description="cron schedule to run the event",
    )
    end_date: date | None = Field(default=None, description="latest possible date the event can occur")
    event_occurrences: list[EventOccurrence] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete"},
    )

    # Food Tracking
    track_food: bool = True
    food_reminder_time: time = Field(default=time(hour=11), description="time to send the reminder at")
    food_reminder_days_before_event: int = Field(
        default=3, description="days before the event to send the food reminder"
    )
    enable_food_discord_reminders: bool = True
    enable_food_sms_reminders: bool = False
    enable_food_email_reminders: bool = False

    # Attendance Tracking
    track_attendance: bool = True
    attendance_reminder_time: time = Field(default=time(hour=11), description="time to send the reminder at")
    attendance_reminder_days_before_event: int = Field(
        default=2, description="days before the event to send the attendance reminder"
    )
    enable_attendance_discord_reminders: bool = True
    enable_attendance_sms_reminders: bool = False
    enable_attendance_email_reminders: bool = False

    @property
    def schedule_trigger(self) -> Trigger:
        return CronTrigger.from_crontab(self.cron_schedule)

    @computed_field
    @property
    def next_event_datetime(self) -> datetime | None:
        """Get the next event date."""
        if self.cron_schedule is None:
            start_datetime = datetime.combine(self.start_date, self.default_start_time).astimezone(
                pytz.timezone(self.timezone)
            )
            return start_datetime if start_datetime > datetime.now(pytz.timezone(self.timezone)) else None
        else:
            return self.schedule_trigger.next().astimezone(pytz.timezone(self.timezone))

    @property
    def attendance_reminder_timestamp(self) -> datetime | None:
        """Get the attendance reminder timestamp."""
        if not self.track_attendance:
            return None

        return datetime.combine(
            self.next_event_datetime - timedelta(days=self.attendance_reminder_days_before_event),
            self.attendance_reminder_time,
        ).astimezone(pytz.timezone(self.timezone))

    @property
    def food_reminder_timestamp(self) -> datetime | None:
        """Get the food reminder timestamp."""
        if not self.track_food:
            return None

        return datetime.combine(
            self.next_event_datetime - timedelta(days=self.food_reminder_days_before_event),
            self.food_reminder_time,
        ).astimezone(pytz.timezone(self.timezone))

    def __str__(self):
        return f"{self.name} [{self.group.name}]"


class DalleImageRequest(SQLModel, table=True):
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
