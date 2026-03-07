"""Pydantic response schemas for the API."""

from datetime import date, datetime, timezone

from pydantic import BaseModel, computed_field, field_serializer


class UserOut(BaseModel):
    id: str
    username: str
    discriminator: str
    avatar: str | None = None
    is_super_admin: bool = False
    can_invite: bool = False
    # Impersonation fields — only populated when a super-admin is impersonating.
    impersonating: bool = False
    impersonator_id: str | None = None
    impersonator_username: str | None = None


class DefaultsOut(BaseModel):
    default_timezone: str


class BotInfoOut(BaseModel):
    id: str
    username: str
    avatar_url: str | None = None


class GuildOut(BaseModel):
    id: str
    name: str
    icon: str | None = None
    is_admin: bool = False


class GuildConfigOut(BaseModel):
    guild_id: int
    timezone: str
    announce_channel_id: int | None
    default_ttrpg_system: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("guild_id")
    def serialize_guild_id(self, v: int) -> str:
        return str(v)

    @field_serializer("announce_channel_id")
    def serialize_announce_channel_id(self, v: int | None) -> str | None:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v) if v is not None else None


class GuildConfigUpdate(BaseModel):
    timezone: str | None = None
    # Accept string or int to avoid JS precision loss on large Discord snowflake IDs
    announce_channel_id: str | int | None = None
    default_ttrpg_system: str | None = None


class ChannelConfigOut(BaseModel):
    channel_id: int
    guild_id: int
    enabled: bool
    auto_respond: bool
    auto_respond_threshold: float
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("channel_id", "guild_id")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class ChannelConfigUpdate(BaseModel):
    # Master switch — when False, Grug ignores this channel entirely.
    enabled: bool | None = None
    auto_respond: bool | None = None
    # Must be in the range [0.0, 1.0].
    auto_respond_threshold: float | None = None


class CalendarEventOut(BaseModel):
    id: int
    guild_id: int
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime | None
    rrule: str | None = None
    location: str | None = None
    channel_id: int | None
    reminder_days: list[int] | None = None
    reminder_time: str | None = None
    poll_advance_days: int | None = None
    campaign_id: int | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime | None = None
    # When serving expanded occurrences the API sets these to the concrete
    # start/end for that occurrence, leaving the original start_time/end_time
    # as the series anchor.
    occurrence_start: datetime | None = None
    occurrence_end: datetime | None = None
    # Original start of the occurrence (for identifying overrides)
    original_start: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "created_by")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)

    @field_serializer("channel_id")
    def serialize_channel_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None


class CalendarEventCreate(BaseModel):
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    rrule: str | None = None
    location: str | None = None
    channel_id: str | int | None = None
    reminder_days: list[int] | None = None
    reminder_time: str | None = None
    poll_advance_days: int | None = None
    campaign_id: int | None = None


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    rrule: str | None = None
    location: str | None = None
    channel_id: str | int | None = None
    reminder_days: list[int] | None = None
    reminder_time: str | None = None
    poll_advance_days: int | None = None
    campaign_id: int | None = None


class ScheduledTaskOut(BaseModel):
    id: int
    guild_id: int
    channel_id: int
    type: str
    name: str | None
    prompt: str
    fire_at: datetime | None
    cron_expression: str | None
    timezone: str = "UTC"
    user_id: int | None
    enabled: bool
    last_run: datetime | None
    source: str
    event_id: int | None = None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "channel_id", "created_by")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)

    @field_serializer("user_id")
    def serialize_user_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None

    @computed_field
    @property
    def next_run(self) -> datetime | None:
        """Compute the next scheduled trigger time for this task.

        For ``once`` tasks returns ``fire_at`` if the task hasn't fired yet.
        For ``recurring`` tasks uses APScheduler's ``CronTrigger`` to compute
        the next fire time from the stored cron expression, interpreting the
        fields in the task's configured timezone.
        """
        now = datetime.now(timezone.utc)
        if self.type == "once":
            if self.fire_at and not self.last_run and self.fire_at > now:
                return self.fire_at
        elif self.type == "recurring" and self.cron_expression and self.enabled:
            try:
                from grug.scheduler.manager import unix_cron_to_trigger

                trigger = unix_cron_to_trigger(
                    self.cron_expression, timezone=self.timezone
                )
                return trigger.get_next_fire_time(None, now)
            except Exception:
                pass
        return None

    @computed_field
    @property
    def upcoming_runs(self) -> list[datetime]:
        """Return the next scheduled fire times for recurring tasks.

        Returns up to 60 upcoming occurrences so the calendar can display all
        instances within any visible date range (covers ~1 year of weekly tasks).
        Only populated for enabled ``recurring`` tasks; always empty for
        ``once`` tasks.  Fire times are computed using the task's stored timezone.
        """
        from datetime import timedelta

        MAX_OCCURRENCES = 60
        if self.type != "recurring" or not self.cron_expression or not self.enabled:
            return []
        try:
            from grug.scheduler.manager import unix_cron_to_trigger

            trigger = unix_cron_to_trigger(self.cron_expression, timezone=self.timezone)
            now = datetime.now(timezone.utc)
            results: list[datetime] = []
            current = now
            for _ in range(MAX_OCCURRENCES):
                nxt = trigger.get_next_fire_time(None, current)
                if nxt is None:
                    break
                results.append(nxt)
                current = nxt + timedelta(seconds=1)
            return results
        except Exception:
            return []


