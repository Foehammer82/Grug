import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, Stack, TextField, Typography } from '@mui/material';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface UserDmConfig {
  dm_context_cutoff: string | null; // ISO 8601 UTC
}

/** Convert ISO UTC datetime string to datetime-local input value (e.g. "2026-03-01T20:00"). */
function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  try { return new Date(iso).toISOString().slice(0, 16); }
  catch { return ''; }
}

/** Convert datetime-local input value (UTC assumed) to ISO string, or null if empty. */
function localInputToIso(value: string): string | null {
  if (!value) return null;
  return new Date(value + ':00.000Z').toISOString();
}

export default function PersonalConfigPage() {
  useAuth();
  const qc = useQueryClient();

  const { data: dmConfig } = useQuery<UserDmConfig>({
    queryKey: ['dmConfig'],
    queryFn: async () => {
      const res = await client.get<UserDmConfig>('/api/personal/dm-config');
      return res.data;
    },
  });

  const dmConfigMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      await client.patch('/api/personal/dm-config', patch);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dmConfig'] }),
  });

  function handleDmCutoffChange(e: React.ChangeEvent<HTMLInputElement>) {
    dmConfigMutation.mutate({ dm_context_cutoff: localInputToIso(e.target.value) });
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Stack spacing={1}>
        <Typography variant="subtitle2" fontWeight={600}>
          Context Settings
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Control how far back Grug reads your DM history when responding.
        </Typography>
        <Stack sx={{ maxWidth: 400, pt: 1 }}>
          <TextField
            size="small"
            fullWidth
            label="DM Context Cutoff (UTC)"
            type="datetime-local"
            value={isoToLocalInput(dmConfig?.dm_context_cutoff ?? null)}
            onChange={handleDmCutoffChange}
            disabled={dmConfigMutation.isPending}
            helperText="Grug ignores DM messages sent before this time. Leave blank for no cutoff."
            InputLabelProps={{ shrink: true }}
          />
          {dmConfigMutation.isError && (
            <Typography variant="caption" color="error.main" sx={{ mt: 0.5 }}>
              Failed to save — please try again.
            </Typography>
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
