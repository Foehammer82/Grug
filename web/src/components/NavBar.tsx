import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';

const navStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '1rem',
  padding: '0.75rem 1.5rem',
  background: '#5865F2',
  color: '#fff',
};

const linkStyle: React.CSSProperties = { color: '#fff', textDecoration: 'none' };

export default function NavBar() {
  const { data: user } = useAuth();
  const { guildId } = useParams<{ guildId?: string }>();
  const navigate = useNavigate();

  const avatarUrl =
    user?.avatar && user?.id
      ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=32`
      : null;

  async function handleLogout() {
    await client.post('/auth/logout');
    navigate('/login');
  }

  return (
    <nav style={navStyle}>
      <Link to="/dashboard" style={{ ...linkStyle, fontWeight: 700, fontSize: '1.2rem' }}>
        🪨 Grug
      </Link>
      {guildId && (
        <>
          <Link to={`/guilds/${guildId}/config`} style={linkStyle}>Config</Link>
          <Link to={`/guilds/${guildId}/events`} style={linkStyle}>Events</Link>
          <Link to={`/guilds/${guildId}/tasks`} style={linkStyle}>Tasks</Link>
          <Link to={`/guilds/${guildId}/documents`} style={linkStyle}>Documents</Link>
          <Link to={`/guilds/${guildId}/glossary`} style={linkStyle}>Glossary</Link>
        </>
      )}
      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {avatarUrl && <img src={avatarUrl} alt="avatar" style={{ borderRadius: '50%', width: 32, height: 32 }} />}
        {user && <span>{user.username}</span>}
        <button
          onClick={handleLogout}
          style={{ background: 'transparent', border: '1px solid #fff', color: '#fff', cursor: 'pointer', borderRadius: 4, padding: '0.25rem 0.75rem' }}
        >
          Logout
        </button>
      </span>
    </nav>
  );
}
