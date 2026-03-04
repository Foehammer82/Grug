"""Character sheet parser — handles PDF, DOCX, images, and plain text.

The parser extracts raw text from the uploaded file, then asks Claude to:
  1. Detect the game system (dnd5e, pf2e, or unknown / homebrew).
  2. Extract a structured JSON summary of the character.

Detected systems
----------------
- ``dnd5e``   — Dungeons & Dragons 5th Edition
- ``pf2e``    — Pathfinder 2nd Edition
- ``unknown`` — Any other system (homebrew, other published games, etc.)

When the system is unknown or homebrew, Grug stores whatever stats and fields
are present in the sheet and trusts the players to provide rule context.
"""

import base64
import json
import logging
from pathlib import Path

from grug.llm_usage import CallType, record_llm_usage

logger = logging.getLogger(__name__)

# Minimum character count from PDF text extraction before we fall back to
# sending the raw PDF bytes to Claude's native PDF understanding.
_PDF_TEXT_MIN_CHARS = 200

# Claude JSON extraction prompt.  The model fills in the fields it can detect
# and leaves everything else null so the schema stays flexible.
_EXTRACTION_PROMPT = """\
You are a TTRPG character sheet parser. Analyse the character sheet provided \
and extract its contents into structured JSON.

Rules:
1. Detect the game system. Use EXACTLY one of: "dnd5e", "pf2e", or "unknown".
   - Use "dnd5e" for D&D 5e and similar (D&D Next, One D&D).
   - Use "pf2e" for Pathfinder 2e.
   - Use "unknown" for any other system, homebrew, or when you cannot tell.
2. Return a single JSON object with these top-level keys (all optional/nullable):
   {
     "system": "<system string>",
     "name": "<character name>",
     "player_name": "<player name if present>",
     "level": <integer or null>,
     "class_and_subclass": "<class(es) and subclass(es)>",
     "race_or_ancestry": "<race / ancestry / species>",
     "background": "<background or concept>",
     "alignment": "<alignment if present>",
     "hp": {"current": <int or null>, "max": <int or null>, "temp": <int or null>},
     "ability_scores": {
       "STR": <int or null>, "DEX": <int or null>, "CON": <int or null>,
       "INT": <int or null>, "WIS": <int or null>, "CHA": <int or null>
     },
     "saving_throws": {},
     "skills": {},
     "armor_class": <int or null>,
     "speed": "<speed string>",
     "initiative": <int or null>,
     "proficiency_bonus": <int or null>,
     "attacks": [],
     "spells": [],
     "features_and_traits": [],
     "inventory": [],
     "currency": {},
     "languages": [],
     "notes": "<any free-form notes or backstory>",
     "extra": {}
   }
   Put system-specific fields that don't fit above into "extra".
3. Do NOT include any prose outside the JSON object.
"""


