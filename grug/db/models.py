"""SQLAlchemy ORM models for Grug."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
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
    # Random token used to authenticate the public iCal feed URL.
    # Generated on first use; can be regenerated to invalidate old subscriptions.
    calendar_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Default TTRPG system for this guild (e.g. "pf2e", "dnd5e").
    # When set, Grug uses this as the fallback system for rule lookups.
    default_ttrpg_system: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
    rule_sources: Mapped[list["RuleSource"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    builtin_overrides: Mapped[list["GuildBuiltinOverride"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )


class ChannelConfig(Base):
    """Per-channel configuration — persists settings that would otherwise live in memory.

    ``enabled`` gates Grug's participation in a channel entirely.  When False,
    Grug ignores all messages in that channel (no passive logging, no responses).
    When True, the normal auto-respond / @mention logic applies.

    ``auto_respond`` enables intelligent auto-response in a channel.  When the
    threshold is 0.0 Grug responds to every message (equivalent to the old
    ``always_respond=True``).  When threshold > 0.0 a lightweight LLM scores
    each message and Grug only responds when ``score >= threshold``.
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
    # Master switch — when False, Grug ignores this channel entirely.
    # Defaults to False; the announce_channel_id for a guild is auto-enabled on setup.
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # When True, Grug considers responding to every message here (not just @mentions).
    # When threshold == 0.0, Grug always responds; when threshold > 0.0, a lightweight
    # LLM scores the message and Grug responds only when score >= threshold.
    auto_respond: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Confidence threshold for the auto-respond scorer (0.0 = always, 1.0 = only if certain).
    auto_respond_threshold: Mapped[float] = mapped_column(
        Float, default=0.5, server_default="0.5", nullable=False
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
    # Discord snowflake of the GM for this campaign.  GMs can view all character
    # sheets in the campaign — same level of access as a guild admin, scoped to
    # this campaign only.  NULL means no GM is assigned.
    gm_discord_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # Soft-delete timestamp.  NULL = active; set = deleted but recoverable.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # ── Banking ──────────────────────────────────────────────────────────
    # Master switch — no banking features work when False.
    banking_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # When True, players (not just GM/admin) may adjust their own wallet and
    # the party pool.
    player_banking_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # When True, every gold mutation is recorded in gold_transactions.
    banking_ledger_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Shared party gold pool (single float, system-agnostic).
    party_gold: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=4), default=0.0, server_default="0", nullable=False
    )
    # ── Combat ────────────────────────────────────────────────────────────
    # How much combat detail the tracker records:
    #   'basic'    — initiative order + turn tracking only
    #   'standard' — + HP tracking, AC display, conditions
    #   'full'     — + damage/healing log, death saves, concentration tracking
    combat_tracker_depth: Mapped[str] = mapped_column(
        String(16), default="standard", server_default="standard", nullable=False
    )
    # ── Scheduling ───────────────────────────────────────────────────────
    # How this campaign's sessions are scheduled:
    #   'fixed'  — GM picks a recurring day/time (default)
    #   'poll'   — an availability poll decides each session date
    schedule_mode: Mapped[str] = mapped_column(
        String(16), default="fixed", server_default="fixed", nullable=False
    )
    # ── Dice ─────────────────────────────────────────────────────────────
    # When True, players may post manual (physical dice) roll results to the
    # campaign log via the dice tab.  Off by default.
    allow_manual_dice_recording: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    characters: Mapped[list["Character"]] = relationship(back_populates="campaign")
    gold_transactions: Mapped[list["GoldTransaction"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    session_notes: Mapped[list["SessionNote"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    encounters: Mapped[list["Encounter"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="campaign",
        foreign_keys="CalendarEvent.campaign_id",
    )


class Character(Base):
    """A player character sheet owned by a Discord user."""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Discord snowflake of the player who owns this character.  Nullable for
    # NPCs or players who don't have a Discord account.
    owner_discord_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    # Free-form display name shown when owner_discord_user_id is null (NPC,
    # non-Discord player, etc.).  Ignored when a Discord owner is set.
    owner_display_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True, default=None
    )
    # Optional link to a campaign; characters can exist without one.
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # Detected game system, e.g. 'dnd5e', 'pf2e', 'unknown'.
    system: Mapped[str] = mapped_column(String(128), default="unknown")
    # Private notes visible only to the character's owner and guild admins.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    # Full text of the sheet as extracted at upload time.
    raw_sheet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured JSON extracted by the parser (stats, abilities, etc.).
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Pathbuilder 2e character ID for sync.  When set, structured_data is
    # populated from the Pathbuilder JSON endpoint instead of Claude extraction.
    pathbuilder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Relative path within the grug_files volume, e.g. characters/123/fighter.pdf
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Timestamp of the last successful Pathbuilder sync (used for 5-min cooldown).
    pathbuilder_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # Personal gold wallet — only meaningful when the campaign has banking_enabled.
    gold: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=4), default=0.0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    campaign: Mapped["Campaign | None"] = relationship(back_populates="characters")


class GoldTransaction(Base):
    """A single gold movement recorded when campaign.banking_ledger_enabled is True.

    Covers both party-pool transactions (character_id IS NULL) and per-character
    wallet adjustments.  ``amount`` is signed: positive = credit, negative = debit.
    """

    __tablename__ = "gold_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=False, index=True
    )
    # NULL means this is a party-pool transaction.
    character_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("characters.id"), nullable=True, index=True
    )
    # Discord snowflake of whoever triggered the transaction.
    actor_discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Signed amount: positive = credit, negative = debit.
    amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="gold_transactions")


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
    # SHA-256 hex digest of the raw file bytes; used to reject duplicate uploads.
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SessionNote(Base):
    """A session note log entry for a campaign.

    Users submit raw notes (pasted text or uploaded file) which are then
    cleaned and synthesized by an LLM into ``clean_notes``.  The clean notes
    are indexed into the RAG vector store so Grug can answer questions about
    past sessions.
    """

    __tablename__ = "session_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=False, index=True
    )
    # Denormalised for efficient RAG scoping queries without a join.
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Optional session date — the in-world or real-world date of the session.
    session_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Raw notes as submitted by the user (unmodified, may be messy).
    raw_notes: Mapped[str] = mapped_column(Text, nullable=False)
    # LLM-synthesized clean version of raw_notes.  NULL until synthesis completes.
    clean_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lifecycle: 'pending' → 'processing' → 'done' | 'failed'
    synthesis_status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", nullable=False
    )
    synthesis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # documents.id of the indexed RAG entry for clean_notes.  NULL until synthesis.
    # No FK constraint — consistent with Document.campaign_id pattern.
    rag_document_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    submitted_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="session_notes")


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
    # Reminder configuration — which days before the event to send reminders.
    # Stored as a JSON list of integers, e.g. [7, 1] = 7 days + 1 day before.
    reminder_days: Mapped[list[int] | None] = mapped_column(
        JSON, nullable=True, default=lambda: [1]
    )
    # Time-of-day for reminders in guild timezone, HH:MM format.
    reminder_time: Mapped[str | None] = mapped_column(
        String(8), nullable=True, default="18:00"
    )
    # How many days in advance to open an availability poll (poll mode only).
    poll_advance_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=7
    )
    # Optional link to a campaign — session events are scoped to a campaign.
    campaign_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    campaign: Mapped["Campaign | None"] = relationship(back_populates="events")
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
        Integer,
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    __table_args__ = (
        UniqueConstraint("event_id", "discord_user_id", name="uq_event_rsvp"),
    )


