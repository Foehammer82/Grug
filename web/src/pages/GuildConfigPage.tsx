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
  IconButton,
  Slider,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ScienceIcon from '@mui/icons-material/Science';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { BuiltinRuleSource, DiscordChannel, GuildConfig } from '../types';

interface ChannelConfig {
  channel_id: string;
  guild_id: string;
  auto_respond: boolean;
  auto_respond_threshold: number;
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
  pf2e: 'Pathfinder 2E',
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
  const [filter, setFilter] = useState('');
  // Tracks slider values while user is dragging (keyed by channel_id).
  const [pendingThresholds, setPendingThresholds] = useState<Record<string, number>>({});

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

  const {
    data: channelConfigs,
    isLoading: configsLoading,
    isError: configsError,
  } = useQuery<ChannelConfig[]>({
    queryKey: ['channelConfigs', guildId],
    queryFn: async () =>
      (await client.get<ChannelConfig[]>(`/api/guilds/${guildId}/channels/configs`)).data,
    enabled: !!guildId,
  });

  const configMap = useMemo(
    () => new Map((channelConfigs ?? []).map((c) => [c.channel_id, c])),
    [channelConfigs],
  );

  const channelMutation = useMutation({
    mutationFn: async ({
      channelId,
      patch,
    }: {
      channelId: string;
      patch: Record<string, unknown>;
    }) => {
      await client.patch(`/api/guilds/${guildId}/channels/${channelId}/config`, patch);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['channelConfigs', guildId] }),
  });

  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return (channels ?? []).filter((ch) => ch.name.toLowerCase().includes(q));
  }, [channels, filter]);

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Configure per-channel settings. Changes save instantly.
      </Typography>

      {channelsError && (
        <Typography variant="caption" color="warning.main">
          Could not load channels from Discord.
        </Typography>
      )}

      {configsError && (
        <Typography variant="caption" color="warning.main">
          Could not load channel settings — displayed values may not reflect actual config.
        </Typography>
      )}

      {channelsLoading || configsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
          <CircularProgress size={20} />
        </Box>
      ) : (
        <>
          <TextField
            size="small"
            label="Filter channels"
            placeholder="e.g. general"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            sx={{ maxWidth: 320 }}
          />
          <TableContainer
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              maxHeight: 420,
            }}
          >
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Channel</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap', minWidth: 200 }}>
                    Auto Respond
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={2}>
                      <Typography variant="body2" color="text.secondary">
                        No channels found.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((ch) => {
                    const cfg = configMap.get(ch.id);
                    const autoRespond = cfg?.auto_respond ?? false;
                    const threshold =
                      pendingThresholds[ch.id] ?? cfg?.auto_respond_threshold ?? 0.1;
                    return (
                      <TableRow key={ch.id} hover>
                        <TableCell>
                          <Typography variant="body2">#{ch.name}</Typography>
                        </TableCell>
                        <TableCell>
                          <Stack spacing={0.5}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Tooltip
                                title={
                                  autoRespond
                                    ? 'Grug considers responding to every message here'
                                    : 'Grug only replies to @mentions'
                                }
                              >
                                <Switch
                                  size="small"
                                  checked={autoRespond}
                                  onChange={(_, checked) =>
                                    channelMutation.mutate({
                                      channelId: ch.id,
                                      patch: { auto_respond: checked },
                                    })
                                  }
                                  disabled={channelMutation.isPending || configsError}
                                />
                              </Tooltip>
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ minWidth: 28 }}
                              >
                                {autoRespond ? 'On' : 'Off'}
                              </Typography>
                            </Box>
                            {autoRespond && (
                              <Box
                                sx={{
                                  pl: 0.5,
                                  pr: 1,
                                  pt: 1,
                                  pb: 1,
                                  maxWidth: 380,
                                }}
                              >
                                <Slider
                                  size="small"
                                  min={0}
                                  max={0.1}
                                  step={null}
                                  value={threshold}
                                  marks={[
                                    { value: 0, label: 'Always' },
                                    { value: 0.25, label: 'Sometimes' },
                                    { value: 0.5, label: 'Selective' },
                                  ]}
                                  valueLabelDisplay="off"
                                  onChange={(_, v) =>
                                    setPendingThresholds((prev) => ({
                                      ...prev,
                                      [ch.id]: v as number,
                                    }))
                                  }
                                  onChangeCommitted={(_, v) => {
                                    setPendingThresholds((prev) => {
                                      const next = { ...prev };
                                      delete next[ch.id];
                                      return next;
                                    });
                                    channelMutation.mutate({
                                      channelId: ch.id,
                                      patch: { auto_respond_threshold: v },
                                    });
                                  }}
                                  disabled={channelMutation.isPending || configsError}
                                  sx={{ flex: 1, mt: 2, mb: 2 }}
                                />
                              </Box>
                            )}
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
          {channelMutation.isError && (
            <Typography variant="caption" color="error.main">
              Failed to save channel settings — please try again.
            </Typography>
          )}
        </>
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
