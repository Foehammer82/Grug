import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import NavBar from '../components/NavBar';
import { useAuth } from '../hooks/useAuth';

interface ScheduledTask {
  id: number;
  guild_id: number;
  channel_id: number;
  name: string;
  prompt: string;
  cron_expression: string;
  enabled: boolean;
  last_run: string | null;
  created_at: string;
}

const thStyle: React.CSSProperties = { padding: '0.5rem 0.75rem', textAlign: 'left', background: '#f0f0f0' };
const tdStyle: React.CSSProperties = { padding: '0.5rem 0.75rem', borderBottom: '1px solid #eee' };

export default function TasksPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const { data: tasks, isLoading } = useQuery<ScheduledTask[]>({
    queryKey: ['tasks', guildId],
    queryFn: async () => {
      const res = await client.get<ScheduledTask[]>(`/api/guilds/${guildId}/tasks`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) => {
      await client.patch(`/api/guilds/${guildId}/tasks/${id}`, { enabled });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks', guildId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/tasks/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks', guildId] }),
  });

  return (
    <>
      <NavBar />
      <main style={{ padding: '2rem' }}>
        <h2>Scheduled Tasks</h2>
        {isLoading && <p>Loading…</p>}
        {tasks && tasks.length === 0 && <p>No scheduled tasks.</p>}
        {tasks && tasks.length > 0 && (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                {['Name', 'Cron', 'Enabled', 'Last Run', 'Actions'].map((h) => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id}>
                  <td style={tdStyle}>{t.name}</td>
                  <td style={tdStyle}><code>{t.cron_expression}</code></td>
                  <td style={tdStyle}>
                    <input
                      type="checkbox"
                      checked={t.enabled}
                      onChange={() => toggleMutation.mutate({ id: t.id, enabled: !t.enabled })}
                    />
                  </td>
                  <td style={tdStyle}>{t.last_run ? new Date(t.last_run).toLocaleString() : '—'}</td>
                  <td style={tdStyle}>
                    <button
                      onClick={() => deleteMutation.mutate(t.id)}
                      style={{ background: '#e53e3e', color: '#fff', border: 'none', borderRadius: 4, padding: '0.25rem 0.75rem', cursor: 'pointer' }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}
