import { Box, Tab, Tabs, Typography } from '@mui/material';
import { Outlet, useNavigate, useParams } from 'react-router-dom';
import { useGuilds } from '../hooks/useGuilds';

const TABS = [
  { label: 'Config',     path: 'config' },
  { label: 'Events',     path: 'events' },
  { label: 'Tasks',      path: 'tasks' },
  { label: 'Documents',  path: 'documents' },
  { label: 'Glossary',   path: 'glossary' },
];

export default function GuildLayout() {
  const { guildId } = useParams<{ guildId: string }>();
  const navigate = useNavigate();
  const { data: guilds } = useGuilds();

  const guild = guilds?.find((g) => g.id === guildId);

  // Determine active tab from the current URL segment
  const lastSegment = location.pathname.split('/').pop() ?? '';
  const activeTab = TABS.findIndex((t) => t.path === lastSegment);

  function handleTabChange(_: React.SyntheticEvent, idx: number) {
    navigate(`/guilds/${guildId}/${TABS[idx].path}`);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header area */}
      <Box sx={{ px: 4, pt: 3, pb: 0, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 1.5 }}>
          {guild?.name ?? 'Loading…'}
        </Typography>
        <Tabs
          value={activeTab === -1 ? 0 : activeTab}
          onChange={handleTabChange}
          sx={{
            minHeight: 40,
            '& .MuiTab-root': {
              minHeight: 40,
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.875rem',
              color: 'text.secondary',
              '&.Mui-selected': { color: 'primary.main' },
              '&.Mui-focusVisible': { outline: 'none', boxShadow: 'none', backgroundColor: 'transparent' },
            },
          }}
        >
          {TABS.map((t) => (
            <Tab key={t.path} label={t.label} disableRipple disableFocusRipple />
          ))}
        </Tabs>
      </Box>

      {/* Page content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 4 }}>
        <Outlet />
      </Box>
    </Box>
  );
}
