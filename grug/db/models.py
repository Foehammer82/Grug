"""SQLAlchemy ORM models for Grug."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GuildConfig(Base):
    """Per-guild configuration."""

    __tablename__ = "guild_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(10), default="!")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    announce_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    events: Mapped[list["CalendarEvent"]] = relationship(back_populates="guild")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="guild")
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship(back_populates="guild")


class Document(Base):
    """A document indexed for RAG retrieval."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chroma_collection: Mapped[str] = mapped_column(String(256), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class CalendarEvent(Base):
    """A calendar event for a guild."""

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    guild: Mapped["GuildConfig"] = relationship(back_populates="events")


class Reminder(Base):
    """A reminder for a user."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    guild: Mapped["GuildConfig"] = relationship(back_populates="reminders")


class ScheduledTask(Base):
    """A recurring agent task (e.g. 'tell a joke every Friday at 9am')."""

    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    guild: Mapped["GuildConfig"] = relationship(back_populates="scheduled_tasks")


class ConversationMessage(Base):
    """A message in a per-channel conversation history."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class GlossaryTerm(Base):
    """A guild- or channel-scoped glossary term for campaign/server-specific definitions.

    channel_id = None  -> guild-wide definition
    channel_id = <id>  -> channel-level override (takes precedence over guild-wide)
    """

    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    term: Mapped[str] = mapped_column(String(256), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    # True while the agent owns this definition; flipped to False on any human edit.
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set once at creation; never mutated — records whether AI originally coined this term.
    originally_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Discord user snowflake; 0 is the sentinel for the agent.
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    history: Mapped[list["GlossaryTermHistory"]] = relationship(
        back_populates="term_ref", cascade="all, delete-orphan"
    )


class GlossaryTermHistory(Base):
    """Immutable audit log of every change made to a glossary term."""

    __tablename__ = "glossary_term_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("glossary_terms.id"), nullable=False, index=True
    )
    # Denormalised for fast guild-scoped history queries without a join.
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_term: Mapped[str] = mapped_column(String(256), nullable=False)
    old_definition: Mapped[str] = mapped_column(Text, nullable=False)
    old_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Discord user snowflake; 0 = agent.
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    term_ref: Mapped["GlossaryTerm"] = relationship(back_populates="history")