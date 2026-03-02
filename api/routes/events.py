"""Event and task routes."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_current_user,
    get_db,
    get_or_404,
)
from api.schemas import (
    CalendarEventCreate,
    CalendarEventOut,
    CalendarEventUpdate,
    CronFromTextOut,
    CronFromTextRequest,
    ScheduledTaskCreate,
    ScheduledTaskOut,
    TaskToggle,
)
from grug.db.models import CalendarEvent, GuildConfig, ScheduledTask
from grug.utils import ensure_guild, expand_event_occurrences

router = APIRouter(tags=["events"])


# --------------------------------------------------------------------------- #
# Calendar events                                                              #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/events", response_model=list[CalendarEventOut])
async def list_events(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start: datetime | None = Query(None, description="Range start (ISO 8601)"),
    end: datetime | None = Query(None, description="Range end (ISO 8601)"),
) -> list[dict]:
    """List calendar events for a guild.

    When *start* and *end* are supplied the response includes expanded
    occurrences of recurring events within that window.  Without range
    parameters the endpoint falls back to returning upcoming events
    (start_time >= now) without RRULE expansion.
    """
    assert_guild_member(guild_id, user)

    if start is not None and end is not None:
        # Date-range mode — return expanded occurrences.
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        result = await db.execute(
            select(CalendarEvent).where(CalendarEvent.guild_id == guild_id)
        )
        events = result.scalars().all()
        occurrences: list[dict] = []
        for ev in events:
            occurrences.extend(expand_event_occurrences(ev, start, end))
        occurrences.sort(key=lambda o: o["occurrence_start"])
        return occurrences
    else:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(CalendarEvent)
            .where(CalendarEvent.guild_id == guild_id, CalendarEvent.start_time >= now)
            .order_by(CalendarEvent.start_time)
        )
        rows = result.scalars().all()
        return [
            {
                "id": e.id,
                "guild_id": e.guild_id,
                "title": e.title,
                "description": e.description,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "rrule": e.rrule,
                "location": e.location,
                "channel_id": e.channel_id,
                "created_by": e.created_by,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
            }
            for e in rows
        ]


@router.post(
    "/api/guilds/{guild_id}/events", response_model=CalendarEventOut, status_code=201
)
async def create_event(
    guild_id: int,
    body: CalendarEventCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Create a new calendar event."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    user_id = int(user["id"])
    await ensure_guild(guild_id)

    channel_id = int(body.channel_id) if body.channel_id is not None else None
    event = CalendarEvent(
        guild_id=guild_id,
        title=body.title,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        rrule=body.rrule,
        location=body.location,
        channel_id=channel_id,
        created_by=user_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.patch(
    "/api/guilds/{guild_id}/events/{event_id}", response_model=CalendarEventOut
)
async def update_event(
    guild_id: int,
    event_id: int,
    body: CalendarEventUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Update a calendar event.  Uses ``model_fields_set`` so explicit
    ``null`` clears the field."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    event = await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )

    for field in body.model_fields_set:
        value = getattr(body, field)
        if field == "channel_id" and value is not None:
            value = int(value)
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/api/guilds/{guild_id}/events/{event_id}", status_code=204)
async def delete_event(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a calendar event."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    event = await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    await db.delete(event)
    await db.commit()


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
    from api.services import parse_cron_from_text

    cron_expr = await parse_cron_from_text(body.text)
    return CronFromTextOut(cron_expression=cron_expr)


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
    await assert_guild_admin(guild_id, user)
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
        source="web",
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
    await assert_guild_admin(guild_id, user)
    task = await get_or_404(
        db,
        ScheduledTask,
        ScheduledTask.id == task_id,
        ScheduledTask.guild_id == guild_id,
        detail="Task not found",
    )
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
    await assert_guild_admin(guild_id, user)
    task = await get_or_404(
        db,
        ScheduledTask,
        ScheduledTask.id == task_id,
        ScheduledTask.guild_id == guild_id,
        detail="Task not found",
    )
    await db.delete(task)
    await db.commit()
