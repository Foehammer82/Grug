import {
  Autocomplete,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import client from '../api/client';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface CalendarEvent {
  id: number;
  guild_id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string | null;
  rrule: string | null;
  location: string | null;
  channel_id: number | null;
  created_by: number;
  created_at: string;
  updated_at: string | null;
  occurrence_start: string | null;
  occurrence_end: string | null;
}

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

interface Props {
  event: CalendarEvent;
  open: boolean;
  onClose: () => void;
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function EventDetailModal({ event, open, onClose }: Props) {
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const { data: channels } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId && open,
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

  const selectedChannel = channels?.find((c) => c.id === String(event.channel_id)) ?? null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        Event Details
        <Button
          size="small"
          color="error"
          variant="outlined"
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
        >
          Delete
        </Button>
      </DialogTitle>

      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
        <TextField
          label="Title"
          defaultValue={event.title}
          onBlur={(e) => handleBlur('title', e.target.value)}
          fullWidth
          size="small"
        />

        <TextField
          label="Description"
          defaultValue={event.description ?? ''}
          onBlur={(e) => handleBlur('description', e.target.value)}
          fullWidth
          multiline
          minRows={2}
          size="small"
        />

        <TextField
          label="Location"
          defaultValue={event.location ?? ''}
          onBlur={(e) => handleBlur('location', e.target.value)}
          fullWidth
          size="small"
          helperText="Where the session takes place — voice channel, address, etc."
        />

        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Start"
            type="datetime-local"
            defaultValue={toLocalInput(event.start_time)}
            onBlur={(e) =>
              handleBlur('start_time', e.target.value ? new Date(e.target.value).toISOString() : null)
            }
            size="small"
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="End"
            type="datetime-local"
            defaultValue={event.end_time ? toLocalInput(event.end_time) : ''}
            onBlur={(e) =>
              handleBlur('end_time', e.target.value ? new Date(e.target.value).toISOString() : null)
            }
            size="small"
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
        </Box>

        <TextField
          label="Recurrence (RRULE)"
          defaultValue={event.rrule ?? ''}
          onBlur={(e) => handleBlur('rrule', e.target.value)}
          fullWidth
          size="small"
          helperText='iCal RRULE — e.g. "FREQ=WEEKLY;BYDAY=TH" for every Thursday.'
          inputProps={{ style: { fontFamily: 'monospace' } }}
        />

        <Autocomplete
          size="small"
          fullWidth
          options={channels ?? []}
          value={selectedChannel}
          onChange={(_, ch) =>
            patchMutation.mutate({ channel_id: ch?.id ?? null })
          }
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

        {/* Placeholder for future RSVP / availability section */}
        <Box sx={{ mt: 1, p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary" fontStyle="italic">
            RSVP &amp; availability polling coming soon.
          </Typography>
        </Box>

        {(patchMutation.isError || deleteMutation.isError) && (
          <Typography color="error" variant="body2">
            Something went wrong — please try again.
          </Typography>
        )}
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
