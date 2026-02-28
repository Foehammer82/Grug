const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export default function LoginPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '1.5rem' }}>
      <h1 style={{ fontSize: '2rem' }}>🪨 Grug Dashboard</h1>
      <p style={{ color: '#555' }}>Sign in with Discord to manage your server.</p>
      <a
        href={`${API_URL}/auth/discord/login`}
        style={{
          background: '#5865F2',
          color: '#fff',
          padding: '0.75rem 2rem',
          borderRadius: 8,
          textDecoration: 'none',
          fontSize: '1.1rem',
          fontWeight: 600,
        }}
      >
        Login with Discord
      </a>
    </div>
  );
}
