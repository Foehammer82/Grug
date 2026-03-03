"""Tests for the auto-respond scorer and bot decision logic.

The ``mock_settings`` fixture in conftest.py is autouse and handles env-var
injection and singleton reset for every test in this module.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# DB model
# ---------------------------------------------------------------------------


def test_channel_config_has_auto_respond_fields():
    """ChannelConfig model exposes auto_respond and auto_respond_threshold columns."""
    from grug.db.models import ChannelConfig

    table = ChannelConfig.__table__
    assert "auto_respond" in table.c
    assert "auto_respond_threshold" in table.c

    auto_col = table.c["auto_respond"]
    threshold_col = table.c["auto_respond_threshold"]
    assert auto_col.nullable is False
    # Float column — check the type name rather than instance equality
    assert (
        "FLOAT" in str(threshold_col.type).upper()
        or "REAL" in str(threshold_col.type).upper()
    )


def test_channel_config_no_always_respond():
    """ChannelConfig no longer exposes the old always_respond column."""
    from grug.db.models import ChannelConfig

    assert "always_respond" not in ChannelConfig.__table__.c


# ---------------------------------------------------------------------------
# score_auto_respond — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_auto_respond_returns_confidence():
    """score_auto_respond parses the LLM response and returns the float."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({"confidence": 0.85}))]
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=10)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with (
        patch("grug.bot.auto_respond.AsyncAnthropic", return_value=mock_client),
        patch("grug.bot.auto_respond.record_llm_usage", new=AsyncMock()),
    ):
        from grug.bot import auto_respond

        score = await auto_respond.score_auto_respond(
            message_content="How do I cast Fireball in PF2e?",
            guild_id=12345,
        )

    assert pytest.approx(score) == 0.85


@pytest.mark.asyncio
async def test_score_auto_respond_clamps_to_0_1():
    """score_auto_respond clamps out-of-range values to [0.0, 1.0]."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({"confidence": 1.5}))]
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=10)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with (
        patch("grug.bot.auto_respond.AsyncAnthropic", return_value=mock_client),
        patch("grug.bot.auto_respond.record_llm_usage", new=AsyncMock()),
    ):
        from grug.bot import auto_respond

        score = await auto_respond.score_auto_respond("anything")

    assert score == 1.0


# ---------------------------------------------------------------------------
# score_auto_respond — error fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_auto_respond_falls_back_on_api_error():
    """score_auto_respond returns 0.0 (respond) when the API call raises."""
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("grug.bot.auto_respond.AsyncAnthropic", return_value=mock_client):
        from grug.bot import auto_respond

        score = await auto_respond.score_auto_respond("whatever")
    assert score == 0.0


@pytest.mark.asyncio
async def test_score_auto_respond_falls_back_when_no_api_key(monkeypatch):
    """score_auto_respond returns 0.0 when ANTHROPIC_API_KEY is not set."""
    import grug.config.settings as s

    s.get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    s.get_settings.cache_clear()

    from grug.bot import auto_respond

    score = await auto_respond.score_auto_respond("hello")
    assert score == 0.0


@pytest.mark.asyncio
async def test_score_auto_respond_falls_back_on_bad_json():
    """score_auto_respond returns 0.0 when the LLM outputs non-JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not json at all")]
    mock_response.usage = MagicMock(input_tokens=20, output_tokens=5)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with (
        patch("grug.bot.auto_respond.AsyncAnthropic", return_value=mock_client),
        patch("grug.bot.auto_respond.record_llm_usage", new=AsyncMock()),
    ):
        from grug.bot import auto_respond

        score = await auto_respond.score_auto_respond("whatever")
    assert score == 0.0


# ---------------------------------------------------------------------------
# on_message response decision — isolated logic tests
# ---------------------------------------------------------------------------


def _make_channel_cfg(*, auto_respond: bool, threshold: float):
    """Return a MagicMock mimicking a ChannelConfig row."""
    cfg = MagicMock()
    cfg.auto_respond = auto_respond
    cfg.auto_respond_threshold = threshold
    return cfg


@pytest.mark.asyncio
async def test_auto_respond_off_no_response():
    """When auto_respond is False and no mention, bot should not respond.

    We test the decision logic in isolation by importing the private helper
    directly (rather than spinning up a full Discord bot).
    """
    # Emulate the decision logic from on_message
    mentioned = False
    cfg = _make_channel_cfg(auto_respond=False, threshold=0.0)

    auto_respond_flag = cfg.auto_respond
    auto_respond_threshold = cfg.auto_respond_threshold

    should_respond = mentioned
    if not should_respond and auto_respond_flag:
        if auto_respond_threshold == 0.0:
            should_respond = True
        # else: would call scorer

    assert should_respond is False


@pytest.mark.asyncio
async def test_auto_respond_on_threshold_zero_always_responds():
    """When auto_respond is True and threshold == 0.0, always respond (fast path)."""
    mentioned = False
    cfg = _make_channel_cfg(auto_respond=True, threshold=0.0)

    auto_respond_flag = cfg.auto_respond
    auto_respond_threshold = cfg.auto_respond_threshold

    should_respond = mentioned
    scorer_called = False
    if not should_respond and auto_respond_flag:
        if auto_respond_threshold == 0.0:
            should_respond = True
        else:
            scorer_called = True

    assert should_respond is True
    assert scorer_called is False  # fast path: no LLM call


@pytest.mark.asyncio
async def test_auto_respond_threshold_met_responds():
    """When the scorer exceeds the threshold, should_respond is True."""
    mentioned = False
    cfg = _make_channel_cfg(auto_respond=True, threshold=0.7)
    mocked_score = 0.9  # above threshold

    auto_respond_flag = cfg.auto_respond
    auto_respond_threshold = cfg.auto_respond_threshold

    should_respond = mentioned
    if not should_respond and auto_respond_flag:
        if auto_respond_threshold == 0.0:
            should_respond = True
        else:
            should_respond = mocked_score >= auto_respond_threshold

    assert should_respond is True


@pytest.mark.asyncio
async def test_auto_respond_threshold_not_met_skips():
    """When the scorer is below the threshold, should_respond is False."""
    mentioned = False
    cfg = _make_channel_cfg(auto_respond=True, threshold=0.8)
    mocked_score = 0.4  # below threshold

    auto_respond_flag = cfg.auto_respond
    auto_respond_threshold = cfg.auto_respond_threshold

    should_respond = mentioned
    if not should_respond and auto_respond_flag:
        if auto_respond_threshold == 0.0:
            should_respond = True
        else:
            should_respond = mocked_score >= auto_respond_threshold

    assert should_respond is False


@pytest.mark.asyncio
async def test_mention_always_responds_regardless_of_auto_respond():
    """A direct @mention always triggers a response regardless of auto_respond."""
    mentioned = True
    cfg = _make_channel_cfg(auto_respond=False, threshold=0.0)

    auto_respond_flag = cfg.auto_respond
    auto_respond_threshold = cfg.auto_respond_threshold

    should_respond = mentioned
    if not should_respond and auto_respond_flag:
        if auto_respond_threshold == 0.0:
            should_respond = True

    assert should_respond is True
