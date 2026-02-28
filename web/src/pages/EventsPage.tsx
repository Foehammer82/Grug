import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import NavBar from '../components/NavBar';
import { useAuth } from '../hooks/useAuth';

interface CalendarEvent {
  id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string | null;
  channel_id: number | null;
}

const thStyle: React.CSSProperties = { padding: '0.5rem 0.75rem', textAlign: 'left', background: '#f0f0f0' };
const tdStyle: React.CSSProperties = { padding: '0.5rem 0.75rem', borderBottom: '1px solid #eee' };

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
    <>
      <NavBar />
      <main style={{ padding: '2rem' }}>
        <h2>Upcoming Events</h2>
        {isLoading && <p>Loading…</p>}
        {events && events.length === 0 && <p>No upcoming events.</p>}
        {events && events.length > 0 && (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                {['Title', 'Description', 'Start', 'End'].map((h) => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td style={tdStyle}>{e.title}</td>
                  <td style={tdStyle}>{e.description ?? '—'}</td>
                  <td style={tdStyle}>{new Date(e.start_time).toLocaleString()}</td>
                  <td style={tdStyle}>{e.end_time ? new Date(e.end_time).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}
