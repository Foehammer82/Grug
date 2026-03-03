"""Admin usage endpoints — LLM token usage and estimated cost tracking.

All endpoints are restricted to Grug super-admins.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_super_admin, get_current_user, get_db
from grug.db.models import LLMUsageDailyAggregate
from grug.llm_usage import MODEL_PRICES, compute_estimated_cost

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ModelPriceOut(BaseModel):
    model: str
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None
    known: bool


class UsageRowOut(BaseModel):
    """A single aggregated usage row as returned by the summary and daily endpoints."""

    model: str
    call_type: str
    request_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    """``None`` when the model is not in the price table."""


class UsageSummaryOut(BaseModel):
    """Overall totals and breakdowns for a date range."""

    start_date: date
    end_date: date
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float | None
    """``None`` when any contributing model is unknown (partial estimates omitted for accuracy)."""
    cost_is_partial: bool
    """True when some tokens had unknown pricing; total_estimated_cost_usd reflects only known models."""
    by_model: list[UsageRowOut]
    by_call_type: list[UsageRowOut]


class DailyUsagePointOut(BaseModel):
    """A single day's aggregated usage for chart rendering."""

    date: date
    request_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _aggregate_cost(rows: list) -> tuple[float | None, bool]:
    """Return (total_estimated_cost_usd, cost_is_partial) from a list of rows.

    If ALL models are known: sum costs, cost_is_partial=False.
    If SOME models are unknown: sum known costs, cost_is_partial=True.
    If ALL models are unknown: return (None, True).

    ``rows`` are expected to have .model, .input_tokens, .output_tokens attrs.
    """
    total = 0.0
    has_unknown = False
    has_known = False
    for row in rows:
        cost = compute_estimated_cost(row.model, row.input_tokens, row.output_tokens)
        if cost is None:
            has_unknown = True
        else:
            total += cost
            has_known = True
    if not has_known:
        return None, True
    return round(total, 6), has_unknown


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/usage/models", response_model=list[ModelPriceOut])
async def list_usage_models(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ModelPriceOut]:
    """Return every distinct model seen in usage records, with price-table info."""
    await assert_super_admin(user)

    result = await db.execute(
        select(LLMUsageDailyAggregate.model)
        .distinct()
        .order_by(LLMUsageDailyAggregate.model)
    )
    seen_models = result.scalars().all()

    out: list[ModelPriceOut] = []
    for model_name in seen_models:
        price = MODEL_PRICES.get(model_name)
        out.append(
            ModelPriceOut(
                model=model_name,
                input_per_mtok=price.input_per_mtok if price else None,
                output_per_mtok=price.output_per_mtok if price else None,
                known=price is not None,
            )
        )
    return out


