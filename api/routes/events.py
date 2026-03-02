"""Event and task routes."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_guild_member, get_current_user, get_db
from api.schemas import (
    CalendarEventOut,
    CronFromTextOut,
    CronFromTextRequest,
    ScheduledTaskCreate,
    ScheduledTaskOut,
    TaskToggle,
)
from grug.db.models import CalendarEvent, GuildConfig, ScheduledTask
from grug.utils import ensure_guild

router = APIRouter(tags=["events"])


# --------------------------------------------------------------------------- #
# Calendar events                                                              #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/events", response_model=list[CalendarEventOut])
async def list_events(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarEvent]:
    """List upcoming calendar events for a guild."""
    assert_guild_member(guild_id, user)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.guild_id == guild_id, CalendarEvent.start_time >= now)
        .order_by(CalendarEvent.start_time)
    )
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Scheduled tasks                                                              #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/tasks", response_model=list[ScheduledTaskOut])
async def list_tasks(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledTask]:
    """List scheduled tasks for a guild."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(ScheduledTask)
        .where(ScheduledTask.guild_id == guild_id)
        .order_by(ScheduledTask.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/tasks/cron-from-text", response_model=CronFromTextOut
)
async def guild_cron_from_text(
    guild_id: int,
    body: CronFromTextRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> CronFromTextOut:
    """Convert a plain-English schedule description to a 5-field UTC cron expression."""
    assert_guild_member(guild_id, user)
    from pydantic import BaseModel as PydanticBase
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from grug.config.settings import get_settings

    class _CronResult(PydanticBase):
        cron_expression: str

    settings = get_settings()
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = AnthropicModel(settings.anthropic_model, provider=provider)
    agent: Agent[None, _CronResult] = Agent(
        model,
        output_type=_CronResult,
        system_prompt=(
            "You convert plain-English schedule descriptions into a single 5-field UTC "
            "cron expression (minute, hour, day-of-month, month, day-of-week). "
            "Return ONLY the cron_expression field. Do not explain. Examples:\n"
            "  'every Monday at 9am UTC' -> '0 9 * * 1'\n"
            "  'every day at midnight' -> '0 0 * * *'\n"
            "  'every weekday at 5pm UTC' -> '0 17 * * 1-5'"
        ),
    )
    result = await agent.run(body.text)
    return CronFromTextOut(cron_expression=result.output.cron_expression)


@router.post(
    "/api/guilds/{guild_id}/tasks", response_model=ScheduledTaskOut, status_code=201
)
async def create_guild_task(
    guild_id: int,
    body: ScheduledTaskCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Create a new scheduled task for a guild via the web UI."""
    assert_guild_member(guild_id, user)
    user_id = int(user["id"])
    await ensure_guild(guild_id)

    # Resolve channel_id: use the provided value or fall back to the guild's announce channel
    if body.channel_id is not None:
        channel_id = int(body.channel_id)
    else:
        cfg_result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        cfg = cfg_result.scalar_one_or_none()
        channel_id = (
            int(cfg.announce_channel_id) if cfg and cfg.announce_channel_id else 0
        )

    name = body.name or (body.prompt[:80] if body.type == "once" else None)
    task = ScheduledTask(
        guild_id=guild_id,
        channel_id=channel_id,
        type=body.type,
        name=name,
        prompt=body.prompt,
        fire_at=body.fire_at,
        cron_expression=body.cron_expression,
        enabled=body.enabled,
        created_by=user_id,
        user_id=user_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/api/guilds/{guild_id}/tasks/{task_id}", response_model=ScheduledTaskOut)
async def toggle_task(
    guild_id: int,
    task_id: int,
    body: TaskToggle,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Enable or disable a scheduled task."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.guild_id == guild_id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.enabled = body.enabled
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/api/guilds/{guild_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    guild_id: int,
    task_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a scheduled task."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.guild_id == guild_id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
