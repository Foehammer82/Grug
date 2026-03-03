"""SQLAlchemy ORM models for Grug."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GuildConfig(Base):
    """Per-guild configuration."""

    __tablename__ = "guild_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    announce_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Discord snowflake ID of the auto-created "grug-admin" role in this guild.
    grug_admin_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Messages timestamped before this are excluded from Grug's context window.
    # None means no cutoff — load all available history.
    context_cutoff: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    events: Mapped[list["CalendarEvent"]] = relationship(back_populates="guild")
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship(
        back_populates="guild"
    )
    channel_configs: Mapped[list["ChannelConfig"]] = relationship(
        back_populates="guild"
    )


class ChannelConfig(Base):
    """Per-channel configuration — overrides guild-level defaults where set.

    ``always_respond`` replaces the old in-memory ``_ALWAYS_RESPOND_CHANNELS``
    set so the setting survives bot restarts.

    ``context_cutoff`` overrides the guild-level cutoff for this specific
    channel.  ``None`` means "fall back to the guild setting".
    """

    __tablename__ = "channel_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_configs.guild_id"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    # When True, Grug responds to every message here (not just @mentions).
    always_respond: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Channel-level override for the context cutoff.  None = use guild default.
    context_cutoff: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    guild: Mapped["GuildConfig"] = relationship(back_populates="channel_configs")


class Campaign(Base):
    """A TTRPG campaign linked to a specific Discord channel.

    One channel = one campaign. This is the primary scoping boundary for
    documents, memory, and character associations.
    """

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # channel_id is unique — one channel can only host one campaign.
    channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # Detected or manually set system tag, e.g. 'dnd5e', 'pf2e', 'unknown'.
    system: Mapped[str] = mapped_column(String(128), default="unknown")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    characters: Mapped[list["Character"]] = relationship(back_populates="campaign")


class Character(Base):
    """A player character sheet owned by a Discord user."""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Discord snowflake of the player who owns this character.
    owner_discord_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    # Optional link to a campaign; characters can exist without one.
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # Detected game system, e.g. 'dnd5e', 'pf2e', 'unknown'.
    system: Mapped[str] = mapped_column(String(128), default="unknown")
    # Full text of the sheet as extracted at upload time.
    raw_sheet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured JSON extracted by the parser (stats, abilities, etc.).
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Relative path within the grug_files volume, e.g. characters/123/fighter.pdf
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    campaign: Mapped["Campaign | None"] = relationship(back_populates="characters")


class UserProfile(Base):
    """Persistent profile for a Discord user, tracking their active character."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    # The character the user has set as active for DM sessions.
    active_character_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("characters.id", use_alter=True, name="fk_user_active_character"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Messages timestamped before this are excluded from Grug's DM context window.
    # None means no cutoff — load all available DM history.
    dm_context_cutoff: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    active_character: Mapped["Character | None"] = relationship(
        "Character", foreign_keys=[active_character_id]
    )


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
    # Optional campaign association; NULL means document is guild-wide.
    campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CalendarEvent(Base):
    """A calendar event for a guild.

    Supports one-off and recurring events.  Recurrence is stored as an
    iCal RRULE string (e.g. ``FREQ=WEEKLY;INTERVAL=2;BYDAY=TH``) and
    expanded server-side into concrete occurrences when queried.
    """

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # iCal RRULE string for recurring events, e.g. "FREQ=WEEKLY;BYDAY=TH"
    rrule: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Human-readable location (voice channel name, address, etc.)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc),
    )

    guild: Mapped["GuildConfig"] = relationship(back_populates="events")
    rsvps: Mapped[list["EventRSVP"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    notes: Mapped[list["EventNote"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    occurrence_overrides: Mapped[list["EventOccurrenceOverride"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    polls: Mapped[list["AvailabilityPoll"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventRSVP(Base):
    """A member's RSVP for a specific calendar event.

    Status values: ``'attending'``, ``'maybe'``, ``'declined'``.
    One row per (event, user) pair — upsert on conflict.
    """

    __tablename__ = "event_rsvps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 'attending' | 'maybe' | 'declined'
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event: Mapped["CalendarEvent"] = relationship(back_populates="rsvps")

    __table_args__ = (UniqueConstraint("event_id", "discord_user_id", name="uq_event_rsvp"),)


class EventNote(Base):
    """A planning note or to-do item attached to a calendar event.

    ``done`` can be toggled to track completion of to-do items.
    """

    __tablename__ = "event_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    done: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event: Mapped["CalendarEvent"] = relationship(back_populates="notes")


class EventOccurrenceOverride(Base):
    """Reschedule or cancel a single occurrence of a recurring event.

    ``original_start`` identifies which occurrence is being overridden.
    Set ``cancelled=True`` to drop that occurrence without rescheduling.
    Set ``new_start`` / ``new_end`` to move it.
    The ``(event_id, original_start)`` pair must be unique.
    """

    __tablename__ = "event_occurrence_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Identifies the specific recurrence being overridden.
    original_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # New start/end — None means unchanged from what the RRULE would produce.
    new_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    new_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When True this occurrence is hidden entirely from the expanded set.
    cancelled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event: Mapped["CalendarEvent"] = relationship(back_populates="occurrence_overrides")

    __table_args__ = (
        UniqueConstraint("event_id", "original_start", name="uq_event_occurrence_override"),
    )


class AvailabilityPoll(Base):
    """A Rallly-style scheduling poll — propose date/time options, let members vote.

    ``options`` is a JSON array of ``{"id": <int>, "start_time": <iso>, "end_time": <iso>, "label": <str>}``
    objects.  ``event_id`` is an optional link to an existing calendar event.
    """

    __tablename__ = "availability_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    # Optional link to a calendar event this poll is associated with.
    event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    # JSON: list of {id, label, start_time?, end_time?}
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When set, this option index was chosen as the winner.
    winner_option_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event: Mapped["CalendarEvent | None"] = relationship(back_populates="polls")
    votes: Mapped[list["PollVote"]] = relationship(
        back_populates="poll", cascade="all, delete-orphan"
    )


class PollVote(Base):
    """A member's vote on an availability poll.

    ``option_ids`` is a JSON array of option IDs the member selected.
    One row per (poll, user) — upsert on conflict.
    """

    __tablename__ = "poll_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("availability_polls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # JSON: list of option IDs this user voted for
    option_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    poll: Mapped["AvailabilityPoll"] = relationship(back_populates="votes")

    __table_args__ = (UniqueConstraint("poll_id", "discord_user_id", name="uq_poll_vote"),)


class ScheduledTask(Base):
    """A scheduled agent task — either a one-shot reminder (type='once') or a
    recurring automated prompt (type='recurring').

    * ``type='once'``:      fires once at ``fire_at``; set ``enabled=False`` after firing.
    * ``type='recurring'``: fires on ``cron_expression``; updates ``last_run`` each time.
    """

    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild_configs.guild_id"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 'once' | 'recurring'
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="recurring")
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Populated for type='once'
    fire_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Populated for type='recurring'
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Where this task was created from: 'discord' (agent tool) or 'web' (UI).
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="discord", server_default="discord"
    )
    # Discord user who requested the task (primarily used for type='once')
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    guild: Mapped["GuildConfig"] = relationship(back_populates="scheduled_tasks")


class ConversationMessage(Base):
    """A message in a per-channel conversation history."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # True = message was logged for context awareness but Grug was not @mentioned
    # and did not respond to it in this exchange.
    is_passive: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GrugUser(Base):
    """Global Grug user record — tracks per-user privileges like can_invite.

    Super-admin status can be set via the GRUG_SUPER_ADMIN_IDS env var OR
    by setting ``is_super_admin=True`` in this table.
    """

    __tablename__ = "grug_users"

    discord_user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    # When True, this user can generate invite URLs to add Grug to servers.
    can_invite: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Grants full super-admin access (same as being listed in GRUG_SUPER_ADMIN_IDS).
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


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
    channel_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    term: Mapped[str] = mapped_column(String(256), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    # True while the agent owns this definition; flipped to False on any human edit.
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set once at creation; never mutated — records whether AI originally coined this term.
    originally_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Discord user snowflake; 0 is the sentinel for the agent.
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    term_ref: Mapped["GlossaryTerm"] = relationship(back_populates="history")
