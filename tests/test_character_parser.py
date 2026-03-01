"""Tests for the character sheet parser."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grug.character.parser import CharacterSheetParser


@pytest.fixture()
def parser() -> CharacterSheetParser:
    return CharacterSheetParser(
        anthropic_api_key="test-key",
        anthropic_model="claude-3-5-sonnet-20241022",
    )


def _make_claude_response(json_data: dict) -> MagicMock:
    """Build a mock Anthropic API response containing JSON."""
    content_block = MagicMock()
    content_block.text = json.dumps(json_data)
    response = MagicMock()
    response.content = [content_block]
    return response


# ---------------------------------------------------------------------------
# Text / Markdown extraction
# ---------------------------------------------------------------------------


async def test_parse_plain_text_dnd5e(parser: CharacterSheetParser) -> None:
    """Plain text sheets are passed straight through as a text block."""
    sheet_text = "Name: Thogar\nClass: Fighter 5\nSTR: 18"
    expected_structured = {
        "system": "dnd5e",
        "name": "Thogar",
        "level": 5,
        "class_and_subclass": "Fighter",
        "ability_scores": {"STR": 18},
    }
    mock_response = _make_claude_response(expected_structured)

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        raw_text, structured, system = await parser.parse(
            sheet_text.encode(), "thogar.txt"
        )

    assert raw_text == sheet_text
    assert system == "dnd5e"
    assert structured["name"] == "Thogar"


async def test_parse_plain_text_pf2e(parser: CharacterSheetParser) -> None:
    """PF2e sheets are correctly identified."""
    sheet_text = "Character: Seraphina\nClass: Investigator\nLevel: 3"
    expected_structured = {"system": "pf2e", "name": "Seraphina", "level": 3}
    mock_response = _make_claude_response(expected_structured)

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        _, structured, system = await parser.parse(sheet_text.encode(), "seraphina.md")

    assert system == "pf2e"
    assert structured["level"] == 3


async def test_parse_unknown_homebrew_system(parser: CharacterSheetParser) -> None:
    """Homebrew / unrecognised systems map to 'unknown'."""
    sheet_text = "Character: Zyx\nSystem: Homebrew Dungeon World\nLevel: 2"
    expected_structured = {"system": "unknown", "name": "Zyx"}
    mock_response = _make_claude_response(expected_structured)

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        _, structured, system = await parser.parse(sheet_text.encode(), "zyx.txt")

    assert system == "unknown"


# ---------------------------------------------------------------------------
# PDF extraction fallback
# ---------------------------------------------------------------------------


async def test_parse_pdf_with_good_text_extraction(
    parser: CharacterSheetParser,
) -> None:
    """When pypdf extracts enough text, the raw PDF is NOT sent to Claude."""
    rich_text = "A" * 300  # above the 200-char threshold
    expected_structured = {"system": "dnd5e", "name": "PDFchar"}
    mock_response = _make_claude_response(expected_structured)

    # Mock pypdf so it returns rich text.
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = rich_text
    mock_reader.pages = [mock_page]

    with (
        patch("pypdf.PdfReader", return_value=mock_reader),
        patch("anthropic.AsyncAnthropic") as mock_anthropic,
    ):
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        raw_text, structured, system = await parser.parse(b"%PDF-stub", "sheet.pdf")

    assert raw_text == rich_text
    # The content block sent to Claude should be a plain text block, not a document block.
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    content_blocks = messages[0]["content"]
    assert any(b["type"] == "text" for b in content_blocks)
    assert not any(b["type"] == "document" for b in content_blocks)


async def test_parse_pdf_sparse_falls_back_to_native_pdf(
    parser: CharacterSheetParser,
) -> None:
    """When pypdf returns less than threshold text, the raw PDF bytes go to Claude."""
    sparse_text = "A few chars"
    expected_structured = {"system": "dnd5e", "name": "ScanChar"}
    mock_response = _make_claude_response(expected_structured)

    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = sparse_text
    mock_reader.pages = [mock_page]

    with (
        patch("pypdf.PdfReader", return_value=mock_reader),
        patch("anthropic.AsyncAnthropic") as mock_anthropic,
    ):
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        raw_text, structured, system = await parser.parse(b"%PDF-scan", "scanned.pdf")

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    content_blocks = messages[0]["content"]
    assert any(b["type"] == "document" for b in content_blocks)


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------


async def test_parse_image_sheet(parser: CharacterSheetParser) -> None:
    """PNG sheets are sent as image blocks to Claude's vision API."""
    fake_png = b"\x89PNG\r\n"
    expected_structured = {"system": "dnd5e", "name": "Arthas"}
    mock_response = _make_claude_response(expected_structured)

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        raw_text, structured, system = await parser.parse(fake_png, "sheet.png")

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    content_blocks = messages[0]["content"]
    assert any(b["type"] == "image" for b in content_blocks)
    assert system == "dnd5e"


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


async def test_parse_non_json_claude_response_returns_unknown(
    parser: CharacterSheetParser,
) -> None:
    """If Claude returns non-JSON, the parser returns system='unknown' gracefully."""
    content_block = MagicMock()
    content_block.text = "Sorry, I cannot parse this."
    mock_response = MagicMock()
    mock_response.content = [content_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        _, structured, system = await parser.parse(b"data", "mystery.txt")

    assert system == "unknown"
    assert structured == {"system": "unknown"}


async def test_parse_claude_api_failure_returns_unknown(
    parser: CharacterSheetParser,
) -> None:
    """If the Anthropic call raises, the parser returns system='unknown' gracefully."""
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))

        _, structured, system = await parser.parse(b"data", "sheet.txt")

    assert system == "unknown"