class EventNote(Base):
    """A planning note or to-do item attached to a calendar event.

    ``done`` can be toggled to track completion of to-do items.
    """

    __tablename__ = "event_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
        Integer,
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
        UniqueConstraint(
            "event_id", "original_start", name="uq_event_occurrence_override"
        ),
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
        Integer,
        ForeignKey("calendar_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        Integer,
        ForeignKey("availability_polls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    __table_args__ = (
        UniqueConstraint("poll_id", "discord_user_id", name="uq_poll_vote"),
    )


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
    # IANA timezone name used to interpret cron fields (e.g. "America/New_York").
    # Defaults to "UTC".  Stored so the scheduler always fires at the intended local time.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC", server_default="UTC")
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
    # Optional link to a calendar event — auto-created reminders reference
    # the event they belong to so they can be refreshed or cleaned up.
    event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    guild: Mapped["GuildConfig"] = relationship(back_populates="scheduled_tasks")
    event: Mapped["CalendarEvent | None"] = relationship()


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


class RuleSource(Base):
    """A custom TTRPG rule source added by a guild administrator.

    Grug can query these URLs when answering rules questions.  A ``system``
    value of ``None`` means the source applies to all game systems.
    """

    __tablename__ = "rule_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_configs.guild_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Lower value = higher priority. Built-in sources are always consulted first."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    guild: Mapped["GuildConfig"] = relationship(back_populates="rule_sources")


class GuildBuiltinOverride(Base):
    """Per-guild enable/disable override for a built-in rule source.

    Built-in sources are defined in ``grug/rules/sources.py``.  A guild admin
    can disable a built-in by creating a row with ``enabled=False``.
    Only explicit overrides are stored; built-ins default to enabled.
    """

    __tablename__ = "guild_builtin_overrides"
    __table_args__ = (
        UniqueConstraint("guild_id", "source_id", name="uq_guild_builtin_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_configs.guild_id"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    guild: Mapped["GuildConfig"] = relationship(back_populates="builtin_overrides")


class GrugNote(Base):
    """Grug's own notes — organically curated observations and reminders.

    Two scopes:

    * **Guild note** — ``guild_id`` set, ``user_id`` NULL.  Visible to guild
      admins on the server's Notes page.
    * **Personal note** — ``user_id`` set, ``guild_id`` NULL.  Visible to the
      individual user in the personal Notes section.

    Content is free-form Markdown maintained by Grug (and editable by admins /
    the owning user via the web UI).
    """

    __tablename__ = "grug_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DiceRoll(Base):
    """A persisted dice roll — every roll is stored for GM audit + session recaps.

    Privacy rules:
    - GM (``Campaign.gm_discord_user_id``) and guild admins can see all rolls.
    - Players see their own rolls and any roll with ``is_private=False``.
    """

    __tablename__ = "dice_rolls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=True, index=True
    )
    # Discord snowflake of the person who rolled.
    roller_discord_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    roller_display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    # Optional character name (for context — "Gandalf rolled…")
    character_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # The raw dice expression as typed by the user, e.g. "2d6+3".
    expression: Mapped[str] = mapped_column(String(256), nullable=False)
    # JSON array of individual die results.
    # Format: [{"sides": 6, "rolls": [4, 2], "kept": [4, 2], "total": 6}]
    individual_rolls: Mapped[list] = mapped_column(JSON, nullable=False)
    # Final numeric result.
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    # Categorises the roll purpose.
    # Values: general, attack, damage, saving_throw, ability_check, initiative,
    #         death_save, skill_check
    roll_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="general", server_default="general"
    )
    # When True, only the roller and GM/admin can see this roll.
    is_private: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Optional flavour text, e.g. "STR save vs Fireball DC 15"
    context_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    campaign: Mapped["Campaign | None"] = relationship()


class Encounter(Base):
    """An initiative encounter within a campaign."""

    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id"), nullable=False, index=True
    )
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="preparing", server_default="preparing"
    )
    current_turn_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    round_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="encounters")
    combatants: Mapped[list["Combatant"]] = relationship(
        back_populates="encounter", cascade="all, delete-orphan"
    )