class TaskToggle(BaseModel):
    enabled: bool


class ScheduledTaskUpdate(BaseModel):
    """Full update payload for a scheduled task (all fields optional).

    Any field included in the request body will be applied; omitted fields
    are left unchanged (uses ``model_fields_set`` on the server side).
    """

    enabled: bool | None = None
    name: str | None = None
    prompt: str | None = None
    fire_at: datetime | None = None
    cron_expression: str | None = None
    channel_id: str | None = None


class ScheduledTaskCreate(BaseModel):
    type: str  # 'once' | 'recurring'
    name: str | None = None
    prompt: str
    fire_at: datetime | None = None
    cron_expression: str | None = None
    enabled: bool = True
    channel_id: str | None = None  # optional: used for guild tasks


class ScheduledTaskRunOut(BaseModel):
    """A single execution record for a scheduled task."""

    id: int
    task_id: int | None
    guild_id: int
    ran_at: datetime
    triggered_by: str
    response: str | None
    success: bool

    model_config = {"from_attributes": True}

    @field_serializer("guild_id")
    def serialize_guild_id(self, v: int) -> str:
        return str(v)


class CronFromTextRequest(BaseModel):
    text: str


class CronFromTextOut(BaseModel):
    cron_expression: str


class RruleFromTextRequest(BaseModel):
    text: str


class RruleFromTextOut(BaseModel):
    rrule: str


class DocumentOut(BaseModel):
    id: int
    guild_id: int
    filename: str
    description: str | None
    chroma_collection: str
    chunk_count: int
    uploaded_by: int
    campaign_id: int | None
    content_hash: str | None
    is_public: bool
    file_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    description: str | None = None
    is_public: bool | None = None


class DocumentSearchRequest(BaseModel):
    query: str
    k: int = 5
    document_id: int | None = None


class DocumentChunk(BaseModel):
    text: str
    filename: str
    chunk_index: int
    distance: float


class DocumentSearchResult(BaseModel):
    chunks: list[DocumentChunk]
    error: bool = False


class GlossaryTermOut(BaseModel):
    id: int
    guild_id: int
    channel_id: int | None
    term: str
    definition: str
    ai_generated: bool
    originally_ai_generated: bool
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "created_by")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)

    @field_serializer("channel_id")
    def serialize_channel_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None


class GlossaryTermCreate(BaseModel):
    term: str
    definition: str
    channel_id: int | None = None


class GlossaryTermUpdate(BaseModel):
    term: str | None = None
    definition: str | None = None


class GlossaryTermHistoryOut(BaseModel):
    id: int
    term_id: int
    guild_id: int
    old_term: str
    old_definition: str
    old_ai_generated: bool
    changed_by: int
    changed_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "changed_by")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class DiscordChannelOut(BaseModel):
    id: str
    name: str
    type: int


class CampaignOut(BaseModel):
    id: int
    guild_id: int
    channel_id: int
    name: str
    system: str
    is_active: bool
    gm_discord_user_id: int | None = None
    schedule_mode: str = "fixed"
    combat_tracker_depth: str = "standard"
    # Banking
    banking_enabled: bool = False
    player_banking_enabled: bool = False
    party_gold: float = 0.0
    # Dice
    allow_manual_dice_recording: bool = False
    # AI model override — None means use the server default
    llm_model: str | None = None
    created_by: int
    created_at: datetime
    deleted_at: datetime | None = None
    character_count: int = 0

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "channel_id", "created_by")
    def serialize_snowflakes(self, v: int) -> str:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v)

    @field_serializer("gm_discord_user_id")
    def serialize_gm_id(self, v: int | None) -> str | None:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v) if v is not None else None


