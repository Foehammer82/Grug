"""Pydantic response schemas for the API."""

from datetime import datetime, timezone

from pydantic import BaseModel, computed_field, field_serializer


class UserOut(BaseModel):
    id: str
    username: str
    discriminator: str
    avatar: str | None = None
    is_super_admin: bool = False
    can_invite: bool = False


class DefaultsOut(BaseModel):
    default_timezone: str


class GuildOut(BaseModel):
    id: str
    name: str
    icon: str | None = None
    is_admin: bool = False


class GuildConfigOut(BaseModel):
    guild_id: int
    timezone: str
    announce_channel_id: int | None
    context_cutoff: datetime | None

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
    context_cutoff: datetime | None = None


class ChannelConfigOut(BaseModel):
    channel_id: int
    guild_id: int
    always_respond: bool
    context_cutoff: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("channel_id", "guild_id")
    def serialize_snowflake(self, v: int) -> str:
        return str(v)


class ChannelConfigUpdate(BaseModel):
    always_respond: bool | None = None
    context_cutoff: datetime | None = None


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


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    rrule: str | None = None
    location: str | None = None
    channel_id: str | int | None = None


class ScheduledTaskOut(BaseModel):
    id: int
    guild_id: int
    channel_id: int
    type: str
    name: str | None
    prompt: str
    fire_at: datetime | None
    cron_expression: str | None
    user_id: int | None
    enabled: bool
    last_run: datetime | None
    source: str
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
        the next fire time from the stored cron expression.
        """
        now = datetime.now(timezone.utc)
        if self.type == "once":
            if self.fire_at and not self.last_run and self.fire_at > now:
                return self.fire_at
        elif self.type == "recurring" and self.cron_expression and self.enabled:
            try:
                from apscheduler.triggers.cron import CronTrigger

                parts = self.cron_expression.strip().split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    trigger = CronTrigger(
                        minute=minute,
                        hour=hour,
                        day=day,
                        month=month,
                        day_of_week=day_of_week,
                    )
                    return trigger.get_next_fire_time(None, now)
            except Exception:
                pass
        return None


class TaskToggle(BaseModel):
    enabled: bool


class ScheduledTaskCreate(BaseModel):
    type: str  # 'once' | 'recurring'
    name: str | None = None
    prompt: str
    fire_at: datetime | None = None
    cron_expression: str | None = None
    enabled: bool = True
    channel_id: str | None = None  # optional: used for guild tasks


class CronFromTextRequest(BaseModel):
    text: str


class CronFromTextOut(BaseModel):
    cron_expression: str


class DocumentOut(BaseModel):
    id: int
    guild_id: int
    filename: str
    description: str | None
    chroma_collection: str
    chunk_count: int
    uploaded_by: int
    campaign_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    description: str | None = None


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
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("guild_id", "channel_id", "created_by")
    def serialize_snowflakes(self, v: int) -> str:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v)


class CampaignCreate(BaseModel):
    name: str
    system: str = "unknown"
    # Accept string or int to avoid JS precision loss on large Discord snowflake IDs
    channel_id: str | int


class CampaignUpdate(BaseModel):
    name: str | None = None
    system: str | None = None
    is_active: bool | None = None
    channel_id: str | int | None = None


class CharacterOut(BaseModel):
    id: int
    owner_discord_user_id: int
    campaign_id: int | None
    name: str
    system: str
    structured_data: dict | None
    file_path: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
