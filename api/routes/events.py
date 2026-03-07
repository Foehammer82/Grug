"""Event and task routes."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
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
    RruleFromTextOut,
    RruleFromTextRequest,
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
    await assert_guild_member(guild_id, user)

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
                "campaign_id": e.campaign_id,
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
    await assert_guild_member(guild_id, user)
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
        reminder_days=body.reminder_days,
        reminder_time=body.reminder_time,
        poll_advance_days=body.poll_advance_days,
        campaign_id=body.campaign_id,
        created_by=user_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # Auto-create reminders for the new event, but only if a channel is set.
    if channel_id is not None:
        from grug.event_reminders import create_event_reminders

        await create_event_reminders(event.id, guild_id, channel_id)

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
    await assert_guild_member(guild_id, user)
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

    # Refresh reminders if timing, channel, or reminder config changed.
    _reminder_fields = {"start_time", "reminder_days", "reminder_time", "channel_id"}
    if body.model_fields_set & _reminder_fields:
        from grug.event_reminders import refresh_event_reminders

        await refresh_event_reminders(event.id)

    return event


@router.delete("/api/guilds/{guild_id}/events/{event_id}", status_code=204)
async def delete_event(
    guild_id: int,
    event_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a calendar event."""
    await assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    event = await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )

    # Clean up any linked reminder tasks before deleting the event.
    from grug.event_reminders import delete_event_reminders

    await delete_event_reminders(event_id)

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
    await assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        CalendarEvent,
        CalendarEvent.id == event_id,
        CalendarEvent.guild_id == guild_id,
        detail="Event not found",
    )
    result = await db.execute(select(EventRSVP).where(EventRSVP.event_id == event_id))
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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


@router.delete("/api/guilds/{guild_id}/polls/{poll_id}/vote", status_code=204)
async def delete_poll_vote(
    guild_id: int,
    poll_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the current user's vote from a poll."""
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
    from api.services import parse_cron_from_text

    cron_expr = await parse_cron_from_text(body.text)
    return CronFromTextOut(cron_expression=cron_expr)


@router.post(
    "/api/guilds/{guild_id}/events/rrule-from-text", response_model=RruleFromTextOut
)
async def guild_rrule_from_text(
    guild_id: int,
    body: RruleFromTextRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> RruleFromTextOut:
    """Convert a plain-English recurrence description to an iCal RRULE string."""
    await assert_guild_member(guild_id, user)
    from api.services import parse_rrule_from_text

    rrule = await parse_rrule_from_text(body.text)
    return RruleFromTextOut(rrule=rrule)


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
    await assert_guild_member(guild_id, user)
    await assert_guild_admin(guild_id, user)
    user_id = int(user["id"])
    await ensure_guild(guild_id)

    # Load guild config once to resolve channel_id fallback and timezone.
    cfg_result = await db.execute(
        select(GuildConfig).where(GuildConfig.guild_id == guild_id)
    )
    cfg = cfg_result.scalar_one_or_none()

    if body.channel_id is not None:
        channel_id = int(body.channel_id)
    else:
        channel_id = (
            int(cfg.announce_channel_id) if cfg and cfg.announce_channel_id else 0
        )

    guild_timezone = cfg.timezone if cfg and cfg.timezone else "UTC"
    name = body.name or (body.prompt[:80] if body.type == "once" else None)
    task = ScheduledTask(
        guild_id=guild_id,
        channel_id=channel_id,
        type=body.type,
        name=name,
        prompt=body.prompt,
        fire_at=body.fire_at,
        cron_expression=body.cron_expression,
        timezone=guild_timezone,
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
    await assert_guild_member(guild_id, user)
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
    await assert_guild_member(guild_id, user)
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
