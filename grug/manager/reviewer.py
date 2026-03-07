"""Core manager agent — reviews Grug's conversations in batch.

The manager agent is a separate pydantic-ai agent that:
1. Loads recent conversation history + user feedback for a guild
2. Analyzes Grug's behaviour against his core rules
3. Produces a structured report with observations and recommendations
4. Optionally creates pending InstructionOverride records for admin review
5. Sends a summary to the configured Discord webhook
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from grug.config.settings import get_settings
from grug.llm_usage import CallType, record_llm_usage

logger = logging.getLogger(__name__)


class ReviewResult(BaseModel):
    """Structured result from a manager review."""

    summary: str = ""
    observations: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []


async def run_review(guild_id: int) -> int:
    """Run a manager review for a guild and return the ManagerReview.id.

    Steps:
    1. Create a ManagerReview record (status='running')
    2. Load recent messages + feedback
    3. Run the manager agent
    4. Parse the result and update the review record
    5. Create pending InstructionOverride records for recommendations
    6. Send webhook report
    7. Return the review ID
    """
    from sqlalchemy import select

    from grug.db.models import (
        ConversationMessage,
        GrugNote,
        InstructionOverride,
        ManagerReview,
        UserFeedback,
    )
    from grug.db.session import get_session_factory

    settings = get_settings()
    factory = get_session_factory()

    # ── Step 1: Create review record ──────────────────────────────────────
    async with factory() as session:
        review = ManagerReview(
            guild_id=guild_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)
        review_id = review.id

    try:
        # ── Step 2: Load data ─────────────────────────────────────────────
        lookback = datetime.now(timezone.utc) - timedelta(days=7)

        async with factory() as session:
            # Recent conversations (non-passive, non-archived)
            msg_result = await session.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.guild_id == guild_id,
                    ConversationMessage.archived.is_(False),
                    ConversationMessage.is_passive.is_(False),
                    ConversationMessage.created_at >= lookback,
                )
                .order_by(ConversationMessage.created_at.asc())
                .limit(200)
            )
            messages = msg_result.scalars().all()

            # Recent feedback
            fb_result = await session.execute(
                select(UserFeedback)
                .where(
                    UserFeedback.guild_id == guild_id,
                    UserFeedback.created_at >= lookback,
                )
                .order_by(UserFeedback.created_at.asc())
                .limit(100)
            )
            feedback_rows = fb_result.scalars().all()

            # Grug's guild-scoped notes (corrections, observations)
            notes_result = await session.execute(
                select(GrugNote)
                .where(
                    GrugNote.guild_id == guild_id,
                    GrugNote.user_id.is_(None),
                )
                .order_by(GrugNote.updated_at.desc())
                .limit(50)
            )
            grug_notes = notes_result.scalars().all()

            # Count
            msg_count = len(messages)
            fb_count = len(feedback_rows)

        if msg_count == 0:
            # Nothing to review
            async with factory() as session:
                result = await session.execute(
                    select(ManagerReview).where(ManagerReview.id == review_id)
                )
                review = result.scalar_one()
                review.status = "completed"
                review.summary = "No recent conversations to review."
                review.messages_reviewed = 0
                review.feedback_reviewed = 0
                review.completed_at = datetime.now(timezone.utc)
                await session.commit()
            return review_id

        # ── Step 3: Build prompt and call LLM ─────────────────────────────
        conversation_text = _format_messages(messages)
        feedback_text = _format_feedback(feedback_rows)
        notes_text = _format_notes(grug_notes)

        prompt = (
            f"Review the following conversation history from a Discord guild "
            f"(guild_id={guild_id}) over the past 7 days.\n\n"
            f"=== CONVERSATION HISTORY ({msg_count} messages) ===\n"
            f"{conversation_text}\n\n"
            f"=== USER FEEDBACK ({fb_count} items) ===\n"
            f"{feedback_text}\n\n"
            f"=== GRUG'S NOTES (corrections and observations logged by Grug) ===\n"
            f"{notes_text}\n\n"
            f"Pay special attention to any entries in Grug's Notes that reflect "
            f"user corrections, complaints, or patterns — these may indicate that "
            f"Grug's underlying prompt or codebase needs updating.\n\n"
            f"Analyze Grug's behaviour and produce your review."
        )

        result = await _call_manager_llm(prompt)

        # ── Step 4: Parse and update ──────────────────────────────────────
        parsed = _parse_review_result(result)

        async with factory() as session:
            review_obj = (
                await session.execute(
                    select(ManagerReview).where(ManagerReview.id == review_id)
                )
            ).scalar_one()
            review_obj.status = "completed"
            review_obj.messages_reviewed = msg_count
            review_obj.feedback_reviewed = fb_count
            review_obj.summary = parsed.summary
            review_obj.observations = [dict(o) for o in parsed.observations]
            review_obj.recommendations = [dict(r) for r in parsed.recommendations]
            review_obj.completed_at = datetime.now(timezone.utc)

            # ── Step 5: Create pending instruction overrides ──────────────
            for rec in parsed.recommendations:
                if rec.get("action") in ("add", "modify"):
                    override = InstructionOverride(
                        guild_id=guild_id,
                        content=rec.get("content", ""),
                        status="pending",
                        source="manager",
                        review_id=review_id,
                        reason=rec.get("reason", ""),
                        created_by=0,  # 0 = agent sentinel
                    )
                    session.add(override)

            await session.commit()

        # ── Step 6: Send webhook ──────────────────────────────────────────
        if settings.manager_webhook_url:
            await _send_webhook(settings.manager_webhook_url, guild_id, parsed)
            async with factory() as session:
                review_obj = (
                    await session.execute(
                        select(ManagerReview).where(ManagerReview.id == review_id)
                    )
                ).scalar_one()
                review_obj.webhook_sent = True
                await session.commit()

    except Exception:
        logger.exception("Manager review failed for guild %d", guild_id)
        async with factory() as session:
            review_obj = (
                await session.execute(
                    select(ManagerReview).where(ManagerReview.id == review_id)
                )
            ).scalar_one()
            review_obj.status = "failed"
            review_obj.error = "Review execution failed — check logs."
            review_obj.completed_at = datetime.now(timezone.utc)
            await session.commit()

    return review_id


def _format_messages(messages: list[Any]) -> str:
    """Format conversation messages into a readable text block."""
    lines: list[str] = []
    for msg in messages:
        ts = msg.created_at.isoformat() if msg.created_at else "?"
        author = msg.author_name or "unknown"
        role = msg.role
        content = (msg.content or "")[:500]  # Truncate long messages
        if role == "assistant":
            lines.append(f"[{ts}] GRUG: {content}")
        else:
            lines.append(f"[{ts}] {author}: {content}")
    return "\n".join(lines) if lines else "(no messages)"


def _format_notes(notes: list[Any]) -> str:
    """Format Grug's guild notes into a readable text block."""
    if not notes:
        return "(no notes)"
    lines: list[str] = []
    for note in notes:
        ts = note.updated_at.isoformat() if note.updated_at else "?"
        content = (note.content or "").strip()
        if content:
            lines.append(f"[updated {ts}]\n{content}")
    return "\n\n".join(lines) if lines else "(no notes)"