class Combatant(Base):
    """A participant in an initiative encounter."""

    __tablename__ = "combatants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    encounter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    character_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("characters.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    initiative_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initiative_modifier: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_enemy: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    # When True, only the GM can see this combatant — hidden from players
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # ── HP / AC (standard+ depth) ────────────────────────────────────────
    max_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temp_hp: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    armor_class: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # JSON list of active condition strings, e.g. ["Blinded","Prone"]
    conditions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # JSON dict of ability save modifiers, e.g. {"STR": 4, "DEX": 2, ...}
    save_modifiers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # ── Death saves & concentration (full depth) ─────────────────────────
    death_save_successes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    death_save_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Name of the spell/effect being concentrated on, or null.
    concentration_spell: Mapped[str | None] = mapped_column(
        String(256), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    encounter: Mapped["Encounter"] = relationship(back_populates="combatants")
    character: Mapped["Character | None"] = relationship()
    combat_log_entries: Mapped[list["CombatLogEntry"]] = relationship(
        back_populates="combatant", cascade="all, delete-orphan"
    )


class CombatLogEntry(Base):
    """A single event in the combat log — damage, healing, death save, etc."""

    __tablename__ = "combat_log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    encounter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    combatant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("combatants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Event type: 'damage', 'healing', 'death_save', 'condition_add',
    # 'condition_remove', 'concentration_check', 'concentration_broken'
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # JSON details — varies by event_type:
    #   damage:  {"amount": 15, "damage_type": "fire", "source": "Fireball"}
    #   healing: {"amount": 10, "source": "Cure Wounds"}
    #   death_save: {"roll": 14, "success": true}
    #   condition_add/remove: {"condition": "Blinded"}
    #   concentration_check: {"dc": 10, "roll": 14, "total": 18, "passed": true}
    #   concentration_broken: {"spell": "Fly", "trigger": "damage"}
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    encounter: Mapped["Encounter"] = relationship()
    combatant: Mapped["Combatant"] = relationship(back_populates="combat_log_entries")


class LLMUsageDailyAggregate(Base):
    """Daily aggregate of LLM API token usage, keyed by date, guild, user, model, and call type.

    Costs are **not** stored — they are computed at read time from the price
    table in :mod:`grug.llm_usage` so that retroactive price updates apply
    automatically.
    """

    __tablename__ = "llm_usage_daily_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "guild_id",
            "user_id",
            "model",
            "call_type",
            name="uq_llm_usage_daily",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Nullable — DMs or background tasks have no guild / user.
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Exact model name as returned by the API, e.g. "claude-haiku-4-5".
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    # Feature that triggered the call — see grug.llm_usage.CallType.
    call_type: Mapped[str] = mapped_column(String(64), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class LLMUsageRecord(Base):
    """Raw per-call LLM usage record with a full timestamp.

    Used for sub-daily (e.g. hourly) reporting.  Records older than 90 days
    are pruned automatically by :func:`grug.llm_usage.record_llm_usage`.
    """

    __tablename__ = "llm_usage_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    call_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
