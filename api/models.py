"""Standalone SQLAlchemy models for the API container.

Mirrors the tables defined in grug/db/models.py using the same table names
so both services share the same SQLite database file.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GuildConfig(Base):
    __tablename__ = "guild_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    prefix: Mapped[str] = mapped_column(String(10), default="!")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    announce_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chroma_collection: Mapped[str] = mapped_column(String(256), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    term: Mapped[str] = mapped_column(String(256), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    originally_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    system: Mapped[str] = mapped_column(String(128), default="unknown")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_discord_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    system: Mapped[str] = mapped_column(String(128), default="unknown")
    raw_sheet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    active_character_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("characters.id", use_alter=True, name="fk_user_active_character"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class GlossaryTermHistory(Base):
    __tablename__ = "glossary_term_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_term: Mapped[str] = mapped_column(String(256), nullable=False)
    old_definition: Mapped[str] = mapped_column(Text, nullable=False)
    old_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
