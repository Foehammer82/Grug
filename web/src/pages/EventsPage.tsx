import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import {
  Box,
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

interface CalendarEvent {
  id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string | null;
  channel_id: number | null;
}

const HEADER_SX = {
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  fontSize: '0.75rem',
  letterSpacing: '0.05em',
  color: 'text.secondary',
};

export default function EventsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();

  const { data: events, isLoading } = useQuery<CalendarEvent[]>({
    queryKey: ['events', guildId],
    queryFn: async () => {
      const res = await client.get<CalendarEvent[]>(`/api/guilds/${guildId}/events`);
      return res.data;
    },
    enabled: !!guildId,
  });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="body2" color="text.secondary">
          One-off calendar events — sessions, milestones, and other scheduled happenings.
          Ask Grug in chat to create one, e.g. "schedule a session next Friday at 7pm".
        </Typography>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
          <CircularProgress />
        </Box>
      ) : !events || events.length === 0 ? (
        <Typography color="text.secondary">No upcoming events.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                {['Title', 'Description', 'Start', 'End'].map((h) => (
                  <TableCell key={h} sx={HEADER_SX}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id} hover>
                  <TableCell>{e.title}</TableCell>
                  <TableCell>{e.description ?? '—'}</TableCell>
                  <TableCell>{new Date(e.start_time).toLocaleString()}</TableCell>
                  <TableCell>{e.end_time ? new Date(e.end_time).toLocaleString() : '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
