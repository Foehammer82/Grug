import {
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import BlockIcon from '@mui/icons-material/Block';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useGuildContext } from '../hooks/useGuildContext';
import { useAuth } from '../hooks/useAuth';
import AvailabilityPollsPanel from './AvailabilityPollsPanel';
import type {
  CalendarEvent,
  DiscordChannel,
  EventNote,
  EventRSVP,
  RSVPStatus,
} from '../types';

export type { CalendarEvent } from '../types';

interface Props {
  event: CalendarEvent;
  open: boolean;
  onClose: () => void;
}

/* ------------------------------------------------------------------ */
/* RSVP status colours                                                 */
/* ------------------------------------------------------------------ */

const RSVP_COLORS: Record<RSVPStatus, 'success' | 'warning' | 'error'> = {
  attending: 'success',
  maybe: 'warning',
  declined: 'error',
};

const RSVP_LABELS: Record<RSVPStatus, string> = {
  attending: 'Attending',
  maybe: 'Maybe',
  declined: 'Declined',
};

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function EventDetailModal({ event, open, onClose }: Props) {
  const { guildId } = useParams<{ guildId: string }>();
  const { isAdmin } = useGuildContext();
  const authQuery = useAuth();
  const currentUserId = authQuery.data?.id ?? null;
  const qc = useQueryClient();

  const [newNoteText, setNewNoteText] = useState('');
  const [rsvpNote, setRsvpNote] = useState('');

  const { data: channels } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId && open,
  });

  /* ---- RSVPs ---- */
  const { data: rsvps, isLoading: rsvpsLoading } = useQuery<EventRSVP[]>({
    queryKey: ['rsvps', guildId, event.id],
    queryFn: async () => {
      const res = await client.get<EventRSVP[]>(
        `/api/guilds/${guildId}/events/${event.id}/rsvps`
      );
      return res.data;
    },
    enabled: !!guildId && open,
  });

  const myRsvp = rsvps?.find((r) => r.discord_user_id === currentUserId) ?? null;

  const rsvpMutation = useMutation({
    mutationFn: async (status: RSVPStatus | null) => {
      if (status === null) {
        await client.delete(`/api/guilds/${guildId}/events/${event.id}/rsvp`);
      } else {
        await client.put(`/api/guilds/${guildId}/events/${event.id}/rsvp`, {
          status,
          note: rsvpNote || null,
        });
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rsvps', guildId, event.id] }),
  });

  /* ---- Planning notes ---- */
  const { data: notes, isLoading: notesLoading } = useQuery<EventNote[]>({
    queryKey: ['event-notes', guildId, event.id],
    queryFn: async () => {
      const res = await client.get<EventNote[]>(
        `/api/guilds/${guildId}/events/${event.id}/notes`
      );
      return res.data;
    },
    enabled: !!guildId && open,
  });

  const addNoteMutation = useMutation({
    mutationFn: async (content: string) => {
      await client.post(`/api/guilds/${guildId}/events/${event.id}/notes`, { content });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['event-notes', guildId, event.id] });
      setNewNoteText('');
    },
  });

  const toggleNoteMutation = useMutation({
    mutationFn: async ({ noteId, done }: { noteId: number; done: boolean }) => {
      await client.patch(`/api/guilds/${guildId}/events/${event.id}/notes/${noteId}`, {
        done,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['event-notes', guildId, event.id] }),
  });

  const deleteNoteMutation = useMutation({
    mutationFn: async (noteId: number) => {
      await client.delete(`/api/guilds/${guildId}/events/${event.id}/notes/${noteId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['event-notes', guildId, event.id] }),
  });

  /* ---- Live-edit PATCH ---- */
  const patchMutation = useMutation({
    mutationFn: async (fields: Record<string, unknown>) => {
      await client.patch(`/api/guilds/${guildId}/events/${event.id}`, fields);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['events', guildId] }),
  });

  const handleBlur = (field: string, value: unknown) => {
    const current = (event as unknown as Record<string, unknown>)[field];
    if (value !== current) {
      patchMutation.mutate({ [field]: value || null });
    }
  };

  /* ---- Occurrence cancel (per-occurrence override) ---- */
  const cancelOccurrenceMutation = useMutation({
    mutationFn: async () => {
      const originalStart = event.original_start ?? event.occurrence_start ?? event.start_time;
      await client.put(`/api/guilds/${guildId}/events/${event.id}/overrides`, {
        original_start: originalStart,
        cancelled: true,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      onClose();
    },
  });

  /* ---- Delete ---- */
  const deleteMutation = useMutation({
    mutationFn: async () => {
      await client.delete(`/api/guilds/${guildId}/events/${event.id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      onClose();
    },
  });

  const selectedChannel = channels?.find((c) => c.id === event.channel_id) ?? null;

  /* ---- RSVP summary counts ---- */
  const rsvpCounts = {
    attending: rsvps?.filter((r) => r.status === 'attending').length ?? 0,
    maybe: rsvps?.filter((r) => r.status === 'maybe').length ?? 0,
    declined: rsvps?.filter((r) => r.status === 'declined').length ?? 0,
  };

  const isOccurrence = !!event.occurrence_start || !!event.original_start;
  const isRecurring = !!event.rrule;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        Event Details
        <Box sx={{ display: 'flex', gap: 1 }}>
          {isAdmin && isRecurring && isOccurrence && (
            <Button
              size="small"
              color="warning"
              variant="outlined"
              startIcon={<BlockIcon />}
              onClick={() => cancelOccurrenceMutation.mutate()}
              disabled={cancelOccurrenceMutation.isPending}
              title="Cancel only this occurrence without affecting the series"
            >
              Cancel This
            </Button>
          )}
          {isAdmin && (
            <Button
              size="small"
              color="error"
              variant="outlined"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              Delete
            </Button>
          )}
        </Box>
      </DialogTitle>

      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
        {/* ── Core fields ── */}
        <TextField
          label="Title"
          defaultValue={event.title}
          onBlur={isAdmin ? (e) => handleBlur('title', e.target.value) : undefined}
          fullWidth
          size="small"
          InputProps={{ readOnly: !isAdmin }}
        />

        <TextField
          label="Description"
          defaultValue={event.description ?? ''}
          onBlur={isAdmin ? (e) => handleBlur('description', e.target.value) : undefined}
          fullWidth
          multiline
          minRows={2}
          size="small"
          InputProps={{ readOnly: !isAdmin }}
        />

        <TextField
          label="Location"
          defaultValue={event.location ?? ''}
          onBlur={isAdmin ? (e) => handleBlur('location', e.target.value) : undefined}
          fullWidth
          size="small"
          helperText="Where the session takes place — voice channel, address, etc."
          InputProps={{ readOnly: !isAdmin }}
        />

        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Start"
            type="datetime-local"
            defaultValue={toLocalInput(event.start_time)}
            onBlur={isAdmin ? (e) =>
              handleBlur('start_time', e.target.value ? new Date(e.target.value).toISOString() : null)
            : undefined}
            size="small"
            fullWidth
            InputLabelProps={{ shrink: true }}
            InputProps={{ readOnly: !isAdmin }}
          />
          <TextField
            label="End"
            type="datetime-local"
            defaultValue={event.end_time ? toLocalInput(event.end_time) : ''}
            onBlur={isAdmin ? (e) =>
              handleBlur('end_time', e.target.value ? new Date(e.target.value).toISOString() : null)
            : undefined}
            size="small"
            fullWidth
            InputLabelProps={{ shrink: true }}
            InputProps={{ readOnly: !isAdmin }}
          />
        </Box>

        <TextField
          label="Recurrence (RRULE)"
          defaultValue={event.rrule ?? ''}
          onBlur={isAdmin ? (e) => handleBlur('rrule', e.target.value) : undefined}
          fullWidth
          size="small"
          helperText='iCal RRULE — e.g. "FREQ=WEEKLY;BYDAY=TH" for every Thursday.'
          inputProps={{ style: { fontFamily: 'monospace' } }}
          InputProps={{ readOnly: !isAdmin }}
        />

        <Autocomplete
          size="small"
          fullWidth
          options={channels ?? []}
          value={selectedChannel}
          onChange={isAdmin ? (_, ch) =>
            patchMutation.mutate({ channel_id: ch?.id ?? null })
          : undefined}
          disabled={!isAdmin}
          getOptionLabel={(ch) => `#${ch.name}`}
          isOptionEqualToValue={(opt, val) => opt.id === val.id}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Announce Channel"
              helperText="Discord channel for event announcements."
            />
          )}
        />

        <Divider />

        {/* ── RSVP section ── */}
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            RSVP
          </Typography>

          {/* Summary chips */}
          {rsvpsLoading ? (
            <CircularProgress size={16} />
          ) : (
            <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
              <Chip
                label={`✅ ${rsvpCounts.attending} attending`}
                size="small"
                color="success"
                variant="outlined"
              />
              <Chip
                label={`🤔 ${rsvpCounts.maybe} maybe`}
                size="small"
                color="warning"
                variant="outlined"
              />
              <Chip
                label={`❌ ${rsvpCounts.declined} declined`}
                size="small"
                color="error"
                variant="outlined"
              />
            </Box>
          )}

          {/* My RSVP controls */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <ToggleButtonGroup
              value={myRsvp?.status ?? null}
              exclusive
              onChange={(_, val) => {
                if (val === null) return; // prevent deselect — use remove button
                rsvpMutation.mutate(val as RSVPStatus);
              }}
              size="small"
            >
              <ToggleButton value="attending" color="success">✅ Attending</ToggleButton>
              <ToggleButton value="maybe" color="warning">🤔 Maybe</ToggleButton>
              <ToggleButton value="declined" color="error">❌ Declined</ToggleButton>
            </ToggleButtonGroup>

            <TextField
              label="Add a note (optional)"
              size="small"
              value={rsvpNote}
              onChange={(e) => setRsvpNote(e.target.value)}
              fullWidth
              helperText={myRsvp ? `Your current RSVP: ${RSVP_LABELS[myRsvp.status]}${myRsvp.note ? ` — "${myRsvp.note}"` : ''}` : 'No RSVP yet'}
            />

            {myRsvp && (
              <Button
                size="small"
                color="inherit"
                sx={{ alignSelf: 'flex-start', opacity: 0.7 }}
                onClick={() => rsvpMutation.mutate(null)}
              >
                Remove my RSVP
              </Button>
            )}
          </Box>

          {/* Attendee details (admin can see all) */}
          {isAdmin && rsvps && rsvps.length > 0 && (
            <Box sx={{ mt: 1 }}>
              {rsvps.map((r) => (
                <Box key={r.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Chip
                    label={RSVP_LABELS[r.status as RSVPStatus]}
                    size="small"
                    color={RSVP_COLORS[r.status as RSVPStatus]}
                  />
                  <Typography variant="caption" color="text.secondary">
                    User {r.discord_user_id}
                    {r.note ? ` — ${r.note}` : ''}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </Box>

        <Divider />

        {/* ── Planning notes ── */}
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Planning Notes
          </Typography>

          {notesLoading ? (
            <CircularProgress size={16} />
          ) : notes && notes.length > 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 1 }}>
              {notes.map((note) => (
                <Box
                  key={note.id}
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1,
                    p: 1,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                  }}
                >
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={note.done}
                        size="small"
                        onChange={(e) =>
                          toggleNoteMutation.mutate({ noteId: note.id, done: e.target.checked })
                        }
                        disabled={!isAdmin}
                      />
                    }
                    label={
                      <Typography
                        variant="body2"
                        sx={{
                          textDecoration: note.done ? 'line-through' : 'none',
                          opacity: note.done ? 0.6 : 1,
                        }}
                      >
                        {note.content}
                      </Typography>
                    }
                    sx={{ flex: 1, mr: 0 }}
                  />
                  {isAdmin && (
                    <IconButton
                      size="small"
                      onClick={() => deleteNoteMutation.mutate(note.id)}
                      disabled={deleteNoteMutation.isPending}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
              ))}
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              No planning notes yet.
            </Typography>
          )}

          {isAdmin && (
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                size="small"
                placeholder="Add a note or to-do…"
                value={newNoteText}
                onChange={(e) => setNewNoteText(e.target.value)}
                fullWidth
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newNoteText.trim()) {
                    addNoteMutation.mutate(newNoteText.trim());
                  }
                }}
              />
              <IconButton
                size="small"
                color="primary"
                onClick={() => newNoteText.trim() && addNoteMutation.mutate(newNoteText.trim())}
                disabled={!newNoteText.trim() || addNoteMutation.isPending}
              >
                <AddIcon />
              </IconButton>
            </Box>
          )}
        </Box>

        {(patchMutation.isError || deleteMutation.isError) && (
          <Typography color="error" variant="body2">
            Something went wrong — please try again.
          </Typography>
        )}

        <Divider />

        {/* ── Availability Polls ── */}
        <AvailabilityPollsPanel eventId={event.id} />
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/** Convert ISO string to `YYYY-MM-DDTHH:mm` for datetime-local input. */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
