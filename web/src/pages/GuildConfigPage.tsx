import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Autocomplete,
  Box,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface GuildConfig {
  guild_id: number;
  timezone: string;
  // Returned as a string to preserve Discord snowflake precision (> MAX_SAFE_INTEGER)
  announce_channel_id: string | null;
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

  const mutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      await client.patch(`/api/guilds/${guildId}/config`, patch);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['config', guildId] });
    },
  });

  function handleTimezoneChange(_: unknown, value: string | null) {
    if (value) mutation.mutate({ timezone: value });
  }

  function handleChannelChange(_: unknown, value: DiscordChannel | null) {
    // Always send the string ID — never parseInt(). Discord snowflake IDs exceed
    // Number.MAX_SAFE_INTEGER and will be silently mangled by JS if converted to number.
    mutation.mutate({ announce_channel_id: value?.id ?? null });
  }

  if (configLoading) return <Typography color="text.secondary">Loading…</Typography>;
  if (!config) return null;

  return (
    <Stack spacing={4} sx={{ maxWidth: 520 }}>
      {/* Section header */}
      <Typography variant="body2" color="text.secondary">
        Settings for this Discord server. Changes save instantly.
      </Typography>

      {/* Live-edit fields */}
      <Stack spacing={2.5}>
        <Autocomplete
          size="small"
          fullWidth
          options={TIMEZONES}
          value={config.timezone ?? defaults?.default_timezone ?? 'UTC'}
          onChange={handleTimezoneChange}
          disabled={mutation.isPending}
          renderInput={(params) => <TextField {...params} label="Server Timezone" />}
        />

        <Autocomplete
          size="small"
          fullWidth
          options={channels ?? []}
          loading={channelsLoading}
          value={channels?.find((c) => c.id === config.announce_channel_id) ?? null}
          onChange={handleChannelChange}
          disabled={mutation.isPending}
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
            <TextField {...params} label="Bot Channel" />
          )}
        />

        {channelsError && (
          <Typography variant="caption" color="warning.main">
            Could not load channels from Discord — check that the bot token is configured correctly.
          </Typography>
        )}

        {mutation.isError && (
          <Typography variant="caption" color="error.main">
            Failed to save — please try again.
          </Typography>
        )}
      </Stack>
    </Stack>
  );
}