class CampaignCreate(BaseModel):
    name: str
    system: str = "unknown"
    # Accept string or int to avoid JS precision loss on large Discord snowflake IDs
    channel_id: str | int
    gm_discord_user_id: str | int | None = None
    schedule_mode: str = "fixed"
    combat_tracker_depth: str = "standard"
    banking_enabled: bool = False
    player_banking_enabled: bool = False
    allow_manual_dice_recording: bool = False
    # AI model override — None means use the server default (claude-haiku-4-5)
    llm_model: str | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    system: str | None = None
    is_active: bool | None = None
    channel_id: str | int | None = None
    gm_discord_user_id: str | int | None = None
    schedule_mode: str | None = None
    combat_tracker_depth: str | None = None
    banking_enabled: bool | None = None
    player_banking_enabled: bool | None = None
    allow_manual_dice_recording: bool | None = None
    # AI model override — None means use the server default (claude-haiku-4-5)
    llm_model: str | None = None


class CharacterCreate(BaseModel):
    name: str
    system: str = "unknown"
    owner_discord_user_id: int | None = None
    owner_display_name: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = None
    system: str | None = None
    campaign_id: int | None = None
    owner_discord_user_id: int | None = None
    owner_display_name: str | None = None
    notes: str | None = None


class CharacterOut(BaseModel):
    id: int
    owner_discord_user_id: int | None
    owner_display_name: str | None = None
    campaign_id: int | None
    name: str
    system: str
    structured_data: dict | None
    pathbuilder_id: int | None = None
    file_path: str | None
    notes: str | None = None
    gold: float = 0.0
    pathbuilder_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("owner_discord_user_id")
    def serialize_owner_id(self, v: int | None) -> str | None:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v) if v is not None else None


class PathbuilderLinkRequest(BaseModel):
    """Request body for linking a Pathbuilder 2e character by ID.

    When ``pathbuilder_data`` is provided (pre-fetched by the browser, which
    bypasses Cloudflare bot protection on the Pathbuilder endpoint), the server
    normalises it directly without making an outbound HTTP request.
    """

    pathbuilder_id: int
    pathbuilder_data: dict | None = None


class SyncPathbuilderRequest(BaseModel):
    """Optional request body for re-syncing a Pathbuilder-linked character.

    Pass ``pathbuilder_data`` (the raw JSON fetched client-side) to skip the
    server-side fetch, which is blocked by Cloudflare bot protection.
    """

    pathbuilder_data: dict | None = None


class CharacterCopyRequest(BaseModel):
    """Request body for copying a character to a different campaign."""

    target_campaign_id: int


# --------------------------------------------------------------------------- #
# Gold banking schemas                                                         #
# --------------------------------------------------------------------------- #


class GoldAdjustRequest(BaseModel):
    """Adjust a gold balance by a signed amount.  Positive = credit, negative = debit."""

    amount: float
    reason: str | None = None


class GoldTransferRequest(BaseModel):
    """Transfer gold between a character wallet and the party pool.

    Exactly one of ``from_character_id`` / ``to_character_id`` must be None
    (the None side means the party pool).
    """

    from_character_id: int | None = None  # None = from party pool
    to_character_id: int | None = None  # None = to party pool
    amount: float
    reason: str | None = None


class GoldTransactionOut(BaseModel):
    id: int
    campaign_id: int
    character_id: int | None = None
    actor_discord_user_id: int
    amount: float
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("actor_discord_user_id")
    def _serialize_actor_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None


class UserProfileOut(BaseModel):
    id: int
    discord_user_id: int
    active_character_id: int | None
    dm_context_cutoff: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserDmConfigUpdate(BaseModel):
    dm_context_cutoff: datetime | None = None


# --------------------------------------------------------------------------- #
# Admin schemas                                                                #
# --------------------------------------------------------------------------- #


