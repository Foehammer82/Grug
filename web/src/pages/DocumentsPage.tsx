import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import client from '../api/client';
import NavBar from '../components/NavBar';
import { useAuth } from '../hooks/useAuth';

interface Document {
  id: number;
  filename: string;
  description: string | null;
  chunk_count: number;
  created_at: string;
}

const thStyle: React.CSSProperties = { padding: '0.5rem 0.75rem', textAlign: 'left', background: '#f0f0f0' };
const tdStyle: React.CSSProperties = { padding: '0.5rem 0.75rem', borderBottom: '1px solid #eee' };

export default function DocumentsPage() {
  useAuth();
  const { guildId } = useParams<{ guildId: string }>();
  const qc = useQueryClient();

  const { data: docs, isLoading } = useQuery<Document[]>({
    queryKey: ['documents', guildId],
    queryFn: async () => {
      const res = await client.get<Document[]>(`/api/guilds/${guildId}/documents`);
      return res.data;
    },
    enabled: !!guildId,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/api/guilds/${guildId}/documents/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', guildId] }),
  });

  return (
    <>
      <NavBar />
      <main style={{ padding: '2rem' }}>
        <h2>Indexed Documents</h2>
        {isLoading && <p>Loading…</p>}
        {docs && docs.length === 0 && <p>No documents indexed.</p>}
        {docs && docs.length > 0 && (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                {['Filename', 'Description', 'Chunks', 'Added', 'Actions'].map((h) => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td style={tdStyle}>{d.filename}</td>
                  <td style={tdStyle}>{d.description ?? '—'}</td>
                  <td style={tdStyle}>{d.chunk_count}</td>
                  <td style={tdStyle}>{new Date(d.created_at).toLocaleDateString()}</td>
                  <td style={tdStyle}>
                    <button
                      onClick={() => deleteMutation.mutate(d.id)}
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
