import { Box, Typography } from '@mui/material';
import grugNb from '../assets/grug_nb.png';
import { useGuilds } from '../hooks/useGuilds';

export default function DashboardPage() {
  const { data: guilds, isLoading } = useGuilds();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        gap: 2,
        userSelect: 'none',
      }}
    >
      <Box
        component="img"
        src={grugNb}
        alt="Grug"
        sx={{ width: 80, height: 80, opacity: 0.35, objectFit: 'contain' }}
      />
      {isLoading ? (
        <Typography color="text.secondary">Loading servers…</Typography>
      ) : guilds && guilds.length > 0 ? (
        <Typography variant="h6" color="text.secondary">
          ← Select a server to get started
        </Typography>
      ) : (
        <>
          <Typography variant="h6" color="text.secondary">No servers found</Typography>
          <Typography variant="body2" color="text.disabled">
            Make sure Grug is in your server.
          </Typography>
        </>
      )}


    </Box>
  );
}