class GrugUserOut(BaseModel):
    discord_user_id: str
    can_invite: bool
    is_super_admin: bool = False
    is_env_super_admin: bool = (
        False  # True when elevated via GRUG_SUPER_ADMIN_IDS env var
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("discord_user_id")
    def serialize_discord_user_id(self, v: int) -> str:
        return str(v)


class GrugUserUpdate(BaseModel):
    can_invite: bool | None = None
    is_super_admin: bool | None = None


class DiscordUserOut(BaseModel):
    """Resolved Discord user profile from the bot API."""

    discord_user_id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    profile_url: str


class DiscordMemberOut(BaseModel):
    """A Discord guild member returned by the member-search endpoint."""

    discord_user_id: str
    username: str
    display_name: str
    avatar_url: str | None = None


class InviteUrlOut(BaseModel):
    url: str


class AdminGuildOut(BaseModel):
    """Guild record returned by the super-admin guild management endpoint."""

    guild_id: str
    name: str
    icon: str | None = None
    member_count: int | None = None
    total_campaigns: int = 0
    active_campaigns: int = 0
    total_messages: int = 0
    joined_at: datetime


# --------------------------------------------------------------------------- #
# RSVP schemas                                                                 #
# --------------------------------------------------------------------------- #


class EventRSVPOut(BaseModel):
    id: int
    event_id: int
    discord_user_id: int
    status: str
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("discord_user_id")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class EventRSVPUpsert(BaseModel):
    status: str  # 'attending' | 'maybe' | 'declined'
    note: str | None = None


# --------------------------------------------------------------------------- #
# Planning Notes schemas                                                       #
# --------------------------------------------------------------------------- #


class EventNoteOut(BaseModel):
    id: int
    event_id: int
    content: str
    done: bool
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_by")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class EventNoteCreate(BaseModel):
    content: str


class EventNoteUpdate(BaseModel):
    content: str | None = None
    done: bool | None = None


# --------------------------------------------------------------------------- #
# Occurrence Override schemas                                                  #
# --------------------------------------------------------------------------- #


class EventOccurrenceOverrideOut(BaseModel):
    id: int
    event_id: int
    original_start: datetime
    new_start: datetime | None
    new_end: datetime | None
    cancelled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventOccurrenceOverrideUpsert(BaseModel):
    original_start: datetime
    new_start: datetime | None = None
    new_end: datetime | None = None
    cancelled: bool = False


# --------------------------------------------------------------------------- #
# Availability Poll schemas                                                    #
# --------------------------------------------------------------------------- #


class PollOptionIn(BaseModel):
    id: int
    label: str
    start_time: datetime | None = None
    end_time: datetime | None = None


class AvailabilityPollCreate(BaseModel):
    title: str
    options: list[PollOptionIn]
    event_id: int | None = None
    closes_at: datetime | None = None


class PollVoteOut(BaseModel):
    id: int
    poll_id: int
    discord_user_id: int
    option_ids: list[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("discord_user_id")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class AvailabilityPollOut(BaseModel):
    id: int
    guild_id: int
    event_id: int | None
    title: str
    options: list[dict]
    closes_at: datetime | None
    winner_option_id: int | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    votes: list[PollVoteOut] = []

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "created_by")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class PollVoteUpsert(BaseModel):
    option_ids: list[int]


class AvailabilityPollUpdate(BaseModel):
    winner_option_id: int | None = None
    closes_at: datetime | None = None


# ── Rule Sources ────────────────────────────────────────────────────────────


class BuiltinRuleSourceOut(BaseModel):
    """A built-in rule source with its effective enabled state for a guild."""

    source_id: str
    name: str
    description: str
    system: str | None
    url: str
    enabled: bool
    """True if this source is active for the guild (default True, overridden via DB)."""


class BuiltinOverrideUpdate(BaseModel):
    enabled: bool


class RuleSourceTestRequest(BaseModel):
    """Run a live test query against a built-in rule source."""

    query: str
    source_id: str | None = None


class RuleSourceTestResult(BaseModel):
    """Raw result text returned by the source fetch function."""

    result: str
    error: bool = False


# ── Grug Notes ──────────────────────────────────────────────────────────────


class GrugNoteOut(BaseModel):
    id: int
    guild_id: int | None
    user_id: int | None
    content: str
    updated_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("guild_id")
    def serialize_guild_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("user_id", "updated_by")
    def serialize_user_ids(self, v: int | None) -> str | None:
        return str(v) if v is not None else None


class GrugNoteUpdate(BaseModel):
    content: str


class SessionNoteOut(BaseModel):
    id: int
    campaign_id: int
    guild_id: int
    session_date: date | None = None
    title: str | None = None
    raw_notes: str
    clean_notes: str | None = None
    synthesis_status: str
    synthesis_error: str | None = None
    rag_document_id: int | None = None
    submitted_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("submitted_by", "guild_id")
    def serialize_snowflakes(self, v: int) -> str:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v)


class SessionNoteCreate(BaseModel):
    raw_notes: str
    session_date: date | None = None
    title: str | None = None


class SessionNoteUpdate(BaseModel):
    raw_notes: str | None = None
    session_date: date | None = None
    title: str | None = None


class SessionNoteRagTestRequest(BaseModel):
    """Payload for a live RAG test against indexed session notes."""

    query: str
    k: int = 5


