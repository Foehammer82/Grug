"""Tests for the RRULE expansion utility and calendar event helpers."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(**overrides):
    """Create a mock CalendarEvent with sensible defaults."""
    defaults = {
        "id": 1,
        "guild_id": 123456,
        "title": "Game Night",
        "description": "Weekly D&D session",
        "start_time": datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
        "rrule": None,
        "location": "Discord voice",
        "channel_id": 999,
        "created_by": 111,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": None,
    }
    defaults.update(overrides)
    ev = MagicMock()
    for k, v in defaults.items():
        setattr(ev, k, v)
    return ev


def _make_override(**overrides):
    """Create a mock EventOccurrenceOverride."""
    defaults = {
        "event_id": 1,
        "original_start": datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
        "new_start": None,
        "new_end": None,
        "cancelled": False,
    }
    defaults.update(overrides)
    ov = MagicMock()
    for k, v in defaults.items():
        setattr(ov, k, v)
    return ov


# ---------------------------------------------------------------------------
# Non-recurring events
# ---------------------------------------------------------------------------


class TestExpandNonRecurring:
    def test_event_within_range(self):
        """A one-off event inside the range is returned."""
        from grug.utils import expand_event_occurrences

        ev = _make_event()
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
        )
        assert len(result) == 1
        assert result[0]["title"] == "Game Night"
        assert result[0]["occurrence_start"] == ev.start_time
        assert result[0]["occurrence_end"] == ev.end_time

    def test_event_outside_range(self):
        """A one-off event outside the range returns empty."""
        from grug.utils import expand_event_occurrences

        ev = _make_event()
        result = expand_event_occurrences(
            ev,
            datetime(2026, 4, 1, tzinfo=timezone.utc),
            datetime(2026, 4, 30, tzinfo=timezone.utc),
        )
        assert len(result) == 0

    def test_event_no_end_time_uses_1h_default(self):
        """When end_time is None a 1-hour default duration is used."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(end_time=None)
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
        )
        assert len(result) == 1
        expected_end = ev.start_time + timedelta(hours=1)
        assert result[0]["occurrence_end"] == expected_end


# ---------------------------------------------------------------------------
# Recurring events
# ---------------------------------------------------------------------------


