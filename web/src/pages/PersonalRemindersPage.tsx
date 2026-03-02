import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
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

interface Reminder {
  id: number;
  user_id: number;
  channel_id: number;
  message: string;
  remind_at: string;
  sent: boolean;
  created_at: string;
}

const HEADER_SX = {
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  fontSize: '0.75rem',
  letterSpacing: '0.05em',
  color: 'text.secondary',
};

export default function PersonalRemindersPage() {
  useAuth();
  const qc = useQueryClient();

  const { data: reminders, isLoading, dataUpdatedAt } = useQuery<Reminder[]>({
    queryKey: ['personal', 'reminders'],
    queryFn: async () => {
      const res = await client.get<Reminder[]>('/api/personal/reminders');
      return res.data;
    },
    refetchInterval: 15_000,
  });

  const POLL_MS = 15_000;

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/personal/reminders/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['personal', 'reminders'] }),
  });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          One-off reminders Grug was asked to set during your DMs.
          Ask Grug directly: "remind me to prep my character sheet in 30 minutes".
        </Typography>
        <PollingIndicator intervalMs={POLL_MS} dataUpdatedAt={dataUpdatedAt} />
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !reminders || reminders.length === 0 ? (
        <Typography color="text.secondary">No personal reminders.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Message', 'Fire At', 'Status', 'Created', ''].map((h, i) => (
                  <TableCell key={i} sx={HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {reminders.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell sx={{ maxWidth: 320, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {r.message}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {new Date(r.remind_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={r.sent ? 'Sent' : 'Pending'}
                      size="small"
                      color={r.sent ? 'default' : 'primary'}
                      variant={r.sent ? 'outlined' : 'filled'}
                    />
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap', color: 'text.secondary' }}>
                    {new Date(r.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      color="error"
                      variant="outlined"
                      onClick={() => deleteMutation.mutate(r.id)}
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