# --------------------------------------------------------------------------- #
# Dice rolling schemas                                                         #
# --------------------------------------------------------------------------- #


class DiceRollRequest(BaseModel):
    """Roll dice via the API."""

    expression: str
    roll_type: str = "general"
    is_private: bool = False
    context_note: str | None = None
    character_name: str | None = None


class ManualDiceRecordRequest(BaseModel):
    """Record a manual (physical) dice roll."""

    expression: str  # e.g. "1d20+5" — what they rolled
    total: int  # the result they got
    roll_type: str = "general"
    is_private: bool = False
    context_note: str | None = None
    character_name: str | None = None


class DiceRollIndividual(BaseModel):
    """A single dice group result within a roll."""

    expression: str
    sides: int
    rolls: list[int]
    kept: list[int]
    total: int


class DiceRollOut(BaseModel):
    """A persisted dice roll record."""

    id: int
    guild_id: int
    campaign_id: int | None = None
    roller_discord_user_id: int
    roller_display_name: str
    character_name: str | None = None
    expression: str
    individual_rolls: list[dict]
    total: int
    roll_type: str
    is_private: bool
    context_note: str | None = None
    formatted: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("roller_discord_user_id")
    def serialize_roller_id(self, v: int) -> str:
        return str(v)

    @field_serializer("guild_id")
    def serialize_guild_id(self, v: int) -> str:
        return str(v)


# ── Encounters / Initiative ──────────────────────────────────────────


class CombatantOut(BaseModel):
    id: int
    encounter_id: int
    character_id: int | None = None
    name: str
    initiative_roll: int | None = None
    initiative_modifier: int = 0
    is_enemy: bool = False
    is_hidden: bool = False
    sort_order: int = 0
    is_active: bool = True
    # HP / AC (standard+ depth)
    max_hp: int | None = None
    current_hp: int | None = None
    temp_hp: int = 0
    armor_class: int | None = None
    conditions: list[str] | None = None
    save_modifiers: dict[str, int] | None = None
    # Death saves & concentration (full depth)
    death_save_successes: int = 0
    death_save_failures: int = 0
    concentration_spell: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EncounterOut(BaseModel):
    id: int
    campaign_id: int
    guild_id: int
    name: str
    status: str
    current_turn_index: int = 0
    round_number: int = 1
    channel_id: int | None = None
    created_by: int
    created_at: datetime
    ended_at: datetime | None = None
    combatants: list[CombatantOut] = []

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "created_by")
    def serialize_snowflakes(self, v: int) -> str:
        return str(v)

    @field_serializer("channel_id")
    def serialize_channel_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None


class EncounterCreate(BaseModel):
    name: str
    channel_id: str | int | None = None


class EncounterUpdate(BaseModel):
    name: str


class CombatantCreate(BaseModel):
    name: str
    initiative_modifier: int = 0
    is_enemy: bool = False
    is_hidden: bool = False
    character_id: int | None = None
    max_hp: int | None = None
    armor_class: int | None = None
    save_modifiers: dict[str, int] | None = None


class CombatantUpdate(BaseModel):
    name: str | None = None
    is_hidden: bool | None = None


class SetInitiativeBody(BaseModel):
    """Body for manually setting a combatant's initiative roll value.

    Pass ``null`` / ``None`` to clear a previously entered manual roll.
    """

    initiative_roll: int | None = None


class CombatLogEntryOut(BaseModel):
    id: int
    encounter_id: int
    combatant_id: int
    round_number: int
    event_type: str
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class DamageHealBody(BaseModel):
    """Body for damage/heal API endpoints."""

    combatant_ids: list[int]
    amount: int
    damage_type: str | None = None
    source: str | None = None


class SavingThrowBody(BaseModel):
    """Body for the saving throw API endpoint."""

    combatant_ids: list[int]
    ability: str
    dc: int


class ConditionBody(BaseModel):
    """Body for add/remove condition API endpoints."""

    combatant_ids: list[int]
    condition: str


class ConcentrationBody(BaseModel):
    """Body for setting concentration."""

    spell: str | None = None


class SavingThrowResult(BaseModel):
    """Result of a single saving throw."""

    combatant_id: int
    combatant_name: str
    roll: int
    modifier: int
    total: int
    dc: int
    passed: bool


class MonsterSearchResult(BaseModel):
    """Structured monster data returned by the monster search API."""

    name: str
    source: str
    system: str
    hp: int | None = None
    ac: int | None = None
    initiative_modifier: int | None = None
    cr: str | None = None
    size: str | None = None
    type: str | None = None
    save_modifiers: dict[str, int] | None = None
