"""Admin usage endpoints — LLM token usage and estimated cost tracking.

All endpoints are restricted to Grug super-admins.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_super_admin, get_current_user, get_db
from grug.config.settings import get_settings
from grug.db.models import LLMUsageDailyAggregate, LLMUsageRecord
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


class ChartPointOut(BaseModel):
    """A single bucketed usage point for the preset chart (hourly/daily/weekly)."""

    label: str
    """ISO-format bucket label: hour (``2026-03-03T14:00``), date (``2026-03-03``), or week-start date."""
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


# ---------------------------------------------------------------------------
# Chart points endpoint — preset-aware bucketed data
# ---------------------------------------------------------------------------

_PRESET = {"1d", "7d", "1m", "1y", "custom"}


@router.get("/api/admin/usage/points", response_model=list[ChartPointOut])
async def get_usage_points(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    preset: str = Query(default="1m"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    guild_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
) -> list[ChartPointOut]:
    """Return bucketed usage points for the bar chart.

    ``preset`` controls both the time range and the bucket size:

    - ``1d``     — last 24 h, one point per hour (from ``llm_usage_records``)
    - ``7d``     — last 7 days, one point per day
    - ``1m``     — last 30 days, one point per day (default)
    - ``1y``     — last 52 weeks, one point per week
    - ``custom`` — ``start_date``/``end_date`` range, one point per day
    """
    await assert_super_admin(user)

    today = _today()
    now_utc = datetime.now(timezone.utc)

    # ── 1d: hourly from raw records ─────────────────────────────────────────
    if preset == "1d":
        cutoff = now_utc - timedelta(hours=24)
        filters = [LLMUsageRecord.created_at >= cutoff]
        if guild_id is not None:
            filters.append(LLMUsageRecord.guild_id == guild_id)
        if user_id is not None:
            filters.append(LLMUsageRecord.user_id == user_id)

        hour_trunc = func.date_trunc("hour", LLMUsageRecord.created_at)
        result = await db.execute(
            select(
                hour_trunc.label("hour"),
                LLMUsageRecord.model,
                func.count().label("request_count"),
                func.sum(LLMUsageRecord.input_tokens).label("input_tokens"),
                func.sum(LLMUsageRecord.output_tokens).label("output_tokens"),
            )
            .where(*filters)
            .group_by(hour_trunc, LLMUsageRecord.model)
            .order_by(hour_trunc)
        )
        rows = result.all()

        # Accumulate by hour key
        hourly: dict[str, dict] = defaultdict(
            lambda: {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_parts": [],
            }
        )
        for row in rows:
            key = row.hour.strftime("%Y-%m-%dT%H:00")
            hourly[key]["request_count"] += int(row.request_count)
            hourly[key]["input_tokens"] += int(row.input_tokens)
            hourly[key]["output_tokens"] += int(row.output_tokens)
            cost = compute_estimated_cost(
                row.model, int(row.input_tokens), int(row.output_tokens)
            )
            if cost is not None:
                hourly[key]["cost_parts"].append(cost)

        # Fill all 24 hour slots (23h ago → now) so the chart is always complete.
        # Labels use the server's configured default timezone so times are not
        # confusingly shown as UTC to the admin.
        settings = get_settings()
        try:
            display_tz = ZoneInfo(settings.default_timezone)
        except (ZoneInfoNotFoundError, Exception):
            display_tz = timezone.utc  # type: ignore[assignment]

        points_out: list[ChartPointOut] = []
        for i in range(23, -1, -1):
            slot = (now_utc - timedelta(hours=i)).replace(
                minute=0, second=0, microsecond=0
            )
            key = slot.strftime("%Y-%m-%dT%H:00")
            d = hourly.get(
                key,
                {
                    "request_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_parts": [],
                },
            )
            local_slot = slot.astimezone(display_tz)
            points_out.append(
                ChartPointOut(
                    label=local_slot.strftime("%H:%M"),
                    request_count=d["request_count"],
                    input_tokens=d["input_tokens"],
                    output_tokens=d["output_tokens"],
                    estimated_cost_usd=round(sum(d["cost_parts"]), 6)
                    if d["cost_parts"]
                    else None,
                )
            )
        return points_out

    # ── Determine date range for day/week presets ───────────────────────────
    if preset == "7d":
        start, end = today - timedelta(days=6), today
    elif preset == "1y":
        start, end = today - timedelta(days=364), today
    else:  # "1m" or "custom" (fallback)
        start = start_date or today - timedelta(days=29)
        end = end_date or today

    base_filters = [
        LLMUsageDailyAggregate.date >= start,
        LLMUsageDailyAggregate.date <= end,
    ]
    if guild_id is not None:
        base_filters.append(LLMUsageDailyAggregate.guild_id == guild_id)
    if user_id is not None:
        base_filters.append(LLMUsageDailyAggregate.user_id == user_id)

    # ── 1y: weekly buckets ──────────────────────────────────────────────────
    if preset == "1y":
        from sqlalchemy import DateTime as SADateTime, cast

        week_trunc = func.date_trunc(
            "week", cast(LLMUsageDailyAggregate.date, SADateTime)
        )
        result = await db.execute(
            select(
                week_trunc.label("week"),
                LLMUsageDailyAggregate.model,
                func.sum(LLMUsageDailyAggregate.request_count).label("request_count"),
                func.sum(LLMUsageDailyAggregate.input_tokens).label("input_tokens"),
                func.sum(LLMUsageDailyAggregate.output_tokens).label("output_tokens"),
            )
            .where(*base_filters)
            .group_by(week_trunc, LLMUsageDailyAggregate.model)
            .order_by(week_trunc)
        )
        rows = result.all()

        weekly: dict[str, dict] = defaultdict(
            lambda: {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_parts": [],
            }
        )
        for row in rows:
            key = (
                row.week.strftime("%Y-%m-%d")
                if hasattr(row.week, "strftime")
                else str(row.week)[:10]
            )
            weekly[key]["request_count"] += int(row.request_count)
            weekly[key]["input_tokens"] += int(row.input_tokens)
            weekly[key]["output_tokens"] += int(row.output_tokens)
            cost = compute_estimated_cost(
                row.model, int(row.input_tokens), int(row.output_tokens)
            )
            if cost is not None:
                weekly[key]["cost_parts"].append(cost)

        # Zero-fill all ISO weeks in the range
        # Walk from start's Monday to end's Monday in 7-day steps
        def _week_start(d: date) -> date:
            return d - timedelta(days=d.weekday())

        all_weeks: list[str] = []
        cursor = _week_start(start)
        week_end = _week_start(end)
        while cursor <= week_end:
            all_weeks.append(cursor.isoformat())
            cursor += timedelta(weeks=1)

        return [
            ChartPointOut(
                label=w,
                request_count=weekly[w]["request_count"],
                input_tokens=weekly[w]["input_tokens"],
                output_tokens=weekly[w]["output_tokens"],
                estimated_cost_usd=round(sum(weekly[w]["cost_parts"]), 6)
                if weekly[w]["cost_parts"]
                else None,
            )
            for w in all_weeks
        ]

    # ── Daily buckets (7d / 1m / custom) ────────────────────────────────────
    result = await db.execute(
        select(
            LLMUsageDailyAggregate.date,
            LLMUsageDailyAggregate.model,
            func.sum(LLMUsageDailyAggregate.request_count).label("request_count"),
            func.sum(LLMUsageDailyAggregate.input_tokens).label("input_tokens"),
            func.sum(LLMUsageDailyAggregate.output_tokens).label("output_tokens"),
        )
        .where(*base_filters)
        .group_by(LLMUsageDailyAggregate.date, LLMUsageDailyAggregate.model)
        .order_by(LLMUsageDailyAggregate.date)
    )
    rows = result.all()

    daily_buckets: dict[str, dict] = defaultdict(
        lambda: {
            "request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_parts": [],
        }
    )
    for row in rows:
        key = str(row.date)
        daily_buckets[key]["request_count"] += int(row.request_count)
        daily_buckets[key]["input_tokens"] += int(row.input_tokens)
        daily_buckets[key]["output_tokens"] += int(row.output_tokens)
        cost = compute_estimated_cost(
            row.model, int(row.input_tokens), int(row.output_tokens)
        )
        if cost is not None:
            daily_buckets[key]["cost_parts"].append(cost)

    # Zero-fill every day in the range so the chart has the correct shape
    day_count = (end - start).days + 1
    all_days = [(start + timedelta(days=i)).isoformat() for i in range(day_count)]
    return [
        ChartPointOut(
            label=key,
            request_count=daily_buckets[key]["request_count"],
            input_tokens=daily_buckets[key]["input_tokens"],
            output_tokens=daily_buckets[key]["output_tokens"],
            estimated_cost_usd=round(sum(daily_buckets[key]["cost_parts"]), 6)
            if daily_buckets[key]["cost_parts"]
            else None,
        )
        for key in all_days
    ]
