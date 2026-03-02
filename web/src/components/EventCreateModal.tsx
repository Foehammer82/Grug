import {
  Autocomplete,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** Pre-fill start time when clicking on a calendar date. */
  defaultStart?: string;
}

/* ------------------------------------------------------------------ */
/* Recurrence presets → RRULE strings                                  */
/* ------------------------------------------------------------------ */

const RECURRENCE_PRESETS: { label: string; rrule: string }[] = [
  { label: 'Does not repeat', rrule: '' },
  { label: 'Every week', rrule: 'FREQ=WEEKLY' },
  { label: 'Every 2 weeks', rrule: 'FREQ=WEEKLY;INTERVAL=2' },
  { label: 'Every month', rrule: 'FREQ=MONTHLY' },
  { label: 'Custom…', rrule: '__custom__' },
];

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

const EMPTY_FORM = {
  title: '',
  description: '',
  start_time: '',
  end_time: '',
  location: '',
  rrulePreset: '',
  rruleCustom: '',
  channel_id: null as string | null,
};

export default function EventCreateModal({ open, onClose, defaultStart }: Props) {
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const [form, setForm] = useState({
    ...EMPTY_FORM,
    start_time: defaultStart ?? '',
  });

  // Reset form when opening
  const handleClose = () => {
    setForm({ ...EMPTY_FORM, start_time: defaultStart ?? '' });
    onClose();
  };

  const { data: channels, isLoading: channelsLoading } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId && open,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const rrule =
        form.rrulePreset === '__custom__' ? form.rruleCustom || null : form.rrulePreset || null;

      const payload: Record<string, unknown> = {
        title: form.title,
        description: form.description || null,
        start_time: form.start_time ? new Date(form.start_time).toISOString() : null,
        end_time: form.end_time ? new Date(form.end_time).toISOString() : null,
        rrule: rrule,
        location: form.location || null,
        channel_id: form.channel_id ?? null,
      };
      await client.post(`/api/guilds/${guildId}/events`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      handleClose();
    },
  });

  const selectedChannel = channels?.find((c) => c.id === form.channel_id) ?? null;
  const isFormValid = form.title.trim().length > 0 && !!form.start_time;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>New Event</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
        <TextField
          label="Title"
          required
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          fullWidth
          size="small"
          autoFocus
        />

        <TextField
          label="Description"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          fullWidth
          multiline
          minRows={2}
          size="small"
        />

        <TextField
          label="Location"
          value={form.location}
          onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
          fullWidth
          size="small"
          helperText="Where the session takes place — voice channel, address, etc."
        />

        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Start"
            type="datetime-local"
            required
            value={form.start_time}
            onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
            size="small"
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="End"
            type="datetime-local"
            value={form.end_time}
            onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))}
            size="small"
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
        </Box>

        <FormControl size="small" fullWidth>
          <InputLabel>Recurrence</InputLabel>
          <Select
            label="Recurrence"
            value={form.rrulePreset}
            onChange={(e) => setForm((f) => ({ ...f, rrulePreset: e.target.value }))}
          >
            {RECURRENCE_PRESETS.map((p) => (
              <MenuItem key={p.rrule} value={p.rrule}>
                {p.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {form.rrulePreset === '__custom__' && (
          <TextField
            label="Custom RRULE"
            value={form.rruleCustom}
            onChange={(e) => setForm((f) => ({ ...f, rruleCustom: e.target.value }))}
            fullWidth
            size="small"
            helperText='iCal RRULE — e.g. "FREQ=WEEKLY;INTERVAL=2;BYDAY=TH"'
            inputProps={{ style: { fontFamily: 'monospace' } }}
          />
        )}

        <Autocomplete
          size="small"
          fullWidth
          options={channels ?? []}
          loading={channelsLoading}
          value={selectedChannel}
          onChange={(_, ch) => setForm((f) => ({ ...f, channel_id: ch?.id ?? null }))}
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

        {createMutation.isError && (
          <Typography color="error" variant="body2">
            Failed to create event. Check your inputs and try again.
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!isFormValid || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          {createMutation.isPending ? 'Creating…' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
