"""Event, task, and reminder routes."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_guild_member, get_current_user, get_db
from api.schemas import (
    CalendarEventOut,
    ReminderOut,
    ScheduledTaskOut,
    TaskToggle,
)
from grug.db.models import CalendarEvent, Reminder, ScheduledTask

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


# --------------------------------------------------------------------------- #
# Reminders                                                                    #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/reminders", response_model=list[ReminderOut])
async def list_reminders(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Reminder]:
    """List reminders for a guild, ordered by reminder time."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(Reminder)
        .where(Reminder.guild_id == guild_id)
        .order_by(Reminder.remind_at)
    )
    return list(result.scalars().all())
