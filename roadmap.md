# Grug Roadmap

## Campaign Session Scheduling

### Phase 1 — Core Infrastructure (implemented)

- `campaign_id` FK on `CalendarEvent` — link events to campaigns
- `schedule_mode` on `Campaign` — `'fixed'` (GM picks time) or `'poll'` (availability poll decides)
- `event_id` FK on `ScheduledTask` — link auto-created reminders to their event
- Event reminders service (`grug/event_reminders.py`) — auto-creates 24h + 1h one-shot reminders; idempotent create/refresh/delete
- Enhanced agent tools: `create_calendar_event` now supports rrule, location, campaign_id; new `rsvp_to_event`, `get_next_session`, `get_session_attendance` tools
- `get_campaign_info` includes next scheduled session in its output
- API schemas + routes updated with campaign_id on events, schedule_mode on campaigns, auto-create/delete reminders on event CRUD
- Scheduler integration: after a reminder fires, reminders for the next recurring occurrence are auto-refreshed

### Phase 2 — Poll-Based Scheduling & Campaign UI (future)

- Availability poll integration: when `schedule_mode='poll'`, automatically create an `AvailabilityPoll` after each session to find the next date
- Campaign schedule page in web UI — view upcoming sessions, RSVP, manage recurring schedule
- Discord embed for session reminders with RSVP buttons
- Per-player timezone awareness for scheduling suggestions
- "Best time" algorithm — suggest optimal session times based on poll results and historical attendance
