import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import PollingIndicator from '../components/PollingIndicator';

interface ScheduledTask {
  id: number;
  channel_id: number;
  type: 'once' | 'recurring';
  name: string | null;
  prompt: string;
  fire_at: string | null;
  cron_expression: string | null;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
  created_at: string;
}

const HEADER_SX = {
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  fontSize: '0.75rem',
  letterSpacing: '0.05em',
  color: 'text.secondary',
};

export default function PersonalTasksPage() {
  useAuth();
  const qc = useQueryClient();

  const POLL_MS = 15_000;

  const { data: tasks, isLoading, dataUpdatedAt } = useQuery<ScheduledTask[]>({
    queryKey: ['personal', 'tasks'],
    queryFn: async () => {
      const res = await client.get<ScheduledTask[]>('/api/personal/tasks');
      return res.data;
    },
    refetchInterval: POLL_MS,
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) => {
      await client.patch(`/api/personal/tasks/${id}`, { enabled });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personal', 'tasks'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/personal/tasks/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personal', 'tasks'] }),
  });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Scheduled tasks Grug was asked to set up during your DMs — one-off reminders
          and recurring automated prompts.
          Ask Grug: "remind me to update my spell slots in 10 minutes" or
          "every Monday morning, remind me to update my character sheet".
        </Typography>
        <PollingIndicator intervalMs={POLL_MS} dataUpdatedAt={dataUpdatedAt} />
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !tasks || tasks.length === 0 ? (
        <Typography color="text.secondary">No personal scheduled tasks.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Type', 'Name / Prompt', 'Schedule', 'Enabled', 'Status', 'Next Run', 'Actions'].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {tasks.map((t) => (
                <TableRow key={t.id} hover>
                  <TableCell>
                    <Chip
                      label={t.type === 'once' ? 'Once' : 'Recurring'}
                      size="small"
                      color={t.type === 'once' ? 'info' : 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 260, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {t.name ?? t.prompt.slice(0, 60)}
                  </TableCell>
                  <TableCell>
                    {t.type === 'once' ? (
                      <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                        {t.fire_at ? new Date(t.fire_at).toLocaleString() : '—'}
                      </Typography>
                    ) : (
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {t.cron_expression ?? '—'}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={t.enabled}
                      onChange={() => toggleMutation.mutate({ id: t.id, enabled: !t.enabled })}
                    />
                  </TableCell>
                  <TableCell>
                    {t.type === 'once' ? (
                      <Chip
                        label={t.last_run ? 'Fired' : 'Pending'}
                        size="small"
                        color={t.last_run ? 'default' : 'primary'}
                        variant={t.last_run ? 'outlined' : 'filled'}
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        {t.last_run ? new Date(t.last_run).toLocaleString() : '—'}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    <Typography variant="body2" color="text.secondary">
                      {t.next_run ? new Date(t.next_run).toLocaleString() : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      color="error"
                      variant="outlined"
                      onClick={() => deleteMutation.mutate(t.id)}
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
