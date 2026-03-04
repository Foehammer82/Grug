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
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import RRuleBuilder from './RRuleBuilder';
import type { Campaign } from '../types';

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
/* Component                                                           */
/* ------------------------------------------------------------------ */

const EMPTY_FORM = {
  title: '',
  description: '',
  start_time: '',
  end_time: '',
  location: '',
  rrule: '',
  channel_id: null as string | null,
  campaign_id: null as number | null,
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

  const { data: campaigns } = useQuery<Campaign[]>({
    queryKey: ['campaigns', guildId],
    queryFn: async () => {
      const res = await client.get<Campaign[]>(`/api/guilds/${guildId}/campaigns`);
      return res.data;
    },
    enabled: !!guildId && open,
  });

  const activeCampaigns = campaigns?.filter((c) => c.is_active && !c.deleted_at) ?? [];

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        title: form.title,
        description: form.description || null,
        start_time: form.start_time ? new Date(form.start_time).toISOString() : null,
        end_time: form.end_time ? new Date(form.end_time).toISOString() : null,
        rrule: form.rrule || null,
        location: form.location || null,
        channel_id: form.channel_id ?? null,
        campaign_id: form.campaign_id ?? null,
      };
      await client.post(`/api/guilds/${guildId}/events`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events', guildId] });
      handleClose();
    },
  });

  const selectedChannel = channels?.find((c) => c.id === form.channel_id) ?? null;
  const selectedCampaign = activeCampaigns.find((c) => c.id === form.campaign_id) ?? null;
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

        <RRuleBuilder
          guildId={guildId!}
          value={form.rrule}
          onChange={(v) => setForm((f) => ({ ...f, rrule: v }))}
        />

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

        {activeCampaigns.length > 0 && (
          <Autocomplete
            size="small"
            fullWidth
            options={activeCampaigns}
            value={selectedCampaign}
            onChange={(_, c) => setForm((f) => ({ ...f, campaign_id: c?.id ?? null }))}
            getOptionLabel={(c) => c.name}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Campaign (optional)"
                helperText="Link this event as a session for a campaign."
              />
            )}
          />
        )}

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
