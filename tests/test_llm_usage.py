"""Tests for grug.llm_usage — price table, cost computation, and usage recording."""

import pytest
from unittest.mock import patch

from grug.llm_usage import (
    CallType,
    MODEL_PRICES,
    compute_estimated_cost,
    record_llm_usage,
)


# ---------------------------------------------------------------------------
# compute_estimated_cost
# ---------------------------------------------------------------------------


def test_compute_cost_known_model_haiku():
    """claude-haiku-4-5 has a defined price; cost should be correct to 8 decimal places."""
    cost = compute_estimated_cost(
        "claude-haiku-4-5", input_tokens=1_000_000, output_tokens=1_000_000
    )
    price = MODEL_PRICES["claude-haiku-4-5"]
    expected = round(price.input_per_mtok + price.output_per_mtok, 8)
    assert cost == pytest.approx(expected, rel=1e-6)


def test_compute_cost_known_model_sonnet():
    cost = compute_estimated_cost(
        "claude-sonnet-4-6", input_tokens=500_000, output_tokens=250_000
    )
    price = MODEL_PRICES["claude-sonnet-4-6"]
    expected = round((0.5 * price.input_per_mtok) + (0.25 * price.output_per_mtok), 8)
    assert cost == pytest.approx(expected, rel=1e-6)


def test_compute_cost_unknown_model_returns_none():
    assert compute_estimated_cost("gpt-99-turbo", 10_000, 5_000) is None


def test_compute_cost_zero_tokens():
    cost = compute_estimated_cost("claude-haiku-4-5", 0, 0)
    assert cost == 0.0


def test_model_prices_dict_has_sensible_values():
    for model, price in MODEL_PRICES.items():
        assert price.input_per_mtok > 0, f"{model} input price must be positive"
        assert price.output_per_mtok >= price.input_per_mtok, (
            f"{model}: output price should be >= input price (output is typically more expensive)"
        )


# ---------------------------------------------------------------------------
# CallType
# ---------------------------------------------------------------------------


def test_call_type_string_values():
    assert str(CallType.CHAT) == "chat"
    assert str(CallType.RULES_LOOKUP) == "rules_lookup"
    assert str(CallType.HISTORY_ARCHIVE) == "history_archive"
    assert str(CallType.CHARACTER_PARSE) == "character_parse"
    assert str(CallType.CRON_PARSE) == "cron_parse"


# ---------------------------------------------------------------------------
# record_llm_usage — happy path upsert
# ---------------------------------------------------------------------------


async def test_record_llm_usage_inserts_row(mock_db_session):
    """record_llm_usage should execute an upsert + raw record insert + prune and commit."""
    mock_factory, mock_session = mock_db_session

    with patch("grug.db.session.get_session_factory", return_value=mock_factory):
        await record_llm_usage(
            model="claude-haiku-4-5",
            call_type=CallType.CHAT,
            input_tokens=1000,
            output_tokens=500,
            guild_id=123456789,
            user_id=987654321,
        )

    # 1) daily aggregate upsert, 2) raw record insert, 3) prune old records
    assert mock_session.execute.call_count == 3
    mock_session.commit.assert_called_once()


async def test_record_llm_usage_nullable_guild_user(mock_db_session):
    """record_llm_usage should work with null guild_id and user_id (background tasks)."""
    mock_factory, mock_session = mock_db_session

    with patch("grug.db.session.get_session_factory", return_value=mock_factory):
        await record_llm_usage(
            model="claude-sonnet-4-6",
            call_type=CallType.HISTORY_ARCHIVE,
            input_tokens=2000,
            output_tokens=400,
        )

    # 1) daily aggregate upsert, 2) raw record insert, 3) prune old records
    assert mock_session.execute.call_count == 3
    mock_session.commit.assert_called_once()


async def test_record_llm_usage_swallows_db_errors(mock_db_session, caplog):
    """A DB error in record_llm_usage must not propagate — it is fire-and-forget."""
    mock_factory, mock_session = mock_db_session
    mock_session.execute.side_effect = RuntimeError("DB exploded")

    with patch("grug.db.session.get_session_factory", return_value=mock_factory):
        # Should not raise
        await record_llm_usage(
            model="claude-haiku-4-5",
            call_type=CallType.CRON_PARSE,
            input_tokens=100,
            output_tokens=50,
        )

    assert "Failed to record LLM usage" in caplog.text