@router.get("/api/admin/usage/summary", response_model=UsageSummaryOut)
async def get_usage_summary(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    guild_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
) -> UsageSummaryOut:
    """Return aggregated usage totals broken down by model and call type.

    Defaults to the current calendar month when no date range is specified.
    """
    await assert_super_admin(user)

    today = _today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = today.replace(day=1)  # current month start

    base_filters = [
        LLMUsageDailyAggregate.date >= start_date,
        LLMUsageDailyAggregate.date <= end_date,
    ]
    if guild_id is not None:
        base_filters.append(LLMUsageDailyAggregate.guild_id == guild_id)
    if user_id is not None:
        base_filters.append(LLMUsageDailyAggregate.user_id == user_id)

    # ── By-model breakdown ──────────────────────────────────────────────────
    by_model_result = await db.execute(
        select(
            LLMUsageDailyAggregate.model,
            func.sum(LLMUsageDailyAggregate.request_count).label("request_count"),
            func.sum(LLMUsageDailyAggregate.input_tokens).label("input_tokens"),
            func.sum(LLMUsageDailyAggregate.output_tokens).label("output_tokens"),
        )
        .where(*base_filters)
        .group_by(LLMUsageDailyAggregate.model)
        .order_by(LLMUsageDailyAggregate.model)
    )
    by_model_rows = by_model_result.all()

    by_model_out = [
        UsageRowOut(
            model=r.model,
            call_type="",
            request_count=r.request_count,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            estimated_cost_usd=compute_estimated_cost(
                r.model, r.input_tokens, r.output_tokens
            ),
        )
        for r in by_model_rows
    ]

    # ── By-call-type breakdown ──────────────────────────────────────────────
    by_type_result = await db.execute(
        select(
            LLMUsageDailyAggregate.call_type,
            LLMUsageDailyAggregate.model,
            func.sum(LLMUsageDailyAggregate.request_count).label("request_count"),
            func.sum(LLMUsageDailyAggregate.input_tokens).label("input_tokens"),
            func.sum(LLMUsageDailyAggregate.output_tokens).label("output_tokens"),
        )
        .where(*base_filters)
        .group_by(LLMUsageDailyAggregate.call_type, LLMUsageDailyAggregate.model)
        .order_by(LLMUsageDailyAggregate.call_type, LLMUsageDailyAggregate.model)
    )
    by_type_rows = by_type_result.all()

    by_call_type_out = [
        UsageRowOut(
            model=r.model,
            call_type=r.call_type,
            request_count=r.request_count,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            estimated_cost_usd=compute_estimated_cost(
                r.model, r.input_tokens, r.output_tokens
            ),
        )
        for r in by_type_rows
    ]

    # ── Overall totals ──────────────────────────────────────────────────────
    total_estimated_cost, cost_is_partial = _aggregate_cost(by_model_rows)

    return UsageSummaryOut(
        start_date=start_date,
        end_date=end_date,
        total_requests=sum(r.request_count for r in by_model_rows),
        total_input_tokens=sum(r.input_tokens for r in by_model_rows),
        total_output_tokens=sum(r.output_tokens for r in by_model_rows),
        total_estimated_cost_usd=total_estimated_cost,
        cost_is_partial=cost_is_partial,
        by_model=by_model_out,
        by_call_type=by_call_type_out,
    )


@router.get("/api/admin/usage/daily", response_model=list[DailyUsagePointOut])
async def get_usage_daily(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    guild_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
) -> list[DailyUsagePointOut]:
    """Return per-day token totals over the requested date range for chart rendering.

    Defaults to the last 30 days when no range is specified.
    """
    await assert_super_admin(user)

    today = _today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = today - timedelta(days=29)

    filters = [
        LLMUsageDailyAggregate.date >= start_date,
        LLMUsageDailyAggregate.date <= end_date,
    ]
    if guild_id is not None:
        filters.append(LLMUsageDailyAggregate.guild_id == guild_id)
    if user_id is not None:
        filters.append(LLMUsageDailyAggregate.user_id == user_id)

    result = await db.execute(
        select(
            LLMUsageDailyAggregate.date,
            LLMUsageDailyAggregate.model,
            func.sum(LLMUsageDailyAggregate.request_count).label("request_count"),
            func.sum(LLMUsageDailyAggregate.input_tokens).label("input_tokens"),
            func.sum(LLMUsageDailyAggregate.output_tokens).label("output_tokens"),
        )
        .where(*filters)
        .group_by(LLMUsageDailyAggregate.date, LLMUsageDailyAggregate.model)
        .order_by(LLMUsageDailyAggregate.date)
    )
    all_rows = result.all()

    # Re-aggregate by date (we need model for cost calc, then roll up to day)
    from collections import defaultdict

    daily: dict[date, dict] = defaultdict(
        lambda: {
            "request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_parts": [],
        }
    )
    for row in all_rows:
        d = row.date
        daily[d]["request_count"] += row.request_count
        daily[d]["input_tokens"] += row.input_tokens
        daily[d]["output_tokens"] += row.output_tokens
        cost = compute_estimated_cost(row.model, row.input_tokens, row.output_tokens)
        if cost is not None:
            daily[d]["cost_parts"].append(cost)

    points: list[DailyUsagePointOut] = []
    for day_date in sorted(daily):
        d = daily[day_date]
        estimated_cost = round(sum(d["cost_parts"]), 6) if d["cost_parts"] else None
        points.append(
            DailyUsagePointOut(
                date=day_date,
                request_count=d["request_count"],
                input_tokens=d["input_tokens"],
                output_tokens=d["output_tokens"],
                estimated_cost_usd=estimated_cost,
            )
        )
    return points
