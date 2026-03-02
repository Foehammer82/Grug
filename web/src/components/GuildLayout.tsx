import { Box, Tab, Tabs, Tooltip, Typography } from '@mui/material';
import { useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useGuilds } from '../hooks/useGuilds';

/** Tab definitions. `adminOnly` tabs are hidden from non-admin guild members. */
const TABS = [
  { label: 'Config',     path: 'config',    adminOnly: true },
  { label: 'Events',     path: 'events',    adminOnly: false },
  { label: 'Tasks',      path: 'tasks',     adminOnly: true },
  { label: 'Documents',  path: 'documents', adminOnly: false },
  { label: 'Glossary',   path: 'glossary',  adminOnly: false },
  { label: 'Campaigns',  path: 'campaigns', adminOnly: true },
];

export default function GuildLayout() {
  const { guildId } = useParams<{ guildId: string }>();
  const navigate = useNavigate();
  const { data: guilds } = useGuilds();
  const [copied, setCopied] = useState(false);
  const location = useLocation();

  const guild = guilds?.find((g) => g.id === guildId);
  const isAdmin = guild?.is_admin ?? false;

  // Filter tabs based on admin status
  const visibleTabs = TABS.filter((t) => !t.adminOnly || isAdmin);

  function handleCopyId() {
    if (!guildId) return;
    navigator.clipboard.writeText(guildId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  // Determine active tab from the current URL segment
  const lastSegment = location.pathname.split('/').pop() ?? '';
  const activeTab = visibleTabs.findIndex((t) => t.path === lastSegment);

  // If non-admin lands on an admin-only page, redirect to events
  const isAdminOnlyPage = TABS.find((t) => t.path === lastSegment)?.adminOnly;
  if (!isAdmin && isAdminOnlyPage) {
    return <Navigate to={`/guilds/${guildId}/events`} replace />;
  }

  function handleTabChange(_: React.SyntheticEvent, idx: number) {
    navigate(`/guilds/${guildId}/${visibleTabs[idx].path}`);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header area */}
      <Box sx={{ px: 4, pt: 3, pb: 0, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 1.5 }}>
          <Typography variant="h5" fontWeight={700}>
            {guild?.name ?? 'Loading…'}
          </Typography>
          {guildId && (
            <Tooltip title={copied ? 'Copied!' : 'Click to copy'} placement="right">
              <Typography
                variant="caption"
                color="text.disabled"
                onClick={handleCopyId}
                sx={{
                  fontFamily: 'monospace',
                  cursor: 'pointer',
                  userSelect: 'none',
                  lineHeight: 1,
                  '&:hover': { color: 'text.secondary' },
                }}
              >
                {guildId}
              </Typography>
            </Tooltip>
          )}
        </Box>
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
          {visibleTabs.map((t) => (
            <Tab key={t.path} label={t.label} disableRipple disableFocusRipple />
          ))}
        </Tabs>
      </Box>

      {/* Page content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 4 }}>
        <Outlet context={{ isAdmin }} />
      </Box>
    </Box>
  );
}
