import { useCallback, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Box, Button, CircularProgress, Typography, useTheme } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';

import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin, { type DateClickArg } from '@fullcalendar/interaction';
import type { EventClickArg, DatesSetArg, EventInput } from '@fullcalendar/core';

import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuildContext } from '../hooks/useGuildContext';
import EventCreateModal from '../components/EventCreateModal';
import type { CalendarEvent, ScheduledTask } from '../types';
import EventDetailModal from '../components/EventDetailModal';
import TaskDetailModal from '../components/TaskDetailModal';

import '../styles/fullcalendar-overrides.css';

/* ------------------------------------------------------------------ */
/* EventsPage — calendar view                                         */
/* ------------------------------------------------------------------ */

export default function EventsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const theme = useTheme();
  const calRef = useRef<FullCalendar>(null);
  const { isAdmin } = useGuildContext();

  /* ---- visible date range (controlled by FullCalendar) ---- */
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);

  /* ---- modal state ---- */
  const [createOpen, setCreateOpen] = useState(false);
  const [createDefault, setCreateDefault] = useState<string>('');
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [selectedTask, setSelectedTask] = useState<ScheduledTask | null>(null);

  /* ---- data fetching ---- */
  const { data: events, isLoading: eventsLoading } = useQuery<CalendarEvent[]>({
    queryKey: ['events', guildId, range?.start, range?.end],
    queryFn: async () => {
      if (!range) return [];
      const res = await client.get<CalendarEvent[]>(`/api/guilds/${guildId}/events`, {
        params: { start: range.start, end: range.end },
      });
      return res.data;
    },
    enabled: !!guildId && !!range,
  });

  const { data: tasks } = useQuery<ScheduledTask[]>({
    queryKey: ['tasks', guildId],
    queryFn: async () => {
      const res = await client.get<ScheduledTask[]>(`/api/guilds/${guildId}/tasks`);
      return res.data;
    },
    enabled: !!guildId,
  });

  /* ---- merge events + tasks into FullCalendar EventInputs ---- */
  const calendarEvents: EventInput[] = useMemo(() => {
    const items: EventInput[] = [];

    // Calendar events
    for (const ev of events ?? []) {
      items.push({
        id: `event-${ev.id}-${ev.occurrence_start ?? ev.start_time}`,
        title: ev.title,
        start: ev.occurrence_start ?? ev.start_time,
        end: ev.occurrence_end ?? ev.end_time ?? undefined,
        color: theme.palette.primary.main,
        extendedProps: { type: 'event' as const, data: ev },
      });
    }

    // Scheduled tasks (show those with a computable next time)
    for (const t of tasks ?? []) {
      if (!t.enabled) continue;
      const when = t.next_run ?? t.fire_at;
      if (!when) continue;
      // Only include if within visible range
      if (range) {
        const d = new Date(when);
        if (d < new Date(range.start) || d > new Date(range.end)) continue;
      }
      items.push({
        id: `task-${t.id}`,
        title: `📋 ${t.name ?? t.prompt.slice(0, 40)}`,
        start: when,
        allDay: false,
        color: theme.palette.success.main,
        classNames: ['fc-event-task'],
        extendedProps: { type: 'task' as const, data: t },
      });
    }

    return items;
  }, [events, tasks, range, theme]);

  /* ---- FullCalendar callbacks ---- */
  const handleDatesSet = useCallback((arg: DatesSetArg) => {
    setRange({
      start: arg.startStr,
      end: arg.endStr,
    });
  }, []);

  const handleEventClick = useCallback((arg: EventClickArg) => {
    const { type, data } = arg.event.extendedProps;
    if (type === 'event') {
      setSelectedEvent(data as CalendarEvent);
    } else if (type === 'task') {
      setSelectedTask(data as ScheduledTask);
    }
  }, []);

  const handleDateClick = useCallback((arg: DateClickArg) => {
    if (!isAdmin) return;
    // Pre-fill the create modal with the clicked date
    const pad = (n: number) => String(n).padStart(2, '0');
    const d = arg.date;
    const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    setCreateDefault(local);
    setCreateOpen(true);
  }, [isAdmin]);

  /* ---- CSS custom properties for FullCalendar theme ---- */
  const cssVars: Record<string, string> = {
    '--grug-bg': theme.palette.background.default,
    '--grug-paper': theme.palette.background.paper,
    '--grug-divider': theme.palette.divider,
    '--grug-primary': theme.palette.primary.main,
    '--grug-primary-alpha': theme.palette.mode === 'dark' ? 'rgba(88,166,255,0.25)' : 'rgba(9,105,218,0.25)',
    '--grug-success': theme.palette.success.main,
    '--grug-text-primary': theme.palette.text.primary,
    '--grug-text-secondary': theme.palette.text.secondary,
    '--grug-hover': theme.palette.mode === 'dark' ? 'rgba(88,166,255,0.06)' : 'rgba(9,105,218,0.04)',
    '--grug-today-bg': theme.palette.mode === 'dark' ? 'rgba(88,166,255,0.08)' : 'rgba(9,105,218,0.06)',
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Header row */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Session calendar — plan your games, track events, and see upcoming tasks.
          Click a date to create an event or click an item for details.
        </Typography>
        {isAdmin && (
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => { setCreateDefault(''); setCreateOpen(true); }}
            sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
          >
            New Event
          </Button>
        )}
      </Box>

      {/* Calendar */}
      {eventsLoading && !events ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Box sx={cssVars as Record<string, unknown>}>
          <FullCalendar
            ref={calRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView="dayGridMonth"
            headerToolbar={{
              left: 'prev,next today',
              center: 'title',
              right: 'dayGridMonth,timeGridWeek,timeGridDay',
            }}
            events={calendarEvents}
            datesSet={handleDatesSet}
            eventClick={handleEventClick}
            dateClick={handleDateClick}
            height="auto"
            dayMaxEvents={4}
            nowIndicator
            eventTimeFormat={{ hour: 'numeric', minute: '2-digit', meridiem: 'short' }}
          />
        </Box>
      )}

      {/* Modals */}
      <EventCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        defaultStart={createDefault}
      />

      {selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          open={!!selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}

      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          open={!!selectedTask}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </Box>
  );
}
