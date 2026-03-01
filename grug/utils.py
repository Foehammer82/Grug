"""Shared utility functions used across the Grug codebase.

Centralises small helpers that were previously duplicated in multiple modules
(agent tools, cogs, indexers). Import from here instead of redefining locally.
"""

import re

from sqlalchemy import select

from grug.db.models import Campaign, GuildConfig
from grug.db.session import get_session_factory

# ---------------------------------------------------------------------------
# Game system labels — canonical mapping of system tags to display names.
# Used by the campaigns and characters cogs.
# ---------------------------------------------------------------------------

GAME_SYSTEM_LABELS: dict[str, str] = {
    "dnd5e": "D&D 5e",
    "pf2e": "Pathfinder 2e",
    "unknown": "Unknown / Homebrew",
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def ensure_guild(guild_id: int) -> None:
    """Ensure a GuildConfig row exists for the given guild.

    Creates one with default values if it doesn't exist. This is safe to call
    repeatedly — the check is idempotent.
    """
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        if result.scalar_one_or_none() is None:
            session.add(GuildConfig(guild_id=guild_id))
            await session.commit()


async def get_campaign_id_for_channel(channel_id: int) -> int | None:
    """Return the campaign ID linked to a Discord channel, or None."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Campaign.id).where(Campaign.channel_id == channel_id)
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[str]:
    """Split *text* into overlapping chunks for vector-store indexing.

    Parameters
    ----------
    text:
        The source text to chunk.
    chunk_size:
        Maximum number of characters per chunk.
    overlap:
        Number of characters to overlap between consecutive chunks.

    Returns
    -------
    list[str]
        A list of text chunks. Empty list if *text* is blank.
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks
