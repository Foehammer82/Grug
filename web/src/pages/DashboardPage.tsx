import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import client from '../api/client';
import NavBar from '../components/NavBar';
import { useAuth } from '../hooks/useAuth';

interface Guild {
  id: string;
  name: string;
  icon: string | null;
}

export default function DashboardPage() {
  useAuth();

  const { data: guilds, isLoading } = useQuery<Guild[]>({
    queryKey: ['guilds'],
    queryFn: async () => {
      const res = await client.get<Guild[]>('/api/guilds');
      return res.data;
    },
  });

  return (
    <>
      <NavBar />
      <main style={{ padding: '2rem' }}>
        <h2>Your Servers</h2>
        {isLoading && <p>Loading…</p>}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginTop: '1rem' }}>
          {guilds?.map((g) => {
            const iconUrl = g.icon
              ? `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png?size=64`
              : null;
            return (
              <Link
                key={g.id}
                to={`/guilds/${g.id}/config`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '1rem 1.5rem',
                  border: '1px solid #ddd',
                  borderRadius: 8,
                  textDecoration: 'none',
                  color: 'inherit',
                  background: '#fafafa',
                  minWidth: 200,
                }}
              >
                {iconUrl ? (
                  <img src={iconUrl} alt={g.name} style={{ width: 48, height: 48, borderRadius: '50%' }} />
                ) : (
                  <span style={{ fontSize: 32 }}>🖥️</span>
                )}
                <span style={{ fontWeight: 600 }}>{g.name}</span>
              </Link>
            );
          })}
          {guilds?.length === 0 && <p>No shared servers found. Make sure Grug is in your server!</p>}
        </div>
      </main>
    </>
  );
}
