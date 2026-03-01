"""Pydantic response schemas for the API."""

from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    username: str
    discriminator: str
    avatar: str | None = None


class GuildOut(BaseModel):
    id: str
    name: str
    icon: str | None = None


class GuildConfigOut(BaseModel):
    guild_id: int
    prefix: str
    timezone: str
    announce_channel_id: int | None

    model_config = {"from_attributes": True}


class GuildConfigUpdate(BaseModel):
    timezone: str | None = None
    announce_channel_id: int | None = None


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
    name: str
    prompt: str
    cron_expression: str
    enabled: bool
    last_run: datetime | None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


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
    created_at: datetime

    model_config = {"from_attributes": True}


class ReminderOut(BaseModel):
    id: int
    guild_id: int
    user_id: int
    channel_id: int
    message: str
    remind_at: datetime
    sent: bool
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
