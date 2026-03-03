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
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import DeleteIcon from '@mui/icons-material/Delete';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ScienceIcon from '@mui/icons-material/Science';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { BuiltinRuleSource, RuleSource } from '../types';

// TTRPG system name → display label
const SYSTEM_LABELS: Record<string, string> = {
  dnd5e: 'D&D 5e',
  pf2e: 'Pathfinder 2e',
  coc7: 'Call of Cthulhu 7e',
  mothership: 'Mothership',
  'blades-in-the-dark': 'Blades in the Dark',
  shadowdark: 'Shadowdark',
  shadowrun: 'Shadowrun',
  'warhammer-fantasy': 'Warhammer Fantasy',
  unknown: 'Unknown',
};
const SYSTEMS = Object.keys(SYSTEM_LABELS);

function systemLabel(sys: string | null): string {
  if (!sys) return 'All systems';
  return SYSTEM_LABELS[sys] ?? sys;
}

export default function RuleSourcesPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const { data: builtins, isLoading: builtinsLoading } = useQuery<BuiltinRuleSource[]>({
    queryKey: ['builtins', guildId],
    queryFn: async () =>
      (
        await client.get<BuiltinRuleSource[]>(
          `/api/guilds/${guildId}/rule-sources/builtins`
        )
      ).data,
    enabled: !!guildId,
  });

  const { data: custom, isLoading: customLoading } = useQuery<RuleSource[]>({
    queryKey: ['ruleSources', guildId],
    queryFn: async () =>
      (await client.get<RuleSource[]>(`/api/guilds/${guildId}/rule-sources`)).data,
    enabled: !!guildId,
  });

  // Sort custom sources by sort_order, then created_at as tiebreaker.
  const sortedCustom = [...(custom ?? [])].sort(
    (a, b) => a.sort_order - b.sort_order || a.created_at.localeCompare(b.created_at)
  );

  const toggleBuiltin = useMutation({
    mutationFn: ({ source_id, enabled }: { source_id: string; enabled: boolean }) =>
      client
        .patch(`/api/guilds/${guildId}/rule-sources/builtins/${source_id}`, { enabled })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['builtins', guildId] }),
  });

  const toggleCustom = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      client
        .patch(`/api/guilds/${guildId}/rule-sources/${id}`, { enabled })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ruleSources', guildId] }),
  });

  const reorder = useMutation({
    mutationFn: async ({
      a,
      b,
    }: {
      a: { id: number; sort_order: number };
      b: { id: number; sort_order: number };
    }) => {
      await client.patch(`/api/guilds/${guildId}/rule-sources/${a.id}`, {
        sort_order: a.sort_order,
      });
      await client.patch(`/api/guilds/${guildId}/rule-sources/${b.id}`, {
        sort_order: b.sort_order,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ruleSources', guildId] }),
  });

  const deleteCustom = useMutation({
    mutationFn: (id: number) =>
      client.delete(`/api/guilds/${guildId}/rule-sources/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ruleSources', guildId] }),
  });

  // ── Test source dialog ───────────────────────────────────────────────────
  const [testOpen, setTestOpen] = useState(false);
  const [testLabel, setTestLabel] = useState('');
  const [testSourceId, setTestSourceId] = useState<string | null>(null);
  const [testSourceName, setTestSourceName] = useState<string | null>(null);
  const [testSourceUrl, setTestSourceUrl] = useState<string | null>(null);
  const [testQuery, setTestQuery] = useState('');
  const [testResult, setTestResult] = useState<{ result: string; error: boolean } | null>(null);

  const testMutation = useMutation({
    mutationFn: (q: string) =>
      client
        .post(`/api/guilds/${guildId}/rule-sources/test`, {
          query: q,
          ...(testSourceId ? { source_id: testSourceId } : {}),
          ...(testSourceName ? { source_name: testSourceName } : {}),
          ...(testSourceUrl ? { source_url: testSourceUrl } : {}),
        })
        .then((r) => r.data as { result: string; error: boolean }),
    onSuccess: (data) => setTestResult(data),
  });

  function openTestDialog(opts: {
    label: string;
    source_id?: string;
    source_name?: string;
    source_url?: string;
  }) {
    setTestLabel(opts.label);
    setTestSourceId(opts.source_id ?? null);
    setTestSourceName(opts.source_name ?? null);
    setTestSourceUrl(opts.source_url ?? null);
    setTestQuery('');
    setTestResult(null);
    setTestOpen(true);
  }

  // ── Add custom source dialog ──────────────────────────────────────────────
  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newUrl, setNewUrl] = useState('');
  const [newSystem, setNewSystem] = useState<string | null>(null);
  const [newNotes, setNewNotes] = useState('');

  const createCustom = useMutation({
    mutationFn: () =>
      client
        .post(`/api/guilds/${guildId}/rule-sources`, {
          name: newName,
          url: newUrl,
          system: newSystem,
          notes: newNotes || null,
          enabled: true,
        })
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ruleSources', guildId] });
      setAddOpen(false);
      setNewName('');
      setNewUrl('');
      setNewSystem(null);
      setNewNotes('');
    },
  });

  if (!guildId) return null;

  return (
    <Stack spacing={3} sx={{ maxWidth: 640 }}>
      <Typography variant="body2" color="text.secondary">
        Control which rule lookup sources Grug uses when answering rules questions.
        Built-in sources are always consulted first; custom sources come after in the
        order you set.
      </Typography>

      {/* ── Header with Add button ──────────────────────────────────── */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle2" fontWeight={600}>
          Sources
        </Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
          Add Source
        </Button>
      </Box>

      {/* ── Unified source list ─────────────────────────────────────── */}
      {builtinsLoading || customLoading ? (
        <CircularProgress size={20} />
      ) : (
        <Stack spacing={1}>
          {/* Built-in sources — always first, fixed order, cannot be deleted */}
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
              {/* No reorder arrows — built-ins have fixed priority */}
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
                      onClick={() =>
                        openTestDialog({ label: src.name, source_id: src.source_id })
                      }
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

          {/* Separator between built-ins and custom */}
          {(builtins ?? []).length > 0 && sortedCustom.length > 0 && <Divider />}

          {/* Custom sources — ordered by sort_order, reorderable */}
          {sortedCustom.map((src, idx) => (
            <Box
              key={src.id}
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 1,
                p: 1.5,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                opacity: src.enabled ? 1 : 0.5,
              }}
            >
              {/* Up / down reorder arrows */}
              <Stack spacing={0}>
                <Tooltip title="Move up">
                  <span>
                    <IconButton
                      size="small"
                      disabled={idx === 0 || reorder.isPending}
                      onClick={() => {
                        const above = sortedCustom[idx - 1];
                        reorder.mutate({
                          a: { id: src.id, sort_order: above.sort_order },
                          b: { id: above.id, sort_order: src.sort_order },
                        });
                      }}
                    >
                      <ArrowUpwardIcon fontSize="inherit" />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title="Move down">
                  <span>
                    <IconButton
                      size="small"
                      disabled={idx === sortedCustom.length - 1 || reorder.isPending}
                      onClick={() => {
                        const below = sortedCustom[idx + 1];
                        reorder.mutate({
                          a: { id: src.id, sort_order: below.sort_order },
                          b: { id: below.id, sort_order: src.sort_order },
                        });
                      }}
                    >
                      <ArrowDownwardIcon fontSize="inherit" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>

              <Stack spacing={0.5} sx={{ flex: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="body2" fontWeight={600}>
                    {src.name}
                  </Typography>
                  <Chip label="Custom" size="small" variant="outlined" />
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
                      onClick={() =>
                        openTestDialog({
                          label: src.name,
                          source_name: src.name,
                          source_url: src.url,
                        })
                      }
                    >
                      <ScienceIcon fontSize="inherit" />
                    </IconButton>
                  </Tooltip>
                </Box>
                {src.notes && (
                  <Typography variant="caption" color="text.secondary">
                    {src.notes}
                  </Typography>
                )}
                <Typography
                  variant="caption"
                  color="text.disabled"
                  sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}
                >
                  {src.url}
                </Typography>
              </Stack>

              <Stack spacing={0.5} sx={{ alignItems: 'center', pt: 0.25 }}>
                <Switch
                  checked={src.enabled}
                  size="small"
                  disabled={toggleCustom.isPending}
                  onChange={(_, checked) =>
                    toggleCustom.mutate({ id: src.id, enabled: checked })
                  }
                />
                <Tooltip title="Delete source">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => deleteCustom.mutate(src.id)}
                    disabled={deleteCustom.isPending}
                  >
                    <DeleteIcon fontSize="inherit" />
                  </IconButton>
                </Tooltip>
              </Stack>
            </Box>
          ))}

          {sortedCustom.length === 0 && (
            <Typography variant="body2" color="text.disabled" sx={{ fontStyle: 'italic' }}>
              No custom sources yet. Click &quot;Add Source&quot; to add one.
            </Typography>
          )}
        </Stack>
      )}

      {/* ── Test source dialog ─────────────────────────────────────── */}
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

      {/* ── Add custom source dialog ────────────────────────────────── */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Custom Rule Source</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name"
              size="small"
              fullWidth
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Kobold Press Tome of Beasts"
            />
            <TextField
              label="URL"
              size="small"
              fullWidth
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder="https://…"
            />
            <Autocomplete
              size="small"
              fullWidth
              options={SYSTEMS}
              value={newSystem}
              onChange={(_, v) => setNewSystem(v)}
              getOptionLabel={(s) => systemLabel(s)}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="System (optional)"
                  helperText="Leave blank if this source covers multiple systems."
                />
              )}
            />
            <TextField
              label="Notes (optional)"
              size="small"
              fullWidth
              multiline
              rows={2}
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              placeholder="Any additional context for Grug…"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!newName || !newUrl || createCustom.isPending}
            onClick={() => createCustom.mutate()}
          >
            Add
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
