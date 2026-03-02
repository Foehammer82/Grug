import { Box, Button, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import grugNb from '../assets/grug_nb.png';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGuilds } from '../hooks/useGuilds';

export default function DashboardPage() {
  const { data: user } = useAuth();
  const { data: guilds, isLoading } = useGuilds();

  const canInvite = user?.is_super_admin || user?.can_invite;

  const { data: inviteData } = useQuery<{ url: string }>({
    queryKey: ['invite-url'],
    queryFn: async () => {
      const res = await client.get<{ url: string }>('/api/invite-url');
      return res.data;
    },
    enabled: !!canInvite,
  });

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

      {canInvite && inviteData?.url && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<OpenInNewIcon />}
          href={inviteData.url}
          target="_blank"
          rel="noopener noreferrer"
          sx={{ mt: 1 }}
        >
          Invite Grug to a Server
        </Button>
      )}
    </Box>
  );
}
