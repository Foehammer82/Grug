"""Contextual auto-respond scoring for Grug.

Uses a lightweight LLM (claude-haiku) to decide whether Grug should respond
to a channel message when auto-respond mode is enabled.  The scorer returns a
float confidence between 0.0 and 1.0; the caller responds when the score
meets or exceeds the configured threshold.

Design principles:
- Errors are *non-disruptive*: any exception falls back to 0.0 (respond),
  so a misconfigured key or transient API failure never silences Grug.
- Fast path: if threshold == 0.0, callers should skip this function entirely
  and respond unconditionally.
"""

import json
import logging

from anthropic import AsyncAnthropic

from grug.config.settings import get_settings
from grug.llm_usage import CallType, record_llm_usage

logger = logging.getLogger(__name__)

_SCORER_SYSTEM = (
    "You are a relevance scorer deciding whether Grug — an AI assistant for "
    "TTRPG (tabletop role-playing game) Discord communities — should respond "
    "to a message.\n\n"
    "Grug SHOULD respond when the message:\n"
    "- Asks a question of any kind\n"
    "- Is about TTRPGs, gaming, rules, lore, character building, or scheduling\n"
    "- Invites discussion or opinion\n"
    "- Directly addresses the group ('anyone know…', 'what do you all think…')\n"
    "- Could benefit from an AI assistant's help\n\n"
    "Grug should NOT respond to:\n"
    "- Pure social chatter or inside jokes with no question or topic\n"
    "- Messages clearly between just two humans about an unrelated personal topic\n"
    "- One-word reactions or emoji-only messages\n\n"
    "Output ONLY a JSON object with a single key 'confidence' and a float value "
    "between 0.0 (definitely do not respond) and 1.0 (definitely respond). "
    'Example: {"confidence": 0.85}'
)


async def score_auto_respond(
    message_content: str,
    recent_context: list[str] | None = None,
    guild_id: int | None = None,
) -> float:
    """Score the probability (0.0–1.0) that Grug should respond to a message.

    Uses claude-haiku to assess whether the message warrants a response given
    the channel's context.  The caller should respond when:
    ``score >= channel_cfg.auto_respond_threshold``.

    Args:
        message_content: The clean text content of the incoming message.
        recent_context: Optional list of recent message strings (oldest first)
            for context — up to the last 5 are included in the prompt.
        guild_id: Discord guild ID used for LLM usage tracking only.

    Returns:
        A float from 0.0 to 1.0.  Errors always return 0.0 (respond) so that
        API failures are never silently disruptive.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.debug(
            "No Anthropic API key — auto-respond scoring skipped, defaulting respond"
        )
        return 0.0

    # Build the context block from the last 5 recent messages.
    context_block = ""
    if recent_context:
        snippet = "\n".join(recent_context[-5:])
        context_block = f"\n\nRecent channel context (last few messages):\n{snippet}\n"

    user_prompt = f"{context_block}\nMessage to score: {message_content}"

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=64,
            system=_SCORER_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        await record_llm_usage(
            model="claude-haiku-4-5",
            call_type=CallType.AUTO_RESPOND_SCORE,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            guild_id=guild_id,
        )
        text = response.content[0].text.strip()
        data = json.loads(text)
        confidence = float(data["confidence"])
        return max(0.0, min(1.0, confidence))
    except Exception:
        logger.exception(
            "Auto-respond scoring failed for guild %s; defaulting to respond", guild_id
        )
        return 0.0
