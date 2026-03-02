import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Button,
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

interface ScheduledTask {
  id: number;
  channel_id: number;
  name: string;
  cron_expression: string;
  enabled: boolean;
  last_run: string | null;
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

  const { data: tasks, isLoading } = useQuery<ScheduledTask[]>({
    queryKey: ['personal', 'tasks'],
    queryFn: async () => {
      const res = await client.get<ScheduledTask[]>('/api/personal/tasks');
      return res.data;
    },
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
      <Box>
        <Typography variant="body2" color="text.secondary">
          Recurring tasks Grug was asked to set up during your DMs.
          Ask Grug: "every Monday morning, remind me to update my character sheet".
        </Typography>
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
                {['Name', 'Cron', 'Enabled', 'Last Run', 'Actions'].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {tasks.map((t) => (
                <TableRow key={t.id} hover>
                  <TableCell>{t.name}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {t.cron_expression}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={t.enabled}
                      onChange={() => toggleMutation.mutate({ id: t.id, enabled: !t.enabled })}
                    />
                  </TableCell>
                  <TableCell>
                    {t.last_run ? new Date(t.last_run).toLocaleString() : '—'}
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
