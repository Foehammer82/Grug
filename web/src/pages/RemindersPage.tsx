import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import {
  Box,
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

export default function RemindersPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();

  const { data: reminders, isLoading, dataUpdatedAt } = useQuery<Reminder[]>({
    queryKey: ['reminders', guildId],
    queryFn: async () => {
      const res = await client.get<Reminder[]>(`/api/guilds/${guildId}/reminders`);
      return res.data;
    },
    enabled: !!guildId,
    refetchInterval: 15_000,
  });

  const POLL_MS = 15_000;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          One-off reminders Grug has been asked to send. These fire once at a specific time —
          ask Grug in chat to set one, e.g. "remind me to check my spell slots in 10 minutes".
        </Typography>
        <PollingIndicator intervalMs={POLL_MS} dataUpdatedAt={dataUpdatedAt} />
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !reminders || reminders.length === 0 ? (
        <Typography color="text.secondary">No reminders set.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Message', 'Fire At', 'Status', 'Created'].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
