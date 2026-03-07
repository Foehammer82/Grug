"""Personal (DM) routes — data created during direct messages with Grug.

DM-originated data is stored with guild_id = 0.  These endpoints expose that
data without a guild membership check (the user just needs to be authenticated).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db, get_or_404
from api.schemas import (
    CronFromTextOut,
    CronFromTextRequest,
    ScheduledTaskCreate,
    ScheduledTaskOut,
    TaskToggle,
    UserDmConfigUpdate,
    UserProfileOut,
)
from grug.db.models import ScheduledTask, UserProfile
from grug.utils import ensure_guild

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personal", tags=["personal"])

_DM_GUILD_ID = 0


# --------------------------------------------------------------------------- #
# Scheduled tasks                                                              #
# --------------------------------------------------------------------------- #


@router.get("/tasks", response_model=list[ScheduledTaskOut])
async def list_personal_tasks(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledTask]:
    """List scheduled tasks created via DMs with Grug."""
    user_id = int(user["id"])
    result = await db.execute(
        select(ScheduledTask)
        .where(ScheduledTask.guild_id == _DM_GUILD_ID)
        .where(ScheduledTask.user_id == user_id)
        .order_by(ScheduledTask.created_at)
    )
    return list(result.scalars().all())


@router.post("/tasks/cron-from-text", response_model=CronFromTextOut)
async def cron_from_text(
    body: CronFromTextRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> CronFromTextOut:
    """Convert a plain-English schedule description to a 5-field UTC cron expression."""
    from api.services import parse_cron_from_text

    cron_expr = await parse_cron_from_text(body.text)
    return CronFromTextOut(cron_expression=cron_expr)


@router.post("/tasks", response_model=ScheduledTaskOut, status_code=201)
async def create_personal_task(
    body: ScheduledTaskCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Create a new personal scheduled task via the web UI."""
    user_id = int(user["id"])
    # Ensure the DM guild config row exists (satisfies the FK constraint)
    await ensure_guild(_DM_GUILD_ID)
    # Auto-derive name for one-shot tasks if not provided (mirrors agent behaviour)
    name = body.name or (body.prompt[:80] if body.type == "once" else None)
    task = ScheduledTask(
        guild_id=_DM_GUILD_ID,
        channel_id=0,
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

    # Register with the local scheduler immediately so the task fires on time
    # without waiting for the bot's periodic sync (which runs every 30 minutes).
    if task.enabled:
        from grug.scheduler.manager import add_cron_job, add_date_job
        from grug.scheduler.tasks import execute_scheduled_task

        job_id = f"task_{task.id}"
        now = datetime.now(timezone.utc)
        try:
            if task.type == "once" and task.fire_at is not None and task.fire_at > now:
                add_date_job(
                    execute_scheduled_task,
                    run_date=task.fire_at,
                    job_id=job_id,
                    args=[task.id],
                )
            elif task.type == "recurring" and task.cron_expression:
                add_cron_job(
                    execute_scheduled_task,
                    cron_expression=task.cron_expression,
                    job_id=job_id,
                    args=[task.id],
                    timezone=task.timezone,
                )
        except Exception:
            # Log but don't fail the request — the bot's periodic sync will
            # pick up the task on its next pass.
            logger.exception(
                "Failed to register personal task %d with scheduler immediately",
                task.id,
            )

    return task


@router.patch("/tasks/{task_id}", response_model=ScheduledTaskOut)
async def toggle_personal_task(
    task_id: int,
    body: TaskToggle,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Enable or disable a personal scheduled task."""
    task = await get_or_404(
        db,
        ScheduledTask,
        ScheduledTask.id == task_id,
        ScheduledTask.guild_id == _DM_GUILD_ID,
        ScheduledTask.user_id == int(user["id"]),
        detail="Task not found",
    )
    task.enabled = body.enabled
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_personal_task(
    task_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a personal scheduled task."""
    task = await get_or_404(
        db,
        ScheduledTask,
        ScheduledTask.id == task_id,
        ScheduledTask.guild_id == _DM_GUILD_ID,
        ScheduledTask.user_id == int(user["id"]),
        detail="Task not found",
    )
    await db.delete(task)
    await db.commit()


# --------------------------------------------------------------------------- #
# DM context configuration                                                     #
# --------------------------------------------------------------------------- #


@router.get("/dm-config", response_model=UserProfileOut)
async def get_dm_config(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """Return the current user's DM configuration (includes context cutoff)."""
    user_id = int(user["id"])
    result = await db.execute(
        select(UserProfile).where(UserProfile.discord_user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(discord_user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.patch("/dm-config", response_model=UserProfileOut)
async def update_dm_config(
    body: UserDmConfigUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """Update the current user's DM context cutoff."""

    user_id = int(user["id"])
    result = await db.execute(
        select(UserProfile).where(UserProfile.discord_user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(discord_user_id=user_id)
        db.add(profile)
    if "dm_context_cutoff" in body.model_fields_set:
        profile.dm_context_cutoff = body.dm_context_cutoff
    await db.commit()
    await db.refresh(profile)
    return profile