class CharacterSheetParser:
    """Parse an uploaded character sheet file and extract structured data.

    Parameters
    ----------
    anthropic_api_key:
        Key used to instantiate the Anthropic client for extraction.
    anthropic_model:
        Model name (default: claude-3-5-sonnet-20241022).
    """

    def __init__(
        self,
        anthropic_api_key: str,
        anthropic_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        self._api_key = anthropic_api_key
        self._model = anthropic_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def parse(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> tuple[str, dict, str]:
        """Parse a character sheet from raw bytes.

        Parameters
        ----------
        file_bytes:
            Raw file content.
        filename:
            Original filename (used to detect format by extension).

        Returns
        -------
        (raw_text, structured_data, detected_system)
        """
        ext = Path(filename).suffix.lower()
        raw_text, content_blocks = await self._extract_content(
            file_bytes, filename, ext
        )
        structured_data = await self._extract_structured(raw_text, content_blocks)
        detected_system = structured_data.get("system", "unknown") or "unknown"
        return raw_text, structured_data, detected_system

    # ------------------------------------------------------------------
    # Content extraction helpers
    # ------------------------------------------------------------------

    async def _extract_content(
        self,
        file_bytes: bytes,
        filename: str,
        ext: str,
    ) -> tuple[str, list[dict]]:
        """Return (raw_text, anthropic_content_blocks).

        Content blocks are ready to be dropped into a Claude messages payload.
        For plain text we use a single text block; for PDFs / images we may
        include base64-encoded media blocks so Claude can see the original.
        """
        if ext in {".txt", ".md", ".rst"}:
            raw_text = file_bytes.decode("utf-8", errors="replace")
            return raw_text, [{"type": "text", "text": raw_text}]

        if ext == ".pdf":
            return await self._extract_pdf(file_bytes)

        if ext in {".docx", ".doc"}:
            return self._extract_docx(file_bytes)

        if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            return self._extract_image(file_bytes, ext)

        # Fallback: treat as UTF-8 text
        raw_text = file_bytes.decode("utf-8", errors="replace")
        return raw_text, [{"type": "text", "text": raw_text}]

    async def _extract_pdf(self, file_bytes: bytes) -> tuple[str, list[dict]]:
        """Extract text from a PDF.  Falls back to native PDF API if sparse."""
        try:
            import io
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            raw_text = "\n".join(pages).strip()
        except Exception as exc:
            logger.warning(
                "pypdf extraction failed (%s), falling back to Claude PDF API", exc
            )
            raw_text = ""

        if len(raw_text) >= _PDF_TEXT_MIN_CHARS:
            # Good text extraction — just pass the text.
            return raw_text, [{"type": "text", "text": raw_text}]

        # Sparse / image-based PDF — send the raw bytes to Claude's PDF API.
        logger.info(
            "Short PDF text (%d chars), sending raw PDF to Claude", len(raw_text)
        )
        b64 = base64.standard_b64encode(file_bytes).decode()
        blocks = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            }
        ]
        return raw_text, blocks

    def _extract_docx(self, file_bytes: bytes) -> tuple[str, list[dict]]:
        """Extract text from a DOCX file."""
        try:
            import io
            from docx import Document as DocxDocument

            doc = DocxDocument(io.BytesIO(file_bytes))
            raw_text = "\n".join(
                para.text for para in doc.paragraphs if para.text.strip()
            )
        except Exception as exc:
            logger.warning("python-docx extraction failed: %s", exc)
            raw_text = ""
        return raw_text, [{"type": "text", "text": raw_text}]

    def _extract_image(self, file_bytes: bytes, ext: str) -> tuple[str, list[dict]]:
        """Prepare an image for Claude's vision API."""
        _mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        media_type = _mime_map.get(ext, "image/png")
        b64 = base64.standard_b64encode(file_bytes).decode()
        blocks = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            }
        ]
        return "", blocks

    # ------------------------------------------------------------------
    # Claude structured extraction
    # ------------------------------------------------------------------

    async def _extract_structured(
        self,
        raw_text: str,
        content_blocks: list[dict],
    ) -> dict:
        """Ask Claude to parse the sheet and return structured JSON."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        messages = [
            {
                "role": "user",
                "content": content_blocks
                + [{"type": "text", "text": _EXTRACTION_PROMPT}],
            }
        ]

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                messages=messages,
            )
            await record_llm_usage(
                model=self._model,
                call_type=CallType.CHARACTER_PARSE,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            raw_json = response.content[0].text.strip()
            # Strip markdown code fences if Claude wrapped the response.
            if raw_json.startswith("```"):
                raw_json = raw_json.split("```")[1]
                if raw_json.startswith("json"):
                    raw_json = raw_json[4:]
            return json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning("Claude returned non-JSON character data: %s", exc)
            return {"system": "unknown"}
        except Exception as exc:
            logger.exception("Claude character extraction failed: %s", exc)
            return {"system": "unknown"}
