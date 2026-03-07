"""Tests for the manager agent feature — prompt rendering, review parsing, and API routes."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# System prompt (Jinja2) tests
# ---------------------------------------------------------------------------


class TestSystemPromptRendering:
    """Verify the Jinja2 system prompt renders correctly with various inputs."""

    def test_render_minimal(self):
        """Prompt renders with only required fields."""
        from grug.agent.prompt import render_system_prompt

        result = render_system_prompt(now="2026-03-07T12:00:00+00:00")
        assert "Grug" in result
        assert "2026-03-07T12:00:00+00:00" in result
        assert "CUSTOM SERVER INSTRUCTIONS" not in result

    def test_render_with_all_fields(self):
        """Prompt renders with all optional fields populated."""
        from grug.agent.prompt import render_system_prompt

        result = render_system_prompt(
            now="2026-03-07T12:00:00+00:00",
            default_ttrpg_system_line="This server uses PF2e",
            campaign_context_line="Campaign: Grug Quest\nSystem: pf2e",
            instruction_overrides="Never discuss potions in detail.",
        )
        assert "This server uses PF2e" in result
        assert "Campaign: Grug Quest" in result
        assert "CUSTOM SERVER INSTRUCTIONS" in result
        assert "Never discuss potions in detail." in result

    def test_render_without_overrides(self):
        """Empty instruction_overrides does not produce the custom section."""
        from grug.agent.prompt import render_system_prompt

        result = render_system_prompt(
            now="2026-03-07T12:00:00+00:00",
            instruction_overrides="",
        )
        assert "CUSTOM SERVER INSTRUCTIONS" not in result

    def test_render_core_sections_present(self):
        """All core prompt sections are present in the output."""
        from grug.agent.prompt import render_system_prompt

        result = render_system_prompt(now="2026-03-07T12:00:00+00:00")
        assert "VOICE RULES" in result
        assert "ALWAYS RESPOND TO ANY REQUEST" in result
        assert "TIME-DELAYED REQUESTS" in result
        assert "DICE ROLLING" in result
        assert "INITIATIVE AND ENCOUNTERS" in result
        assert "COMBAT TRACKING" in result
        assert "CHARACTER SHEETS AND PRIVACY" in result
        assert "RULE LOOKUPS" in result
        assert "SCHEDULED EXECUTION RULE" in result


# ---------------------------------------------------------------------------
# Review result parsing tests
# ---------------------------------------------------------------------------


class TestReviewResultParsing:
    """Verify the _parse_review_result function handles various formats."""

    def test_parse_valid_json(self):
        from grug.manager.reviewer import _parse_review_result

        raw = json.dumps(
            {
                "summary": "Grug doing great!",
                "observations": [
                    {
                        "category": "voice",
                        "severity": "info",
                        "detail": "Consistent orc voice",
                    }
                ],
                "recommendations": [],
            }
        )
        result = _parse_review_result(raw)
        assert result.summary == "Grug doing great!"
        assert len(result.observations) == 1
        assert result.observations[0]["category"] == "voice"
        assert result.recommendations == []

    def test_parse_json_in_code_block(self):
        from grug.manager.reviewer import _parse_review_result

        raw = '```json\n{"summary": "Good", "observations": [], "recommendations": []}\n```'
        result = _parse_review_result(raw)
        assert result.summary == "Good"

    def test_parse_invalid_json_fallback(self):
        from grug.manager.reviewer import _parse_review_result

        raw = "This is not JSON at all. Grug is doing fine."
        result = _parse_review_result(raw)
        assert result.summary == raw
        assert result.observations == []
        assert result.recommendations == []

    def test_parse_empty_observations(self):
        from grug.manager.reviewer import _parse_review_result

        raw = json.dumps(
            {
                "summary": "All clear",
                "observations": [],
                "recommendations": [],
            }
        )
        result = _parse_review_result(raw)
        assert result.summary == "All clear"
        assert result.observations == []

    def test_parse_with_recommendations(self):
        from grug.manager.reviewer import _parse_review_result

        raw = json.dumps(
            {
                "summary": "Some issues found",
                "observations": [],
                "recommendations": [
                    {
                        "action": "add",
                        "content": "Always greet with 'Grug!'",
                        "reason": "Users expect a greeting",
                    }
                ],
            }
        )
        result = _parse_review_result(raw)
        assert len(result.recommendations) == 1
        assert result.recommendations[0]["action"] == "add"


# ---------------------------------------------------------------------------
# Message/feedback formatting tests
# ---------------------------------------------------------------------------


class TestFormatters:
    """Test the helper functions that format data for the LLM prompt."""

    def test_format_messages_empty(self):
        from grug.manager.reviewer import _format_messages

        assert _format_messages([]) == "(no messages)"

    def test_format_messages_with_data(self):
        from grug.manager.reviewer import _format_messages

        msg = MagicMock()
        msg.created_at = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        msg.author_name = "Blake"
        msg.role = "user"
        msg.content = "Hey Grug!"
        result = _format_messages([msg])
        assert "Blake" in result
        assert "Hey Grug!" in result

    def test_format_messages_assistant(self):
        from grug.manager.reviewer import _format_messages

        msg = MagicMock()
        msg.created_at = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        msg.author_name = None
        msg.role = "assistant"
        msg.content = "Grug here!"
        result = _format_messages([msg])
        assert "GRUG" in result
        assert "Grug here!" in result

    def test_format_feedback_empty(self):
        from grug.manager.reviewer import _format_feedback

        assert _format_feedback([]) == "(no feedback)"

    def test_format_feedback_with_data(self):
        from grug.manager.reviewer import _format_feedback

        fb = MagicMock()
        fb.rating = 1
        fb.message_id = 42
        fb.comment = "Great joke!"
        result = _format_feedback([fb])
        assert "👍" in result
        assert "42" in result
        assert "Great joke!" in result

    def test_format_feedback_negative(self):
        from grug.manager.reviewer import _format_feedback

        fb = MagicMock()
        fb.rating = -1
        fb.message_id = 99
        fb.comment = None
        result = _format_feedback([fb])
        assert "👎" in result


# ---------------------------------------------------------------------------
# DB model instantiation tests
# ---------------------------------------------------------------------------


class TestManagerModels:
    """Verify the new ORM models can be instantiated with expected defaults."""

    def test_user_feedback_defaults(self):
        from grug.db.models import UserFeedback

        fb = UserFeedback(
            guild_id=123,
            channel_id=456,
            message_id=789,
            discord_user_id=111,
            rating=1,
        )
        assert fb.guild_id == 123
        assert fb.rating == 1
        assert fb.comment is None

    def test_instruction_override_defaults(self):
        from grug.db.models import InstructionOverride

        override = InstructionOverride(
            guild_id=123,
            content="Extra instruction",
            scope="guild",
            status="active",
            source="admin",
            created_by=111,
        )
        assert override.scope == "guild"
        assert override.status == "active"
        assert override.source == "admin"
        assert override.channel_id is None
        assert override.review_id is None

    def test_manager_review_defaults(self):
        from grug.db.models import ManagerReview

        review = ManagerReview(guild_id=123, status="pending")
        assert review.status == "pending"
        assert review.summary is None
        assert review.observations is None
        assert review.recommendations is None
        assert review.error is None


# ---------------------------------------------------------------------------
# CallType enum tests
# ---------------------------------------------------------------------------


class TestCallType:
    """Verify MANAGER_REVIEW is in the CallType enum."""

    def test_manager_review_in_enum(self):
        from grug.llm_usage import CallType

        assert CallType.MANAGER_REVIEW == "manager_review"
        assert "MANAGER_REVIEW" in CallType.__members__


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


class TestManagerSettings:
    """Verify manager settings have correct defaults."""

    def test_defaults(self):
        from grug.config.settings import get_settings

        settings = get_settings()
        assert settings.manager_webhook_url == ""
        assert settings.manager_review_cron == "0 6 * * 1"
        assert settings.manager_review_enabled is False


# ---------------------------------------------------------------------------
# Webhook sender tests
# ---------------------------------------------------------------------------


class TestWebhookSender:
    """Test the Discord webhook sender."""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self):
        from grug.manager.reviewer import ReviewResult, _send_webhook

        result = ReviewResult(
            summary="All good!",
            observations=[
                {
                    "category": "voice",
                    "severity": "info",
                    "detail": "Consistent orc talk",
                }
            ],
            recommendations=[],
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _send_webhook(
                "https://discord.com/api/webhooks/123/abc", 999, result
            )

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://discord.com/api/webhooks/123/abc"
            payload = call_args[1]["json"]
            assert "embeds" in payload
            assert payload["embeds"][0]["title"] == "📋 Grug Manager Review"

    @pytest.mark.asyncio
    async def test_send_webhook_failure_logged(self):
        from grug.manager.reviewer import ReviewResult, _send_webhook

        result = ReviewResult(summary="Test")
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Should not raise — errors are logged
            await _send_webhook("https://example.com/webhook", 999, result)
