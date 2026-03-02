"""Personal (DM) routes — data created during direct messages with Grug.

DM-originated data is stored with guild_id = 0.  These endpoints expose that
data without a guild membership check (the user just needs to be authenticated).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.schemas import ScheduledTaskOut, TaskToggle
from grug.db.models import ScheduledTask

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
    result = await db.execute(
        select(ScheduledTask)
        .where(ScheduledTask.guild_id == _DM_GUILD_ID)
        .order_by(ScheduledTask.created_at)
    )
    return list(result.scalars().all())


@router.patch("/tasks/{task_id}", response_model=ScheduledTaskOut)
async def toggle_personal_task(
    task_id: int,
    body: TaskToggle,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Enable or disable a personal scheduled task."""
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.guild_id == _DM_GUILD_ID
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
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
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.guild_id == _DM_GUILD_ID
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
