"""SQLModel classes for the bot's database."""

from datetime import date, datetime

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel


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

    brought_food_for_sessions: list["DndSession"] = Relationship(
        back_populates="food_bringer"
    )

    @property
    def friendly_name(self):
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

    food_selection_messages: list["FoodSelectionMessage"] | None = Relationship(
        back_populates="dnd_session"
    )


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