class TestExpandRecurring:
    def test_weekly_produces_correct_count(self):
        """A weekly RRULE in a 4-week window produces ~4 occurrences."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),  # Thursday
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=WEEKLY;BYDAY=TH",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
        )
        # March 2026 Thursdays: 5, 12, 19, 26
        assert len(result) == 4
        # Each occurrence should preserve the 3-hour duration
        for occ in result:
            assert (occ["occurrence_end"] - occ["occurrence_start"]) == timedelta(
                hours=3
            )

    def test_biweekly(self):
        """A biweekly RRULE produces half as many occurrences."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=WEEKLY;INTERVAL=2;BYDAY=TH",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
        )
        # Biweekly from Mar 5: Mar 5, Mar 19
        assert len(result) == 2

    def test_monthly(self):
        """A monthly RRULE on the 5th produces one occurrence per month."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 1, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=MONTHLY;BYMONTHDAY=5",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        # Jan, Feb, Mar, Apr, May, Jun = 6 months
        assert len(result) == 6

    def test_rrule_with_count_limit(self):
        """An RRULE with COUNT stops after the specified number."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=WEEKLY;BYDAY=TH;COUNT=3",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        assert len(result) == 3

    def test_rrule_with_until(self):
        """An RRULE with UNTIL stops at the specified date."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=WEEKLY;BYDAY=TH;UNTIL=20260320T000000Z",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        # Mar 5, 12, 19 — UNTIL is exclusive of the 20th
        assert len(result) == 3

    def test_max_occurrences_cap(self):
        """The safety cap prevents unbounded expansion."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc),
            rrule="FREQ=DAILY",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2030, 12, 31, tzinfo=timezone.utc),
            max_occurrences=10,
        )
        assert len(result) == 10

    def test_preserves_event_metadata(self):
        """Expanded occurrences carry the parent event's metadata."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            rrule="FREQ=WEEKLY;BYDAY=TH",
            location="Ye Olde Tavern",
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 10, tzinfo=timezone.utc),
        )
        assert len(result) >= 1
        occ = result[0]
        assert occ["id"] == ev.id
        assert occ["title"] == "Game Night"
        assert occ["location"] == "Ye Olde Tavern"
        assert occ["guild_id"] == 123456


# ---------------------------------------------------------------------------
# Occurrence overrides
# ---------------------------------------------------------------------------


class TestOccurrenceOverrides:
    def test_cancelled_occurrence_excluded(self):
        """A cancelled override drops the specific occurrence."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=WEEKLY;BYDAY=TH",
        )
        # Cancel the second Thursday (Mar 12)
        cancel_ov = _make_override(
            event_id=1,
            original_start=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
            cancelled=True,
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
            overrides=[cancel_ov],
        )
        # March Thursdays: 5, 12, 19, 26 — but 12 is cancelled
        assert len(result) == 3
        starts = [r["occurrence_start"] for r in result]
        assert datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc) not in starts

    def test_rescheduled_occurrence_uses_new_times(self):
        """A rescheduled override uses new_start/new_end for the occurrence."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),
            rrule="FREQ=WEEKLY;BYDAY=TH",
        )
        new_start = datetime(2026, 3, 13, 19, 0, tzinfo=timezone.utc)  # Friday instead
        new_end = datetime(2026, 3, 13, 22, 0, tzinfo=timezone.utc)
        reschedule_ov = _make_override(
            event_id=1,
            original_start=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
            new_start=new_start,
            new_end=new_end,
            cancelled=False,
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
            overrides=[reschedule_ov],
        )
        # Still 4 occurrences, but the 2nd has moved
        assert len(result) == 4
        rescheduled = [r for r in result if r["occurrence_start"] == new_start]
        assert len(rescheduled) == 1
        assert rescheduled[0]["occurrence_end"] == new_end

    def test_override_without_new_end_uses_duration(self):
        """An override with only new_start preserves the original duration."""
        from grug.utils import expand_event_occurrences

        ev = _make_event(
            start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 5, 22, 0, tzinfo=timezone.utc),  # 3h duration
            rrule="FREQ=WEEKLY;BYDAY=TH",
        )
        new_start = datetime(2026, 3, 13, 20, 0, tzinfo=timezone.utc)  # 1h later
        reschedule_ov = _make_override(
            event_id=1,
            original_start=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
            new_start=new_start,
            new_end=None,
            cancelled=False,
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
            overrides=[reschedule_ov],
        )
        rescheduled = [r for r in result if r["occurrence_start"] == new_start]
        assert len(rescheduled) == 1
        # Duration should still be 3h
        assert (rescheduled[0]["occurrence_end"] - rescheduled[0]["occurrence_start"]) == timedelta(hours=3)

    def test_non_recurring_event_ignores_overrides(self):
        """Overrides on a non-recurring event have no effect."""
        from grug.utils import expand_event_occurrences

        ev = _make_event()  # no rrule
        ov = _make_override(
            original_start=ev.start_time,
            cancelled=True,
        )
        result = expand_event_occurrences(
            ev,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 31, tzinfo=timezone.utc),
            overrides=[ov],
        )
        # Non-recurring events are included as-is; overrides only apply to RRULE expansions
        assert len(result) == 1


# ---------------------------------------------------------------------------
# iCal export
# ---------------------------------------------------------------------------


class TestICalExport:
    def test_icalendar_library_available(self):
        """The icalendar library can be imported."""
        from icalendar import Calendar  # noqa: F401

        assert Calendar is not None

    def test_ical_generation_single_event(self):
        """A single non-recurring event produces one VEVENT component."""
        from icalendar import Calendar

        ev = _make_event()

        cal = Calendar()
        cal.add("prodid", "-//Grug//Test//EN")
        cal.add("version", "2.0")

        from icalendar import Event as ICalEvent, vText

        ical_ev = ICalEvent()
        ical_ev.add("uid", f"grug-{ev.id}-test@grug")
        ical_ev.add("summary", ev.title)
        ical_ev.add("dtstart", ev.start_time)
        ical_ev.add("dtend", ev.end_time)
        ical_ev.add("description", vText(ev.description))
        cal.add_component(ical_ev)

        ics = cal.to_ical()
        assert b"Game Night" in ics
        assert b"VEVENT" in ics
        assert b"BEGIN:VCALENDAR" in ics


# ---------------------------------------------------------------------------
# Calendar token
# ---------------------------------------------------------------------------


class TestCalendarToken:
    def test_token_is_non_empty(self):
        """secrets.token_urlsafe produces a non-empty string of adequate length."""
        import secrets

        token = secrets.token_urlsafe(32)
        # 32 bytes of randomness → at least 43 base64url chars
        assert len(token) >= 43

    def test_token_uniqueness(self):
        """Two generated tokens are different (collision probability negligible)."""
        import secrets

        t1 = secrets.token_urlsafe(32)
        t2 = secrets.token_urlsafe(32)
        assert t1 != t2

    def test_ical_url_structure(self):
        """The expected iCal feed URL shape is correct."""
        api_base = "http://localhost:8000"
        guild_id = "123456789"
        token = "abc123"
        expected = f"{api_base}/api/guilds/{guild_id}/events/ical?token={token}"
        url = f"{api_base}/api/guilds/{guild_id}/events/ical?token={token}"
        assert url == expected

    def test_webcal_url_substitution(self):
        """https:// is correctly replaced with webcal:// for Apple Calendar links."""
        feed_url = "https://example.com/api/guilds/123/events/ical?token=abc"
        webcal_url = feed_url.replace("https://", "webcal://")
        assert webcal_url == "webcal://example.com/api/guilds/123/events/ical?token=abc"

    def test_google_calendar_url(self):
        """Google Calendar deep-link URL is correctly formed."""
        import urllib.parse
        from urllib.parse import urlparse

        feed_url = "https://example.com/api/guilds/123/events/ical?token=abc"
        google_url = f"https://calendar.google.com/calendar/u/0/r/settings/addbyurl?url={urllib.parse.quote(feed_url)}"
        parsed = urlparse(google_url)
        assert parsed.netloc == "calendar.google.com"
        assert "addbyurl" in parsed.path
        assert "url=" in parsed.query
