"""Manager agent API routes — user feedback, instruction overrides, and reviews.

All endpoints are scoped to a guild and require authentication.
Instruction overrides and manager reviews require guild admin access.
Feedback submission is open to all guild members.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_member,
    assert_super_admin,
    get_current_user,
    get_db,
)
from grug.config.settings import get_settings
from grug.db.models import (
    ConversationMessage,
    InstructionOverride,
    ManagerReview,
    UserFeedback,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["manager"])


def _assert_manager_enabled() -> None:
    """Raise 503 if the manager agent feature is disabled via env var."""
    if not get_settings().manager_review_enabled:
        raise HTTPException(
            status_code=503,
            detail="Manager agent is disabled. Set MANAGER_REVIEW_ENABLED=true to enable it.",
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FeedbackCreate(BaseModel):
    message_id: int
    rating: int  # +1 or -1
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: int
    guild_id: str
    channel_id: str
    message_id: int
    discord_user_id: str
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InstructionOverrideOut(BaseModel):
    id: int
    guild_id: str
    channel_id: str | None
    scope: str
    content: str
    status: str
    source: str
    review_id: int | None
    reason: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InstructionOverrideCreate(BaseModel):
    content: str
    scope: str = "guild"
    channel_id: str | None = None
    reason: str | None = None


class InstructionOverrideUpdate(BaseModel):
    content: str | None = None
    status: str | None = None
    reason: str | None = None


class ManagerReviewOut(BaseModel):
    id: int
    guild_id: str
    status: str
    messages_reviewed: int
    feedback_reviewed: int
    summary: str | None
    observations: list | None
    recommendations: list | None
    webhook_sent: bool
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Feedback endpoints
# ---------------------------------------------------------------------------


@router.post("/api/guilds/{guild_id}/feedback", response_model=FeedbackOut)
async def submit_feedback(
    guild_id: int,
    body: FeedbackCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Submit feedback on a Grug response.

    ``rating`` must be +1 (positive) or -1 (negative).
    ``message_id`` refers to a conversation_messages row (the assistant response).
    """
    await assert_guild_member(guild_id, user)

    if body.rating not in (1, -1):
        raise HTTPException(status_code=422, detail="rating must be +1 or -1")

    # Verify the message exists and belongs to this guild
    msg = (
        await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.id == body.message_id,
                ConversationMessage.guild_id == guild_id,
                ConversationMessage.role == "assistant",
            )
        )
    ).scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    user_id = int(user["id"])

    # Upsert — one feedback per user per message
    existing = (
        await db.execute(
            select(UserFeedback).where(
                UserFeedback.message_id == body.message_id,
                UserFeedback.discord_user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.rating = body.rating
        existing.comment = body.comment
        await db.commit()
        await db.refresh(existing)
        return _feedback_to_out(existing)

    fb = UserFeedback(
        guild_id=guild_id,
        channel_id=msg.channel_id,
        message_id=body.message_id,
        discord_user_id=user_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return _feedback_to_out(fb)


def _feedback_to_out(fb: UserFeedback) -> dict[str, Any]:
    """Convert a UserFeedback ORM object to a dict with string snowflakes."""
    return {
        "id": fb.id,
        "guild_id": str(fb.guild_id),
        "channel_id": str(fb.channel_id),
        "message_id": fb.message_id,
        "discord_user_id": str(fb.discord_user_id),
        "rating": fb.rating,
        "comment": fb.comment,
        "created_at": fb.created_at,
    }


# ---------------------------------------------------------------------------
# Instruction override endpoints
# ---------------------------------------------------------------------------


@router.get("/api/manager/enabled")
async def manager_enabled(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, bool]:
    """Return whether the manager agent feature is enabled (any authenticated user)."""
    return {"enabled": get_settings().manager_review_enabled}


@router.get(
    "/api/guilds/{guild_id}/instructions",
    response_model=list[InstructionOverrideOut],
)
async def list_instructions(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    """List all instruction overrides for a guild (super-admin only)."""
    _assert_manager_enabled()
    await assert_guild_member(guild_id, user)
    await assert_super_admin(user)

    result = await db.execute(
        select(InstructionOverride)
        .where(InstructionOverride.guild_id == guild_id)
        .order_by(InstructionOverride.created_at.desc())
    )
    overrides = result.scalars().all()
    return [_override_to_out(o) for o in overrides]


@router.post(
    "/api/guilds/{guild_id}/instructions",
    response_model=InstructionOverrideOut,
    status_code=201,
)
async def create_instruction(
    guild_id: int,
    body: InstructionOverrideCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new instruction override (super-admin only)."""
    _assert_manager_enabled()
    await assert_guild_member(guild_id, user)
    await assert_super_admin(user)

    if body.scope not in ("guild", "channel"):
        raise HTTPException(status_code=422, detail="scope must be 'guild' or 'channel'")

    if body.scope == "channel" and body.channel_id is None:
        raise HTTPException(
            status_code=422, detail="channel_id required for channel-scoped overrides"
        )

    channel_id_int: int | None = None
    if body.channel_id is not None:
        try:
            channel_id_int = int(body.channel_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="channel_id must be a numeric Discord channel ID",
            )

    override = InstructionOverride(
        guild_id=guild_id,
        channel_id=channel_id_int,
        scope=body.scope,
        content=body.content,
        status="active",
        source="admin",
        reason=body.reason,
        created_by=int(user["id"]),
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)
    return _override_to_out(override)


@router.patch(
    "/api/guilds/{guild_id}/instructions/{override_id}",
    response_model=InstructionOverrideOut,
)
async def update_instruction(
    guild_id: int,
    override_id: int,
    body: InstructionOverrideUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update an instruction override — change content, status, or reason.

    Use ``status: 'active'`` to apply a pending recommendation.
    Use ``status: 'rejected'`` to reject a pending recommendation.
    """
    _assert_manager_enabled()
    await assert_guild_member(guild_id, user)
    await assert_super_admin(user)

    override = (
        await db.execute(
            select(InstructionOverride).where(
                InstructionOverride.id == override_id,
                InstructionOverride.guild_id == guild_id,
            )
        )
    ).scalar_one_or_none()
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found")

    if "content" in body.model_fields_set:
        override.content = body.content
    if "status" in body.model_fields_set:
        if body.status not in ("active", "pending", "rejected"):
            raise HTTPException(
                status_code=422,
                detail="status must be 'active', 'pending', or 'rejected'",
            )
        override.status = body.status
    if "reason" in body.model_fields_set:
        override.reason = body.reason

    await db.commit()
    await db.refresh(override)
    return _override_to_out(override)


@router.delete(
    "/api/guilds/{guild_id}/instructions/{override_id}",
    status_code=204,
)
async def delete_instruction(
    guild_id: int,
    override_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an instruction override (super-admin only)."""
    _assert_manager_enabled()
    await assert_guild_member(guild_id, user)
    await assert_super_admin(user)

    override = (
        await db.execute(
            select(InstructionOverride).where(
                InstructionOverride.id == override_id,
                InstructionOverride.guild_id == guild_id,
            )
        )
    ).scalar_one_or_none()
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found")

    await db.delete(override)
    await db.commit()


def _override_to_out(o: InstructionOverride) -> dict[str, Any]:
    """Convert an InstructionOverride ORM object to a dict with string snowflakes."""
    return {
        "id": o.id,
        "guild_id": str(o.guild_id),
        "channel_id": str(o.channel_id) if o.channel_id is not None else None,
        "scope": o.scope,
        "content": o.content,
        "status": o.status,
        "source": o.source,
        "review_id": o.review_id,
        "reason": o.reason,
        "created_by": str(o.created_by),
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


# ---------------------------------------------------------------------------
# Manager review endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/guilds/{guild_id}/manager/reviews",
    response_model=list[ManagerReviewOut],
)
async def list_reviews(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    """List manager reviews for a guild (super-admin only)."""
    _assert_manager_enabled()
    await assert_guild_member(guild_id, user)
    await assert_super_admin(user)

    result = await db.execute(
        select(ManagerReview)
        .where(ManagerReview.guild_id == guild_id)
        .order_by(ManagerReview.created_at.desc())
        .limit(50)
    )
    reviews = result.scalars().all()
    return [_review_to_out(r) for r in reviews]


@router.post(
    "/api/guilds/{guild_id}/manager/reviews",
    response_model=ManagerReviewOut,
    status_code=201,
)
async def trigger_review(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Trigger an on-demand manager review for a guild (super-admin only).

    The review runs asynchronously — returns the review record immediately
    with ``status='running'``.  Poll the review list to see the result.
    """
    _assert_manager_enabled()
    await assert_guild_member(guild_id, user)
    await assert_super_admin(user)

    import asyncio

    from grug.manager.reviewer import run_review

    # Start the review in the background so the endpoint returns quickly.
    review = ManagerReview(
        guild_id=guild_id,
        status="pending",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    # Fire-and-forget — the reviewer creates its own DB session and manages
    # its own error state (sets status='failed' on exception).
    async def _bg_review() -> None:
        try:
            await run_review(guild_id=guild_id, review_id=review.id)
        except Exception:
            logger.exception(
                "Background manager review failed for guild %d (review id %d)",
                guild_id,
                review.id,
            )

    asyncio.create_task(_bg_review(), name=f"manager_review_{guild_id}")

    return _review_to_out(review)


def _review_to_out(r: ManagerReview) -> dict[str, Any]:
    """Convert a ManagerReview ORM object to a dict with string snowflakes."""
    return {
        "id": r.id,
        "guild_id": str(r.guild_id),
        "status": r.status,
        "messages_reviewed": r.messages_reviewed,
        "feedback_reviewed": r.feedback_reviewed,
        "summary": r.summary,
        "observations": r.observations,
        "recommendations": r.recommendations,
        "webhook_sent": r.webhook_sent,
        "error": r.error,
        "started_at": r.started_at,
        "completed_at": r.completed_at,
        "created_at": r.created_at,
    }
