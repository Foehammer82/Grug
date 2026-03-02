"""Personal (DM) routes — data created during direct messages with Grug.

DM-originated data is stored with guild_id = 0.  These endpoints expose that
data without a guild membership check (the user just needs to be authenticated).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.schemas import (
    CronFromTextOut,
    CronFromTextRequest,
    ScheduledTaskCreate,
    ScheduledTaskOut,
    TaskToggle,
)
from grug.db.models import ScheduledTask
from grug.utils import ensure_guild

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


@router.post("/tasks/cron-from-text", response_model=CronFromTextOut)
async def cron_from_text(
    body: CronFromTextRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> CronFromTextOut:
    """Convert a plain-English schedule description to a 5-field UTC cron expression."""
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
        created_by=user_id,
        user_id=user_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


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