def _format_feedback(feedback_rows: list[Any]) -> str:
    """Format user feedback into a readable text block."""
    if not feedback_rows:
        return "(no feedback)"
    lines: list[str] = []
    for fb in feedback_rows:
        rating = "👍" if fb.rating > 0 else "👎"
        comment = f" — {fb.comment}" if fb.comment else ""
        lines.append(f"  {rating} on message #{fb.message_id}{comment}")
    return "\n".join(lines)


async def _call_manager_llm(prompt: str) -> str:
    """Call the LLM with the manager system prompt and return the response text."""
    import anthropic

    from grug.manager.prompt import MANAGER_SYSTEM_PROMPT

    settings = get_settings()
    # Use the big-brain model for manager reviews — they need deeper reasoning.
    model = settings.anthropic_big_brain_model

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=MANAGER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    await record_llm_usage(
        model=model,
        call_type=CallType.MANAGER_REVIEW,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return result_text


def _parse_review_result(raw: str) -> ReviewResult:
    """Parse the LLM's JSON response into a ReviewResult."""
    # Try to extract JSON from the response (may be wrapped in markdown code blocks)
    text = raw.strip()
    if text.startswith("```"):
        # Strip markdown code fences
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        return ReviewResult(
            summary=data.get("summary", ""),
            observations=data.get("observations", []),
            recommendations=data.get("recommendations", []),
        )
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse manager review as JSON, using raw text")
        return ReviewResult(
            summary=text[:500],
            observations=[],
            recommendations=[],
        )


async def _send_webhook(
    webhook_url: str, guild_id: int, result: ReviewResult
) -> None:
    """Send a review summary to the configured Discord webhook."""
    import httpx

    # Build the embed
    obs_text = ""
    if result.observations:
        obs_lines: list[str] = []
        for obs in result.observations[:10]:
            severity = obs.get("severity", "info")
            category = obs.get("category", "other")
            detail = obs.get("detail", "")[:200]
            icon = {"info": "ℹ️", "minor": "⚠️", "major": "🔶", "critical": "🔴"}.get(
                severity, "ℹ️"
            )
            obs_lines.append(f"{icon} **[{category}]** {detail}")
        obs_text = "\n".join(obs_lines)

    rec_text = ""
    if result.recommendations:
        rec_lines: list[str] = []
        for rec in result.recommendations[:5]:
            action = rec.get("action", "?")
            reason = rec.get("reason", "")[:200]
            rec_lines.append(f"• **{action}**: {reason}")
        rec_text = "\n".join(rec_lines)

    embed: dict[str, Any] = {
        "title": "📋 Grug Manager Review",
        "description": result.summary[:2000],
        "color": 0x58A6FF,  # GitHub blue accent
        "footer": {"text": f"Guild {guild_id}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    fields: list[dict[str, Any]] = []
    if obs_text:
        fields.append(
            {"name": "Observations", "value": obs_text[:1024], "inline": False}
        )
    if rec_text:
        fields.append(
            {"name": "Recommendations", "value": rec_text[:1024], "inline": False}
        )
    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json=payload)
            r.raise_for_status()
    except Exception:
        logger.exception("Failed to send manager review to webhook")
