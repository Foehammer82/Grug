import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useBotAvatar } from '../hooks/useBotAvatar';
import { getEnv } from '../env';

const API_URL = getEnv('VITE_API_URL') ?? 'http://localhost:8000';

const DiscordIcon = () => (
  <svg width="22" height="22" viewBox="0 0 127.14 96.36" fill="currentColor" style={{ flexShrink: 0 }}>
    <path d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0a105.89 105.89 0 0 0-26.25 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15ZM42.45 65.69C36.18 65.69 31 60 31 53s5-12.74 11.43-12.74S54 46 53.89 53s-5.05 12.69-11.44 12.69Zm42.24 0C78.41 65.69 73.25 60 73.25 53s5-12.74 11.44-12.74S96.23 46 96.12 53s-5.04 12.69-11.43 12.69Z" />
  </svg>
);

export default function LoginPage() {
  const [hovered, setHovered] = useState(false);
  const botAvatar = useBotAvatar();

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        minHeight: '100vh',
        background: (t) =>
          t.palette.mode === 'dark'
            ? 'radial-gradient(ellipse at 60% 40%, rgba(212,146,74,0.22) 0%, transparent 65%), #1c1812'
            : 'radial-gradient(ellipse at 60% 40%, rgba(160,92,32,0.14) 0%, transparent 65%), #faf5ee',
      }}
    >
      <Paper
        elevation={8}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 3,
          p: '3rem 3.5rem',
          maxWidth: 420,
          width: '90%',
          textAlign: 'center',
          borderRadius: 3,
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          <Box component="img" src={botAvatar} alt="Grug" sx={{ width: 80, height: 80, objectFit: 'contain', borderRadius: '50%' }} />
          <Typography variant="h5" fontWeight={700} letterSpacing="-0.02em">
            Grug Dashboard
          </Typography>
        </Box>

        <Typography variant="body2" color="text.secondary" lineHeight={1.7}>
          Roll for initiative on your server.<br />
          Sign in with Discord to get started.
        </Typography>

        <Divider sx={{ width: '100%' }} />

        <Button
          component="a"
          href={`${API_URL}/auth/discord/login`}
          variant="contained"
          size="large"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          startIcon={<DiscordIcon />}
          sx={{
            background: hovered ? '#4752c4' : '#5865F2',
            '&:hover': { background: '#4752c4' },
            px: 4,
            gap: 1,
          }}
        >
          Login with Discord
        </Button>

        <Typography variant="caption" color="text.disabled">
          Only Discord server admins can manage settings.
        </Typography>
      </Paper>
    </Box>
  );
}
