import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import type { BuiltinRuleSource } from '../types';

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

  const toggleBuiltin = useMutation({
    mutationFn: ({ source_id, enabled }: { source_id: string; enabled: boolean }) =>
      client
        .patch(`/api/guilds/${guildId}/rule-sources/builtins/${source_id}`, { enabled })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['builtins', guildId] }),
  });

  // ── Test source dialog ───────────────────────────────────────────────────
  const [testOpen, setTestOpen] = useState(false);
  const [testLabel, setTestLabel] = useState('');
  const [testSourceId, setTestSourceId] = useState<string | null>(null);
  const [testQuery, setTestQuery] = useState('');
  const [testResult, setTestResult] = useState<{ result: string; error: boolean } | null>(null);

  const testMutation = useMutation({
    mutationFn: (q: string) =>
      client
        .post(`/api/guilds/${guildId}/rule-sources/test`, {
          query: q,
          source_id: testSourceId,
        })
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

  if (!guildId) return null;

  return (
    <Stack spacing={3} sx={{ maxWidth: 640 }}>
      <Typography variant="body2" color="text.secondary">
        Control which rule lookup sources Grug uses when answering rules questions.
      </Typography>

      <Typography variant="subtitle2" fontWeight={600}>
        Sources
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
    </Stack>
  );
}
