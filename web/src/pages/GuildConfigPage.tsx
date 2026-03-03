import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ScienceIcon from '@mui/icons-material/Science';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { isoToLocalInput, localInputToIso } from '../types';
import type { BuiltinRuleSource, DiscordChannel, GuildConfig } from '../types';

interface ChannelConfig {
  channel_id: string;
  guild_id: string;
  always_respond: boolean;
  context_cutoff: string | null;
  updated_at: string;
}

interface Defaults {
  default_timezone: string;
}

const TIMEZONES: string[] = Intl.supportedValuesOf('timeZone');

// Supported TTRPG systems shown as autocomplete suggestions.
// Users may still type any free-form value — these are just quick-picks.
const SYSTEM_LABELS: Record<string, string> = {
  dnd5e: 'D&D 5e',
  pf2e: 'Pathfinder 2e',
};
const SYSTEMS = Object.keys(SYSTEM_LABELS);

function systemLabel(sys: string | null): string {
  if (!sys) return 'All systems';
  return SYSTEM_LABELS[sys] ?? sys;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-panel: Server Settings
// ─────────────────────────────────────────────────────────────────────────────

function ServerSettingsPanel({ guildId }: { guildId: string }) {
  const qc = useQueryClient();

  const { data: config, isLoading } = useQuery<GuildConfig>({
    queryKey: ['config', guildId],
    queryFn: async () => (await client.get<GuildConfig>(`/api/guilds/${guildId}/config`)).data,
    enabled: !!guildId,
  });
  const { data: defaults } = useQuery<Defaults>({
    queryKey: ['defaults'],
    queryFn: async () => (await client.get<Defaults>('/api/defaults')).data,
    staleTime: Infinity,
  });
  const {
    data: channels,
    isLoading: channelsLoading,
    isError: channelsError,
  } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () =>
      (await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`)).data,
    enabled: !!guildId,
  });

  const mutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      await client.patch(`/api/guilds/${guildId}/config`, patch);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config', guildId] }),
  });

  if (isLoading) return <Typography color="text.secondary">Loading…</Typography>;
  if (!config) return null;

  return (
    <Stack spacing={2.5} sx={{ maxWidth: 520 }}>
      <Typography variant="body2" color="text.secondary">
        Server-wide settings. Changes save instantly.
      </Typography>

      <Autocomplete
        size="small"
        fullWidth
        options={TIMEZONES}
        value={config.timezone ?? defaults?.default_timezone ?? 'UTC'}
        onChange={(_, v) => v && mutation.mutate({ timezone: v })}
        disabled={mutation.isPending}
        renderInput={(params) => (
          <TextField
            {...params}
            label="Server Timezone"
            helperText="Used for scheduling, event display, and cron expressions."
          />
        )}
      />

      <Autocomplete
        size="small"
        fullWidth
        options={channels ?? []}
        loading={channelsLoading}
        value={channels?.find((c) => c.id === config.announce_channel_id) ?? null}
        onChange={(_, ch) =>
          mutation.mutate({ announce_channel_id: ch?.id ?? null })
        }
        disabled={mutation.isPending}
        getOptionLabel={(ch) => `#${ch.name}`}
        filterOptions={(opts, { inputValue }) => {
          const q = inputValue.toLowerCase();
          return opts.filter(
            (ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q)
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
            helperText="Where Grug posts announcements and responds by default."
          />
        )}
      />

      <TextField
        size="small"
        fullWidth
        label="Global Context Cutoff (UTC)"
        type="datetime-local"
        value={isoToLocalInput(config.context_cutoff)}
        onChange={(e) => mutation.mutate({ context_cutoff: localInputToIso(e.target.value) })}
        disabled={mutation.isPending}
        helperText="Grug ignores messages sent before this time, server-wide. Leave blank for no cutoff."
        InputLabelProps={{ shrink: true }}
      />

      <Autocomplete
        size="small"
        fullWidth
        freeSolo
        options={SYSTEMS}
        value={config.default_ttrpg_system ?? ''}
        onChange={(_, v) => mutation.mutate({ default_ttrpg_system: (v as string) || null })}
        onInputChange={(_, _v, reason) => {
          if (reason === 'clear') mutation.mutate({ default_ttrpg_system: null });
        }}
        disabled={mutation.isPending}
        getOptionLabel={(v) => systemLabel(v)}
        renderInput={(params) => (
          <TextField
            {...params}
            label="Default TTRPG System"
            helperText="Grug uses this when looking up rules and no specific system is mentioned. Leave blank for all systems."
          />
        )}
      />

      {channelsError && (
        <Typography variant="caption" color="warning.main">
          Could not load channels from Discord — check that the bot token is configured.
        </Typography>
      )}
      {mutation.isError && (
        <Typography variant="caption" color="error.main">
          Failed to save — please try again.
        </Typography>
      )}
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-panel: Channel Settings
// ─────────────────────────────────────────────────────────────────────────────

function ChannelSettingsPanel({ guildId }: { guildId: string }) {
  const qc = useQueryClient();
  const [selectedChannel, setSelectedChannel] = useState<DiscordChannel | null>(null);

  const {
    data: channels,
    isLoading: channelsLoading,
    isError: channelsError,
  } = useQuery<DiscordChannel[]>({
    queryKey: ['channels', guildId],
    queryFn: async () =>
      (await client.get<DiscordChannel[]>(`/api/guilds/${guildId}/channels`)).data,
    enabled: !!guildId,
  });

  const { data: channelConfig } = useQuery<ChannelConfig>({
    queryKey: ['channelConfig', guildId, selectedChannel?.id],
    queryFn: async () =>
      (
        await client.get<ChannelConfig>(
          `/api/guilds/${guildId}/channels/${selectedChannel!.id}/config`
        )
      ).data,
    enabled: !!guildId && !!selectedChannel,
  });

  const channelMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      await client.patch(
        `/api/guilds/${guildId}/channels/${selectedChannel!.id}/config`,
        patch
      );
    },
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ['channelConfig', guildId, selectedChannel?.id],
      }),
  });

  return (
    <Stack spacing={2.5} sx={{ maxWidth: 520 }}>
      <Typography variant="body2" color="text.secondary">
        Override server-wide settings for a specific channel.
      </Typography>

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
          return opts.filter(
            (ch) => ch.name.toLowerCase().includes(q) || ch.id.includes(q)
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

      {channelsError && (
        <Typography variant="caption" color="warning.main">
          Could not load channels from Discord.
        </Typography>
      )}

      {selectedChannel && (
        <Stack spacing={2} sx={{ pl: 1 }}>
          <FormControlLabel
            control={
              <Switch
                checked={channelConfig?.always_respond ?? false}
                onChange={(_, checked) =>
                  channelMutation.mutate({ always_respond: checked })
                }
                disabled={channelMutation.isPending || !channelConfig}
                size="small"
              />
            }
            label={
              <Stack>
                <Typography variant="body2">Always Respond</Typography>
                <Typography variant="caption" color="text.secondary">
                  Grug replies to every message here, not just @mentions.
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
            onChange={(e) =>
              channelMutation.mutate({
                context_cutoff: localInputToIso(e.target.value),
              })
            }
            disabled={channelMutation.isPending || !channelConfig}
            helperText="Overrides server-wide cutoff for this channel. Leave blank to use the server default."
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
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-panel: Rule Sources
// ─────────────────────────────────────────────────────────────────────────────

function RuleSourcesPanel({ guildId }: { guildId: string }) {
  const qc = useQueryClient();

  const { data: builtins, isLoading: builtinsLoading } = useQuery<BuiltinRuleSource[]>({
    queryKey: ['builtins', guildId],
    queryFn: async () =>
      (await client.get<BuiltinRuleSource[]>(`/api/guilds/${guildId}/rule-sources/builtins`)).data,
    enabled: !!guildId,
  });

  const toggleBuiltin = useMutation({
    mutationFn: ({ source_id, enabled }: { source_id: string; enabled: boolean }) =>
      client
        .patch(`/api/guilds/${guildId}/rule-sources/builtins/${source_id}`, { enabled })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['builtins', guildId] }),
  });

  const [testOpen, setTestOpen] = useState(false);
  const [testLabel, setTestLabel] = useState('');
  const [testSourceId, setTestSourceId] = useState<string | null>(null);
  const [testQuery, setTestQuery] = useState('');
  const [testResult, setTestResult] = useState<{ result: string; error: boolean } | null>(null);

  const testMutation = useMutation({
    mutationFn: (q: string) =>
      client
        .post(`/api/guilds/${guildId}/rule-sources/test`, { query: q, source_id: testSourceId })
        .then((r) => r.data as { result: string; error: boolean }),
    onSuccess: (data) => setTestResult(data),
  });

  function openTestDialog(opts: { label: string; source_id: string }) {
    setTestLabel(opts.label);
    setTestSourceId(opts.source_id);
    setTestQuery('');
    setTestResult(null);
    setTestOpen(true);
  }

  return (
    <Stack spacing={2} sx={{ maxWidth: 520 }}>
      <Typography variant="body2" color="text.secondary">
        Control which rule lookup sources Grug uses when answering rules questions.
      </Typography>

      {builtinsLoading ? (
        <CircularProgress size={20} />
      ) : (
        <Stack spacing={1}>
          {(builtins ?? []).map((src) => (
            <Box
              key={src.source_id}
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 2,
                p: 1.5,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                opacity: src.enabled ? 1 : 0.5,
              }}
            >
              <Stack spacing={0.5} sx={{ flex: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="body2" fontWeight={600}>
                    {src.name}
                  </Typography>
                  <Chip label="Built-in" size="small" color="primary" variant="outlined" />
                  {src.system && (
                    <Chip label={systemLabel(src.system)} size="small" variant="outlined" />
                  )}
                  <Tooltip title="Open source URL">
                    <IconButton
                      size="small"
                      component="a"
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <OpenInNewIcon fontSize="inherit" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Test source">
                    <IconButton
                      size="small"
                      onClick={() => openTestDialog({ label: src.name, source_id: src.source_id })}
                    >
                      <ScienceIcon fontSize="inherit" />
                    </IconButton>
                  </Tooltip>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {src.description}
                </Typography>
              </Stack>
              <Switch
                checked={src.enabled}
                size="small"
                disabled={toggleBuiltin.isPending}
                onChange={(_, checked) =>
                  toggleBuiltin.mutate({ source_id: src.source_id, enabled: checked })
                }
              />
            </Box>
          ))}
        </Stack>
      )}

      <Dialog open={testOpen} onClose={() => setTestOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Test: {testLabel}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Test query"
              placeholder="e.g. Rogue, Fireball, Grapple…"
              value={testQuery}
              onChange={(e) => setTestQuery(e.target.value)}
              fullWidth
              size="small"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && testQuery.trim()) testMutation.mutate(testQuery.trim());
              }}
            />
            <Button
              variant="contained"
              disabled={!testQuery.trim() || testMutation.isPending}
              onClick={() => testMutation.mutate(testQuery.trim())}
            >
              {testMutation.isPending ? 'Running…' : 'Run Test'}
            </Button>
            {testResult && (
              <Box
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  bgcolor: testResult.error ? 'error.dark' : 'background.paper',
                  border: 1,
                  borderColor: testResult.error ? 'error.main' : 'divider',
                  borderRadius: 1,
                  p: 2,
                  maxHeight: 400,
                  overflowY: 'auto',
                }}
              >
                {testResult.result || '(no output)'}
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTestOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main GuildConfigPage — stacked server + channel settings
// ─────────────────────────────────────────────────────────────────────────────

export default function GuildConfigPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  if (!guildId) return null;

  return (
    <Stack spacing={4}>
      <Box>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Server Settings
        </Typography>
        <ServerSettingsPanel guildId={guildId} />
      </Box>
      <Divider />
      <Box>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Channel Settings
        </Typography>
        <ChannelSettingsPanel guildId={guildId} />
      </Box>
      <Divider />
      <Box>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Rule Sources
        </Typography>
        <RuleSourcesPanel guildId={guildId} />
      </Box>
    </Stack>
  );
}
