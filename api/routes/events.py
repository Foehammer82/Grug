"""Event and task routes."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import (
    assert_guild_admin,
    assert_guild_member,
    get_current_user,
    get_db,
    get_or_404,
)
from api.schemas import (
    AvailabilityPollCreate,
    AvailabilityPollOut,
    AvailabilityPollUpdate,
    CalendarEventCreate,
    CalendarEventOut,
    CalendarEventUpdate,
    CronFromTextOut,
    CronFromTextRequest,
    EventNoteCreate,
    EventNoteOut,
    EventNoteUpdate,
    EventOccurrenceOverrideOut,
    EventOccurrenceOverrideUpsert,
    EventRSVPOut,
    EventRSVPUpsert,
    PollVoteOut,
    PollVoteUpsert,
    ScheduledTaskCreate,
    ScheduledTaskOut,
    TaskToggle,
)
from grug.db.models import (
    AvailabilityPoll,
    CalendarEvent,
    EventNote,
    EventOccurrenceOverride,
    EventRSVP,
    GuildConfig,
    PollVote,
    ScheduledTask,
)
from grug.utils import ensure_guild, expand_event_occurrences

router = APIRouter(tags=["events"])


# --------------------------------------------------------------------------- #
# Calendar events                                                              #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/events/ical")
async def export_ical(
    guild_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export guild calendar events as a subscribable iCal (.ics) feed.

    This endpoint is unauthenticated so it can be subscribed to directly from
    calendar applications.  To restrict access, add a secret token query
    parameter in a future iteration.
    """
    from icalendar import Calendar, Event as ICalEvent, vText  # type: ignore[import-untyped]

    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.guild_id == guild_id)
    )
    events = result.scalars().all()

    # Load overrides for all events at once.
    event_ids = [e.id for e in events]
    overrides_result = await db.execute(
        select(EventOccurrenceOverride).where(
            EventOccurrenceOverride.event_id.in_(event_ids)
        )
    )
    overrides_by_event: dict[int, list] = {}
    for ov in overrides_result.scalars().all():
        overrides_by_event.setdefault(ov.event_id, []).append(ov)

    cal = Calendar()
    cal.add("prodid", "-//Grug Bot//Grug Calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", f"Guild {guild_id} Events")

    # Expand a wide window (2 years back, 2 years forward) for the .ics feed.
    now = datetime.now(timezone.utc)
    from datetime import timedelta

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
            "Content-Disposition": f'attachment; filename="guild-{guild_id}-events.ics"'
        },
    )


@router.get("/api/guilds/{guild_id}/events", response_model=list[CalendarEventOut])
async def list_events(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start: datetime | None = Query(None, description="Range start (ISO 8601)"),
    end: datetime | None = Query(None, description="Range end (ISO 8601)"),
) -> list[dict]:
    """List calendar events for a guild.

    When *start* and *end* are supplied the response includes expanded
    occurrences of recurring events within that window.  Without range
    parameters the endpoint falls back to returning upcoming events
    (start_time >= now) without RRULE expansion.
    """
    assert_guild_member(guild_id, user)

    if start is not None and end is not None:
        # Date-range mode — return expanded occurrences.
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        result = await db.execute(
            select(CalendarEvent).where(CalendarEvent.guild_id == guild_id)
        )
        events = result.scalars().all()

        # Load occurrence overrides for all events in one query.
        event_ids = [e.id for e in events]
        if event_ids:
            ov_result = await db.execute(
                select(EventOccurrenceOverride).where(
                    EventOccurrenceOverride.event_id.in_(event_ids)
                )
            )
            overrides_by_event: dict[int, list] = {}
            for ov in ov_result.scalars().all():
                overrides_by_event.setdefault(ov.event_id, []).append(ov)
        else:
            overrides_by_event = {}

        occurrences: list[dict] = []
        for ev in events:
            occurrences.extend(
                expand_event_occurrences(
                    ev, start, end, overrides=overrides_by_event.get(ev.id, [])
                )
            )
        occurrences.sort(key=lambda o: o["occurrence_start"])
        return occurrences
    else:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(CalendarEvent)
            .where(CalendarEvent.guild_id == guild_id, CalendarEvent.start_time >= now)
            .order_by(CalendarEvent.start_time)
        )
        rows = result.scalars().all()
        return [
            {
                "id": e.id,
                "guild_id": e.guild_id,
                "title": e.title,
                "description": e.description,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "rrule": e.rrule,
                "location": e.location,
                "channel_id": e.channel_id,
                "created_by": e.created_by,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
            }
            for e in rows
        ]


