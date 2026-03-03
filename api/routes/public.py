"""Public (unauthenticated) routes — iCal calendar feed."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from grug.db.models import CalendarEvent, EventOccurrenceOverride, GuildConfig
from grug.utils import expand_event_occurrences

router = APIRouter(tags=["public"])


@router.get("/api/guilds/{guild_id}/events/ical")
async def export_ical(
    guild_id: int,
    token: str = Query(..., description="Calendar feed token"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export guild calendar events as a subscribable iCal (.ics) feed.

    Protected by a per-guild ``token`` query parameter so the URL is not
    completely public.  Admins can regenerate the token at any time via
    ``POST /api/guilds/{guild_id}/calendar-token/regenerate``, which
    invalidates existing subscriptions.

    Returns a ``text/calendar`` response suitable for import or subscription
    in Google Calendar, Apple Calendar, Outlook, and any other iCal-compatible
    application.
    """

    from icalendar import Calendar, Event as ICalEvent, vText  # type: ignore[import-untyped]

    # Validate token against the guild config.
    cfg_result = await db.execute(
        select(GuildConfig).where(GuildConfig.guild_id == guild_id)
    )
    cfg = cfg_result.scalar_one_or_none()
    if cfg is None or not cfg.calendar_token or cfg.calendar_token != token:
        raise HTTPException(status_code=401, detail="Invalid or missing calendar token")

    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.guild_id == guild_id)
    )
    events = result.scalars().all()

    # Load overrides for all events at once.
    event_ids = [e.id for e in events]
    overrides_by_event: dict[int, list[EventOccurrenceOverride]] = {}
    if event_ids:
        overrides_result = await db.execute(
            select(EventOccurrenceOverride).where(
                EventOccurrenceOverride.event_id.in_(event_ids)
            )
        )
        for ov in overrides_result.scalars().all():
            overrides_by_event.setdefault(ov.event_id, []).append(ov)

    # Resolve the guild's display name from the config (use guild_id as fallback).
    cal_name = f"Guild {guild_id} Events"

    cal = Calendar()
    cal.add("prodid", "-//Grug Bot//Grug Calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    # X-WR-CALNAME is the display name shown in most calendar apps.
    cal.add("x-wr-calname", vText(cal_name))
    # Encourage calendar apps to refresh every hour.
    cal.add("x-published-ttl", "PT1H")
    cal.add("x-wr-timezone", "UTC")

    # Expand a wide window (2 years back, 2 years forward) for the .ics feed.
    now = datetime.now(timezone.utc)
    window_start = now.replace(year=now.year - 2, month=1, day=1)
    window_end = now.replace(year=now.year + 2, month=12, day=31)

    for ev in events:
        overrides = overrides_by_event.get(ev.id, [])
        occurrences = expand_event_occurrences(
            ev, window_start, window_end, overrides=overrides
        )
        for occ in occurrences:
            ical_ev = ICalEvent()
            uid = f"grug-{ev.id}-{occ['occurrence_start'].strftime('%Y%m%dT%H%M%SZ')}@grug"
            ical_ev.add("uid", uid)
            ical_ev.add("summary", ev.title)
            ical_ev.add("dtstart", occ["occurrence_start"])
            ical_ev.add("dtend", occ["occurrence_end"])
            if ev.description:
                ical_ev.add("description", vText(ev.description))
            if ev.location:
                ical_ev.add("location", vText(ev.location))
            ical_ev.add("dtstamp", now)
            cal.add_component(ical_ev)

    ics_bytes = cal.to_ical()
    return Response(
        content=ics_bytes,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="guild-{guild_id}-events.ics"',
            # Allow calendar apps to cache the feed.
            "Cache-Control": "public, max-age=3600",
        },
    )
