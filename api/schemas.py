"""Pydantic response schemas for the API."""

from datetime import datetime, timezone

from pydantic import BaseModel, computed_field, field_serializer


class UserOut(BaseModel):
    id: str
    username: str
    discriminator: str
    avatar: str | None = None


class DefaultsOut(BaseModel):
    default_timezone: str


class GuildOut(BaseModel):
    id: str
    name: str
    icon: str | None = None


class GuildConfigOut(BaseModel):
    guild_id: int
    timezone: str
    announce_channel_id: int | None

    model_config = {"from_attributes": True}

    @field_serializer("announce_channel_id")
    def serialize_announce_channel_id(self, v: int | None) -> str | None:
        """Return as string to avoid JS precision loss on large Discord snowflake IDs."""
        return str(v) if v is not None else None


class GuildConfigUpdate(BaseModel):
    timezone: str | None = None
    # Accept string or int to avoid JS precision loss on large Discord snowflake IDs
    announce_channel_id: str | int | None = None


class CalendarEventOut(BaseModel):
    id: int
    guild_id: int
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime | None
    channel_id: int | None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


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
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}

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
    created_at: datetime

    model_config = {"from_attributes": True}
