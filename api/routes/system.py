"""System / public info routes — no auth required."""

import logging

import httpx
from fastapi import APIRouter

from api.schemas import BotInfoOut, DefaultsOut
from grug.config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/api/defaults", response_model=DefaultsOut)
async def get_defaults() -> DefaultsOut:
    """Return server-wide defaults that the web UI can use as fallback values."""
    settings = get_settings()
    return DefaultsOut(default_timezone=settings.default_timezone)


@router.get("/api/bot-info", response_model=BotInfoOut)
async def get_bot_info() -> BotInfoOut:
    """Return the Discord bot's profile — username and avatar URL.

    Used by the web UI to display the bot's actual Discord profile picture
    instead of the bundled placeholder image.  No user auth required.
    Falls back gracefully if the Discord API is unreachable.
    """
    settings = get_settings()
    bot_token = settings.discord_bot_token or settings.discord_token
    if not bot_token:
        return BotInfoOut(id="", username="Grug", avatar_url=None)

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {bot_token}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()

        bot_id = data["id"]
        avatar_hash = data.get("avatar")
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{bot_id}/{avatar_hash}.png?size=256"
            if avatar_hash
            else None
        )
        return BotInfoOut(
            id=bot_id, username=data.get("username", "Grug"), avatar_url=avatar_url
        )
    except Exception:
        logger.warning("Failed to fetch bot info from Discord", exc_info=True)
        return BotInfoOut(id="", username="Grug", avatar_url=None)
