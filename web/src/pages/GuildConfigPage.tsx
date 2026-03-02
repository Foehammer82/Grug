import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Autocomplete,
  Box,
  Divider,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface GuildConfig {
  guild_id: number;
  timezone: string;
  // Returned as a string to preserve Discord snowflake precision (> MAX_SAFE_INTEGER)
  announce_channel_id: string | null;
  context_cutoff: string | null; // ISO 8601 UTC datetime string
}

interface ChannelConfig {
  channel_id: number;
  guild_id: number;
  always_respond: boolean;
  context_cutoff: string | null; // ISO 8601 UTC datetime string
  updated_at: string;
}

/** Convert ISO UTC datetime string to datetime-local input value (e.g. "2026-03-01T20:00"). */
function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toISOString().slice(0, 16);
  } catch {
    return '';
  }
}

/** Convert datetime-local input value (UTC assumed) to ISO string, or null if empty. */
function localInputToIso(value: string): string | null {
  if (!value) return null;
  return new Date(value + ':00.000Z').toISOString();
}

interface Defaults {
  default_timezone: string;
}

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

// Full IANA timezone list from the browser's built-in Intl API
const TIMEZONES: string[] = Intl.supportedValuesOf('timeZone');

export default function GuildConfigPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  // Track which channel is selected for per-channel override editing.
  const [selectedChannel, setSelectedChannel] = useState<DiscordChannel | null>(null);

  const { data: config, isLoading: configLoading } = useQuery<GuildConfig>({
    queryKey: ['config', guildId],
    queryFn: async () => {
      const res = await client.get<GuildConfig>(`/api/guilds/${guildId}/config`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const { data: defaults } = useQuery<Defaults>({
    queryKey: ['defaults'],
    queryFn: async () => {
      const res = await client.get<Defaults>('/api/defaults');
      return res.data;
    },
    staleTime: Infinity,
  });

  const { data: channels, isLoading: channelsLoading, isError: channelsError } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () => {
      const res = await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`);
      return res.data;
    },
    enabled: !!guildId,
  });

  // Per-channel config — fetched when a channel is selected.
  const { data: channelConfig } = useQuery<ChannelConfig>({
    queryKey: ['channelConfig', guildId, selectedChannel?.id],
    queryFn: async () => {
      const res = await client.get<ChannelConfig>(
        `/api/guilds/${guildId}/channels/${selectedChannel!.id}/config`
      );
      return res.data;
    },
    enabled: !!guildId && !!selectedChannel,
  });

  const guildMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      await client.patch(`/api/guilds/${guildId}/config`, patch);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['config', guildId] });
    },
  });

  const channelMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      await client.patch(
        `/api/guilds/${guildId}/channels/${selectedChannel!.id}/config`,
        patch
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channelConfig', guildId, selectedChannel?.id] });
    },
  });

  function handleTimezoneChange(_: unknown, value: string | null) {
    if (value) guildMutation.mutate({ timezone: value });
  }

  function handleAnnounceChannelChange(_: unknown, value: DiscordChannel | null) {
    // Always send the string ID — never parseInt(). Discord snowflake IDs exceed
    // Number.MAX_SAFE_INTEGER and will be silently mangled by JS if converted to number.
    guildMutation.mutate({ announce_channel_id: value?.id ?? null });
  }

  function handleGuildCutoffChange(e: React.ChangeEvent<HTMLInputElement>) {
    guildMutation.mutate({ context_cutoff: localInputToIso(e.target.value) });
  }

  function handleAlwaysRespondChange(_: React.ChangeEvent<HTMLInputElement>, checked: boolean) {
    channelMutation.mutate({ always_respond: checked });
  }

  function handleChannelCutoffChange(e: React.ChangeEvent<HTMLInputElement>) {
    channelMutation.mutate({ context_cutoff: localInputToIso(e.target.value) });
  }

  if (configLoading) return <Typography color="text.secondary">Loading…</Typography>;
  if (!config) return null;

  return (
    <Stack spacing={4} sx={{ maxWidth: 520 }}>
      {/* Section header */}
      <Typography variant="body2" color="text.secondary">
        Settings for this Discord server. Changes save instantly.
      </Typography>

      {/* ── Server-wide settings ─────────────────────────────────── */}
      <Stack spacing={2.5}>
        <Autocomplete
          size="small"
          fullWidth
          options={TIMEZONES}
          value={config.timezone ?? defaults?.default_timezone ?? 'UTC'}
          onChange={handleTimezoneChange}
          disabled={guildMutation.isPending}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Server Timezone"
              helperText="Used for scheduling, event display, and cron expressions. All times are stored in UTC and converted to this timezone when shown."
            />
          )}
        />

        <Autocomplete
          size="small"
          fullWidth
          options={channels ?? []}
          loading={channelsLoading}
          value={channels?.find((c) => c.id === config.announce_channel_id) ?? null}
          onChange={handleAnnounceChannelChange}
          disabled={guildMutation.isPending}
          getOptionLabel={(ch) => `#${ch.name}`}
          filterOptions={(opts, { inputValue }) => {
            const q = inputValue.toLowerCase();
            return opts.filter((ch) =>
              ch.name.toLowerCase().includes(q) || ch.id.includes(q)
            );
          }}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          renderOption={(props, ch) => (
            <Box component="li" {...props} key={ch.id}>
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                <span>#{ch.name}</span>
                <Typography component="span" variant="caption" color="text.disabled">
                  {ch.id}
                </Typography>
              </Box>
            </Box>
          )}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Bot Channel"
              helperText="The channel where Grug posts announcements and responds to @mentions by default."
            />
          )}
        />

        {/* Global context cutoff */}
        <TextField
          size="small"
          fullWidth
          label="Global Context Cutoff (UTC)"
          type="datetime-local"
          value={isoToLocalInput(config.context_cutoff)}
          onChange={handleGuildCutoffChange}
          disabled={guildMutation.isPending}
          helperText="Grug ignores messages sent before this time, server-wide. Leave blank for no cutoff."
          InputLabelProps={{ shrink: true }}
        />

        {channelsError && (
          <Typography variant="caption" color="warning.main">
            Could not load channels from Discord — check that the bot token is configured correctly.
          </Typography>
        )}

        {guildMutation.isError && (
          <Typography variant="caption" color="error.main">
            Failed to save — please try again.
          </Typography>
        )}
      </Stack>

      <Divider />

      {/* ── Per-channel overrides ─────────────────────────────────── */}
      <Stack spacing={1}>
        <Typography variant="subtitle2" fontWeight={600}>
          Channel Overrides
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Configure a specific channel to override server-wide context settings or
          enable Grug to respond to every message.
        </Typography>
      </Stack>

      <Stack spacing={2.5}>
        <Autocomplete
          size="small"
          fullWidth
          options={channels ?? []}
          loading={channelsLoading}
          value={selectedChannel}
          onChange={(_, ch) => setSelectedChannel(ch)}
          getOptionLabel={(ch) => `#${ch.name}`}
          filterOptions={(opts, { inputValue }) => {
            const q = inputValue.toLowerCase();
            return opts.filter((ch) =>
              ch.name.toLowerCase().includes(q) || ch.id.includes(q)
            );
          }}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          renderOption={(props, ch) => (
            <Box component="li" {...props} key={ch.id}>
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                <span>#{ch.name}</span>
                <Typography component="span" variant="caption" color="text.disabled">
                  {ch.id}
                </Typography>
              </Box>
            </Box>
          )}
          renderInput={(params) => (
            <TextField {...params} label="Select Channel to Configure" />
          )}
        />

        {selectedChannel && (
          <Stack spacing={2} sx={{ pl: 1 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={channelConfig?.always_respond ?? false}
                  onChange={handleAlwaysRespondChange}
                  disabled={channelMutation.isPending || !channelConfig}
                  size="small"
                />
              }
              label={
                <Stack>
                  <Typography variant="body2">Always Respond</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Grug replies to every message in this channel, not just @mentions.
                  </Typography>
                </Stack>
              }
              sx={{ alignItems: 'flex-start', mt: 0.5 }}
            />

            <TextField
              size="small"
              fullWidth
              label="Channel Context Cutoff (UTC)"
              type="datetime-local"
              value={isoToLocalInput(channelConfig?.context_cutoff ?? null)}
              onChange={handleChannelCutoffChange}
              disabled={channelMutation.isPending || !channelConfig}
              helperText="Overrides the server-wide cutoff for this channel only. Leave blank to use server default."
              InputLabelProps={{ shrink: true }}
            />

            {channelMutation.isError && (
              <Typography variant="caption" color="error.main">
                Failed to save channel settings — please try again.
              </Typography>
            )}
          </Stack>
        )}
      </Stack>
    </Stack>
  );
}
