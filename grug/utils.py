"""Shared utility functions used across the Grug codebase.

Centralises small helpers that were previously duplicated in multiple modules
(agent tools, cogs, indexers). Import from here instead of redefining locally.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from grug.config.settings import get_settings
from grug.db.models import Campaign, GuildConfig
from grug.db.session import get_session_factory

if TYPE_CHECKING:
    from grug.db.models import CalendarEvent

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
            settings = get_settings()
            session.add(
                GuildConfig(guild_id=guild_id, timezone=settings.default_timezone)
            )
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


# ---------------------------------------------------------------------------
# RRULE expansion for calendar events
# ---------------------------------------------------------------------------


def expand_event_occurrences(
    event: CalendarEvent,
    range_start: datetime,
    range_end: datetime,
    *,
    max_occurrences: int = 200,
) -> list[dict]:
    """Expand a recurring ``CalendarEvent`` into concrete occurrences.

    For non-recurring events (``event.rrule is None``) the function returns a
    single-item list if the event falls within *range_start* … *range_end*,
    or an empty list otherwise.

    For recurring events the iCal RRULE string is parsed via
    ``dateutil.rrule`` and occurrences within the requested range are
    materialised.

    Each returned dict contains all event fields plus ``occurrence_start``
    and ``occurrence_end`` representing that specific instance.

    Parameters
    ----------
    event:
        The ORM ``CalendarEvent`` instance (must be loaded / attached).
    range_start, range_end:
        The window to enumerate occurrences within (inclusive of start).
    max_occurrences:
        Safety cap to prevent unbounded expansion.
    """
    duration = (
        (event.end_time - event.start_time) if event.end_time else timedelta(hours=1)
    )

    base = {
        "id": event.id,
        "guild_id": event.guild_id,
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "rrule": event.rrule,
        "location": event.location,
        "channel_id": event.channel_id,
        "created_by": event.created_by,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }

    if not event.rrule:
        # Non-recurring: include if it overlaps the range at all.
        occ_end = event.start_time + duration
        if event.start_time <= range_end and occ_end >= range_start:
            return [
                {
                    **base,
                    "occurrence_start": event.start_time,
                    "occurrence_end": occ_end,
                }
            ]
        return []

    # Recurring — parse the RRULE anchored at `event.start_time`.
    from dateutil.rrule import rrulestr  # type: ignore[import-untyped]

    rule = rrulestr(
        f"DTSTART:{event.start_time.strftime('%Y%m%dT%H%M%SZ')}\nRRULE:{event.rrule}",
        ignoretz=False,
    )

    occurrences: list[dict] = []
    for dt in rule:
        # dateutil may return naive datetimes — ensure UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt > range_end:
            break
        occ_end = dt + duration
        if occ_end >= range_start:
            occurrences.append(
                {
                    **base,
                    "occurrence_start": dt,
                    "occurrence_end": occ_end,
                }
            )
        if len(occurrences) >= max_occurrences:
            break

    return occurrences