@router.post(
    "/api/guilds/{guild_id}/events", response_model=CalendarEventOut, status_code=201
)
async def create_event(
    guild_id: int,
    body: CalendarEventCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Create a new calendar event."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    user_id = int(user["id"])
    await ensure_guild(guild_id)

    channel_id = int(body.channel_id) if body.channel_id is not None else None
    event = CalendarEvent(
        guild_id=guild_id,
        title=body.title,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        rrule=body.rrule,
        location=body.location,
        channel_id=channel_id,
        created_by=user_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.patch(
    "/api/guilds/{guild_id}/events/{event_id}", response_model=CalendarEventOut
)
async def update_event(
    guild_id: int,
    event_id: int,
    body: CalendarEventUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Update a calendar event.  Uses ``model_fields_set`` so explicit
    ``null`` clears the field."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    event = await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )

    for field in body.model_fields_set:
        value = getattr(body, field)
        if field == "channel_id" and value is not None:
            value = int(value)
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/api/guilds/{guild_id}/events/{event_id}", status_code=204)
async def delete_event(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a calendar event."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    event = await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    await db.delete(event)
    await db.commit()


# --------------------------------------------------------------------------- #
# RSVP                                                                        #
# --------------------------------------------------------------------------- #


@router.get(
    "/api/guilds/{guild_id}/events/{event_id}/rsvps",
    response_model=list[EventRSVPOut],
)
async def list_rsvps(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EventRSVP]:
    """List all RSVPs for a calendar event."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    result = await db.execute(
        select(EventRSVP).where(EventRSVP.event_id == event_id)
    )
    return list(result.scalars().all())


@router.put(
    "/api/guilds/{guild_id}/events/{event_id}/rsvp",
    response_model=EventRSVPOut,
)
async def upsert_rsvp(
    guild_id: int,
    event_id: int,
    body: EventRSVPUpsert,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventRSVP:
    """Set or update the current user's RSVP for an event."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    discord_user_id = int(user["id"])
    result = await db.execute(
        select(EventRSVP).where(
            EventRSVP.event_id == event_id,
            EventRSVP.discord_user_id == discord_user_id,
        )
    )
    rsvp = result.scalar_one_or_none()
    if rsvp is None:
        rsvp = EventRSVP(
            event_id=event_id,
            discord_user_id=discord_user_id,
            status=body.status,
            note=body.note,
        )
        db.add(rsvp)
    else:
        rsvp.status = body.status
        rsvp.note = body.note
    await db.commit()
    await db.refresh(rsvp)
    return rsvp


@router.delete("/api/guilds/{guild_id}/events/{event_id}/rsvp", status_code=204)
async def delete_rsvp(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the current user's RSVP for an event."""
    assert_guild_member(guild_id, user)
    discord_user_id = int(user["id"])
    result = await db.execute(
        select(EventRSVP).where(
            EventRSVP.event_id == event_id,
            EventRSVP.discord_user_id == discord_user_id,
        )
    )
    rsvp = result.scalar_one_or_none()
    if rsvp is not None:
        await db.delete(rsvp)
        await db.commit()


# --------------------------------------------------------------------------- #
# Planning notes                                                               #
# --------------------------------------------------------------------------- #


@router.get(
    "/api/guilds/{guild_id}/events/{event_id}/notes",
    response_model=list[EventNoteOut],
)
async def list_notes(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EventNote]:
    """List planning notes for a calendar event."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    result = await db.execute(
        select(EventNote)
        .where(EventNote.event_id == event_id)
        .order_by(EventNote.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/events/{event_id}/notes",
    response_model=EventNoteOut,
    status_code=201,
)
async def create_note(
    guild_id: int,
    event_id: int,
    body: EventNoteCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventNote:
    """Add a planning note to a calendar event."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    note = EventNote(
        event_id=event_id,
        content=body.content,
        created_by=int(user["id"]),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.patch(
    "/api/guilds/{guild_id}/events/{event_id}/notes/{note_id}",
    response_model=EventNoteOut,
)
async def update_note(
    guild_id: int,
    event_id: int,
    note_id: int,
    body: EventNoteUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventNote:
    """Update a planning note's content or done state."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    note = await get_or_404(
        db,
        EventNote,
        EventNote.id == note_id,
        EventNote.event_id == event_id,
        detail="Note not found",
    )
    for field in body.model_fields_set:
        setattr(note, field, getattr(body, field))
    await db.commit()
    await db.refresh(note)
    return note


@router.delete(
    "/api/guilds/{guild_id}/events/{event_id}/notes/{note_id}", status_code=204
)
async def delete_note(
    guild_id: int,
    event_id: int,
    note_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a planning note."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    note = await get_or_404(
        db,
        EventNote,
        EventNote.id == note_id,
        EventNote.event_id == event_id,
        detail="Note not found",
    )
    await db.delete(note)
    await db.commit()


# --------------------------------------------------------------------------- #
# Occurrence overrides                                                         #
# --------------------------------------------------------------------------- #


@router.get(
    "/api/guilds/{guild_id}/events/{event_id}/overrides",
    response_model=list[EventOccurrenceOverrideOut],
)
async def list_overrides(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EventOccurrenceOverride]:
    """List per-occurrence overrides for a recurring event."""
    assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    result = await db.execute(
        select(EventOccurrenceOverride)
        .where(EventOccurrenceOverride.event_id == event_id)
        .order_by(EventOccurrenceOverride.original_start)
    )
    return list(result.scalars().all())


@router.put(
    "/api/guilds/{guild_id}/events/{event_id}/overrides",
    response_model=EventOccurrenceOverrideOut,
)
async def upsert_override(
    guild_id: int,
    event_id: int,
    body: EventOccurrenceOverrideUpsert,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventOccurrenceOverride:
    """Create or update a per-occurrence override for a recurring event.

    Identified by ``original_start`` — pass ``cancelled=true`` to hide the
    occurrence; set ``new_start`` / ``new_end`` to reschedule it.
    """
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    original_start = body.original_start
    if original_start.tzinfo is None:
        original_start = original_start.replace(tzinfo=timezone.utc)

    result = await db.execute(
        select(EventOccurrenceOverride).where(
            EventOccurrenceOverride.event_id == event_id,
            EventOccurrenceOverride.original_start == original_start,
        )
    )
    override = result.scalar_one_or_none()
    if override is None:
        override = EventOccurrenceOverride(
            event_id=event_id,
            original_start=original_start,
            new_start=body.new_start,
            new_end=body.new_end,
            cancelled=body.cancelled,
        )
        db.add(override)
    else:
        override.new_start = body.new_start
        override.new_end = body.new_end
        override.cancelled = body.cancelled
    await db.commit()
    await db.refresh(override)
    return override


@router.delete(
    "/api/guilds/{guild_id}/events/{event_id}/overrides/{override_id}",
    status_code=204,
)
async def delete_override(
    guild_id: int,
    event_id: int,
    override_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a per-occurrence override, restoring the normal RRULE occurrence."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    override = await get_or_404(
        db,
        EventOccurrenceOverride,
        EventOccurrenceOverride.id == override_id,
        EventOccurrenceOverride.event_id == event_id,
        detail="Override not found",
    )
    await db.delete(override)
    await db.commit()


# --------------------------------------------------------------------------- #
# Availability polls                                                           #
# --------------------------------------------------------------------------- #


@router.get(
    "/api/guilds/{guild_id}/polls",
    response_model=list[AvailabilityPollOut],
)
async def list_polls(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AvailabilityPoll]:
    """List availability polls for a guild."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(AvailabilityPoll)
        .where(AvailabilityPoll.guild_id == guild_id)
        .options(selectinload(AvailabilityPoll.votes))
        .order_by(AvailabilityPoll.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/polls",
    response_model=AvailabilityPollOut,
    status_code=201,
)
async def create_poll(
    guild_id: int,
    body: AvailabilityPollCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityPoll:
    """Create a new availability poll for a guild."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    await ensure_guild(guild_id)

    options = [o.model_dump(mode="json") for o in body.options]
    poll = AvailabilityPoll(
        guild_id=guild_id,
        event_id=body.event_id,
        title=body.title,
        options=options,
        closes_at=body.closes_at,
        created_by=int(user["id"]),
    )
    db.add(poll)
    await db.commit()
    await db.refresh(poll)
    # Eager-load votes (empty on creation)
    result = await db.execute(
        select(AvailabilityPoll)
        .where(AvailabilityPoll.id == poll.id)
        .options(selectinload(AvailabilityPoll.votes))
    )
    return result.scalar_one()


@router.get(
    "/api/guilds/{guild_id}/polls/{poll_id}",
    response_model=AvailabilityPollOut,
)
async def get_poll(
    guild_id: int,
    poll_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityPoll:
    """Get a single availability poll with its votes."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(AvailabilityPoll)
        .where(
            AvailabilityPoll.id == poll_id,
            AvailabilityPoll.guild_id == guild_id,
        )
        .options(selectinload(AvailabilityPoll.votes))
    )
    poll = result.scalar_one_or_none()
    if poll is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Poll not found")
    return poll


@router.patch(
    "/api/guilds/{guild_id}/polls/{poll_id}",
    response_model=AvailabilityPollOut,
)
async def update_poll(
    guild_id: int,
    poll_id: int,
    body: AvailabilityPollUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityPoll:
    """Update a poll (e.g. set winner or close it)."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    result = await db.execute(
        select(AvailabilityPoll)
        .where(
            AvailabilityPoll.id == poll_id,
            AvailabilityPoll.guild_id == guild_id,
        )
        .options(selectinload(AvailabilityPoll.votes))
    )
    poll = result.scalar_one_or_none()
    if poll is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Poll not found")
    for field in body.model_fields_set:
        setattr(poll, field, getattr(body, field))
    await db.commit()
    await db.refresh(poll)
    result = await db.execute(
        select(AvailabilityPoll)
        .where(AvailabilityPoll.id == poll.id)
        .options(selectinload(AvailabilityPoll.votes))
    )
    return result.scalar_one()


@router.put(
    "/api/guilds/{guild_id}/polls/{poll_id}/vote",
    response_model=PollVoteOut,
)
async def upsert_poll_vote(
    guild_id: int,
    poll_id: int,
    body: PollVoteUpsert,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PollVote:
    """Cast or update the current user's vote on a poll."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(AvailabilityPoll).where(
            AvailabilityPoll.id == poll_id,
            AvailabilityPoll.guild_id == guild_id,
        )
    )
    poll = result.scalar_one_or_none()
    if poll is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Poll not found")

    discord_user_id = int(user["id"])
    vote_result = await db.execute(
        select(PollVote).where(
            PollVote.poll_id == poll_id,
            PollVote.discord_user_id == discord_user_id,
        )
    )
    vote = vote_result.scalar_one_or_none()
    if vote is None:
        vote = PollVote(
            poll_id=poll_id,
            discord_user_id=discord_user_id,
            option_ids=body.option_ids,
        )
        db.add(vote)
    else:
        vote.option_ids = body.option_ids
    await db.commit()
    await db.refresh(vote)
    return vote


@router.delete(
    "/api/guilds/{guild_id}/polls/{poll_id}/vote", status_code=204
)
async def delete_poll_vote(
    guild_id: int,
    poll_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the current user's vote from a poll."""
    assert_guild_member(guild_id, user)
    discord_user_id = int(user["id"])
    result = await db.execute(
        select(PollVote).where(
            PollVote.poll_id == poll_id,
            PollVote.discord_user_id == discord_user_id,
        )
    )
    vote = result.scalar_one_or_none()
    if vote is not None:
        await db.delete(vote)
        await db.commit()


@router.delete("/api/guilds/{guild_id}/polls/{poll_id}", status_code=204)
async def delete_poll(
    guild_id: int,
    poll_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an availability poll."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    result = await db.execute(
        select(AvailabilityPoll).where(
            AvailabilityPoll.id == poll_id,
            AvailabilityPoll.guild_id == guild_id,
        )
    )
    poll = result.scalar_one_or_none()
    if poll is not None:
        await db.delete(poll)
        await db.commit()


# --------------------------------------------------------------------------- #
# Scheduled tasks                                                              #
# --------------------------------------------------------------------------- #


@router.get("/api/guilds/{guild_id}/tasks", response_model=list[ScheduledTaskOut])
async def list_tasks(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledTask]:
    """List scheduled tasks for a guild."""
    assert_guild_member(guild_id, user)
    result = await db.execute(
        select(ScheduledTask)
        .where(ScheduledTask.guild_id == guild_id)
        .order_by(ScheduledTask.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/api/guilds/{guild_id}/tasks/cron-from-text", response_model=CronFromTextOut
)
async def guild_cron_from_text(
    guild_id: int,
    body: CronFromTextRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> CronFromTextOut:
    """Convert a plain-English schedule description to a 5-field UTC cron expression."""
    assert_guild_member(guild_id, user)
    from api.services import parse_cron_from_text

    cron_expr = await parse_cron_from_text(body.text)
    return CronFromTextOut(cron_expression=cron_expr)


@router.post(
    "/api/guilds/{guild_id}/tasks", response_model=ScheduledTaskOut, status_code=201
)
async def create_guild_task(
    guild_id: int,
    body: ScheduledTaskCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Create a new scheduled task for a guild via the web UI."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    user_id = int(user["id"])
    await ensure_guild(guild_id)

    # Resolve channel_id: use the provided value or fall back to the guild's announce channel
    if body.channel_id is not None:
        channel_id = int(body.channel_id)
    else:
        cfg_result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        cfg = cfg_result.scalar_one_or_none()
        channel_id = (
            int(cfg.announce_channel_id) if cfg and cfg.announce_channel_id else 0
        )

    name = body.name or (body.prompt[:80] if body.type == "once" else None)
    task = ScheduledTask(
        guild_id=guild_id,
        channel_id=channel_id,
        type=body.type,
        name=name,
        prompt=body.prompt,
        fire_at=body.fire_at,
        cron_expression=body.cron_expression,
        enabled=body.enabled,
        source="web",
        created_by=user_id,
        user_id=user_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/api/guilds/{guild_id}/tasks/{task_id}", response_model=ScheduledTaskOut)
async def toggle_task(
    guild_id: int,
    task_id: int,
    body: TaskToggle,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    """Enable or disable a scheduled task."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    task = await get_or_404(
        db,
        ScheduledTask,
        ScheduledTask.id == task_id,
        ScheduledTask.guild_id == guild_id,
        detail="Task not found",
    )
    task.enabled = body.enabled
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/api/guilds/{guild_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    guild_id: int,
    task_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a scheduled task."""
    assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    task = await get_or_404(
        db,
        ScheduledTask,
        ScheduledTask.id == task_id,
        ScheduledTask.guild_id == guild_id,
        detail="Task not found",
    )
    await db.delete(task)
    await db.commit()

