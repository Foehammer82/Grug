"""LLM usage tracking — records token counts and estimates costs for every API call.

Usage is stored as daily aggregates keyed by (date, guild_id, user_id, model,
call_type).  This keeps the table compact for self-hosted deployments.

Costs are **estimated** from a hardcoded price table and recomputed at read time
so retroactive price corrections are free.  Unknown models show token counts
but no dollar amount.

Anthropic pricing reference (March 2026):
  https://www.anthropic.com/pricing
All prices are in USD per million tokens (MTok).
"""

from __future__ import annotations

import logging
from datetime import date
from enum import StrEnum
from typing import NamedTuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing — USD per 1 million tokens
# ---------------------------------------------------------------------------


class _ModelPrice(NamedTuple):
    input_per_mtok: float
    output_per_mtok: float


# Update this dict when Anthropic adjusts prices or when new models are added.
MODEL_PRICES: dict[str, _ModelPrice] = {
    # Claude 3.5 family
    "claude-3-5-sonnet-20241022": _ModelPrice(
        input_per_mtok=3.00, output_per_mtok=15.00
    ),
    "claude-3-5-haiku-20241022": _ModelPrice(input_per_mtok=0.80, output_per_mtok=4.00),
    # Claude 4 family
    "claude-haiku-4-5": _ModelPrice(input_per_mtok=0.80, output_per_mtok=4.00),
    "claude-sonnet-4-5": _ModelPrice(input_per_mtok=3.00, output_per_mtok=15.00),
    "claude-sonnet-4-6": _ModelPrice(input_per_mtok=3.00, output_per_mtok=15.00),
    "claude-opus-4-5": _ModelPrice(input_per_mtok=15.00, output_per_mtok=75.00),
}


def compute_estimated_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Return the estimated cost in USD, or ``None`` if the model is unknown."""
    price = MODEL_PRICES.get(model)
    if price is None:
        return None
    input_cost = (input_tokens / 1_000_000) * price.input_per_mtok
    output_cost = (output_tokens / 1_000_000) * price.output_per_mtok
    return round(input_cost + output_cost, 8)


# ---------------------------------------------------------------------------
# Call type enum
# ---------------------------------------------------------------------------


class CallType(StrEnum):
    """The feature that triggered the LLM API call."""

    CHAT = "chat"
    RULES_LOOKUP = "rules_lookup"
    HISTORY_ARCHIVE = "history_archive"
    CHARACTER_PARSE = "character_parse"
    CRON_PARSE = "cron_parse"


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


async def record_llm_usage(
    *,
    model: str,
    call_type: CallType | str,
    input_tokens: int,
    output_tokens: int,
    guild_id: int | None = None,
    user_id: int | None = None,
) -> None:
    """Upsert a daily aggregate row for this LLM call.

    This function is **fire-and-forget** — it catches and logs all exceptions
    so that tracking never disrupts the user-facing flow.

    Args:
        model: The exact model name as reported by the API (e.g. "claude-haiku-4-5").
        call_type: Which feature made the call (see :class:`CallType`).
        input_tokens: Number of input/prompt tokens consumed.
        output_tokens: Number of output/completion tokens consumed.
        guild_id: Discord guild snowflake, or ``None`` for DMs / background tasks.
        user_id: Discord user snowflake, or ``None`` for background tasks.
    """
    try:
        from sqlalchemy.dialects.postgresql import insert

        from grug.db.models import LLMUsageDailyAggregate
        from grug.db.session import get_session_factory

        today = date.today()
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                insert(LLMUsageDailyAggregate)
                .values(
                    date=today,
                    guild_id=guild_id,
                    user_id=user_id,
                    model=model,
                    call_type=str(call_type),
                    request_count=1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                .on_conflict_do_update(
                    constraint="uq_llm_usage_daily",
                    set_={
                        "request_count": LLMUsageDailyAggregate.request_count + 1,
                        "input_tokens": LLMUsageDailyAggregate.input_tokens
                        + input_tokens,
                        "output_tokens": LLMUsageDailyAggregate.output_tokens
                        + output_tokens,
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()
    except Exception:
        logger.exception(
            "Failed to record LLM usage — model=%s call_type=%s guild=%s user=%s",
            model,
            call_type,
            guild_id,
            user_id,
        )
