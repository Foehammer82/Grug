"""SQLModel classes for the bot's database."""

from datetime import date, datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, computed_field
from sqlmodel import Field, Relationship, SQLModel


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
    event_attendance_id: int | None = Field(default=None, foreign_key="events_attendance.id", primary_key=True)
    rsvp: Rsvp = Field(default=Rsvp.NO_RESPONSE)


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

    assistant_thread_id: str | None = None

    groups: list["Group"] = Relationship(back_populates="users", link_model=UserGroupLink)
    discord_accounts: list["DiscordAccount"] = Relationship(back_populates="user")
    brought_food_for: list["EventFood"] = Relationship(back_populates="user_assigned_food")
    event_attendance: list["EventAttendance"] = Relationship(back_populates="users", link_model=UserEventAttendanceLink)
    secrets: Optional["UserSecrets"] = Relationship(back_populates="user")


class UserSecrets(SQLModel, table=True):
    __tablename__ = "users_secrets"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    user: User | None = Relationship(back_populates="secrets")
    hashed_password: str


class Group(SQLModel, table=True):
    """SQLModel class for a group in the system."""

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    name: str | None = None

    users: list["User"] = Relationship(back_populates="groups", link_model=UserGroupLink)
    events: list["Event"] = Relationship(back_populates="group")
    discord_servers: list["DiscordServer"] = Relationship(back_populates="group")

    # TODO: these two params are just a thought right now, but it might make sense to have openai "assistants" tied
    #       to groups, so that each group has its own assistant that can be customized for that group.
    #       The openai_assistant module would need to be overhauled to support this.  and, this would more tightly
    #       couple the assistant to the group rather than the global application.
    bot_name_override: str | None = None
    bot_instructions_override: str | None = None


class DiscordAccount(SQLModel, table=True):
    """Discord user model."""

    __tablename__ = "discord_accounts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    user: User | None = Relationship(back_populates="discord_accounts")
    discord_member_id: str


class DiscordServer(SQLModel, table=True):
    """SQLModel class for a Discord server."""

    __tablename__ = "discord_servers"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int | None = Field(default=None, foreign_key="groups.id")
    group: Group | None = Relationship(back_populates="discord_servers")
    discord_guild_id: str


class Event(SQLModel, table=True):
    """Model for an event."""

    # TODO: either as a method or a separate function, will need to have a way to get food and attendance history

    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    group_id: int | None = Field(default=None, foreign_key="groups.id")
    group: Group | None = Relationship(back_populates="events")

    # Event Schedule
    event_schedule_cron: str | None = Field(
        default=None,
        description=(
            "If the event is recurring, this is the cron schedule for the event.  If the event is non-recurring, this "
            "should be `None`."
        ),
    )
    event_schedule_start_date: date | None = Field(
        default=None,
        description=(
            "The first date of the event schedule.  If event is non-recurring, this should be the date of the event."
        ),
    )
    event_schedule_end_date: date | None = None

    # Food Tracking
    track_food: bool = True
    food_reminder_cron: str | None = None
    food: list["EventFood"] = Relationship(back_populates="event")

    # Attendance Tracking
    track_attendance: bool = True
    attendance_reminder_cron: str | None = None
    attendance: list["EventAttendance"] = Relationship(back_populates="event")


class EventFood(SQLModel, table=True):
    """Model for tracking food."""

    __tablename__ = "events_food"

    id: int | None = Field(default=None, primary_key=True)
    event_date: date
    event_id: int | None = Field(default=None, foreign_key="events.id")
    event: Event | None = Relationship(back_populates="food")
    user_assigned_food_id: int | None = Field(default=None, foreign_key="users.id")
    user_assigned_food: User | None = Relationship(back_populates="brought_food_for")

    food_name: str | None
    food_description: str | None

    discord_message_id: str | None = None


class EventAttendance(SQLModel, table=True):
    """Model for tracking attendance."""

    __tablename__ = "events_attendance"

    id: int | None = Field(default=None, primary_key=True)
    event_date: date
    event_id: int | None = Field(default=None, foreign_key="events.id")
    event: Event | None = Relationship(back_populates="attendance")
    users: list[User] = Relationship(back_populates="event_attendance", link_model=UserEventAttendanceLink)

    discord_message_id: str | None = None


# *********************************************************************************************************************
# TODO: Everything below this is deprecated and the rest of the app will need to be updated to user the
#       above new models.
# *********************************************************************************************************************


class Player(SQLModel, table=True):
    """SQLModel class for a player in the D&D group."""

    id: int | None = Field(default=None, primary_key=True)

    discord_member_id: str
    discord_guild_id: str
    discord_username: str
    discord_guild_nickname: str | None = None

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    brings_food: bool = True
    is_active: bool = True

    assistant_thread_id: str | None = None

    brought_food_for_sessions: list["DndSession"] = Relationship(back_populates="food_bringer")

    @computed_field
    @property
    def friendly_name(self) -> str:
        """Get the player's friendly name."""
        if self.first_name is not None:
            return self.first_name
        elif self.discord_guild_nickname is not None:
            return self.discord_guild_nickname
        else:
            return self.discord_username


class DndSession(SQLModel, table=True):
    """SQLModel class for a D&D session."""

    id: int | None = Field(default=None, primary_key=True)
    discord_guild_id: str
    session_start_datetime: datetime

    food_bringer_player_id: int | None = Field(default=None, foreign_key="player.id")
    food_bringer: Player | None = Relationship(back_populates="brought_food_for_sessions")

    food_selection_messages: list["FoodSelectionMessage"] | None = Relationship(back_populates="dnd_session")


class FoodSelectionMessage(SQLModel, table=True):
    """SQLModel class for a food selection message."""

    id: int | None = Field(default=None, primary_key=True)
    discord_message_id: str = Field(index=True)

    dnd_session_id: int = Field(foreign_key="dndsession.id")
    dnd_session: DndSession = Relationship(back_populates="food_selection_messages")


class DiscordTextChannel(SQLModel, table=True):
    """SQLModel class for a Discord text channel."""

    id: int | None = Field(default=None, primary_key=True)

    discord_id: str = Field(index=True)
    assistant_thread_id: str | None = None


class AssistantResponse(BaseModel):
    """Pydantic model for an assistant response."""

    response: str
    thread_id: str


class BroughtFood(BaseModel):
    """Pydantic model for a brought food response."""

    by_player: Player
    on_date: date
