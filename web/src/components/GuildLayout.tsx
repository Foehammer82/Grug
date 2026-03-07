import { Box, Tab, Tabs, Tooltip, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useGuilds } from '../hooks/useGuilds';
import client from '../api/client';
import type { GuildConfig } from '../types';
import PollingIndicator from './PollingIndicator';

/** How often to refresh all active guild queries, in milliseconds. */
const POLL_MS = 30_000;

/** Tab definitions. `adminOnly` tabs are hidden from non-admin guild members. */
const TABS = [
  { label: 'Config',       path: 'config',       adminOnly: true },
  { label: 'Calendar',        path: 'events',       adminOnly: false },
  { label: 'Scheduled Tasks', path: 'tasks',        adminOnly: true },
  { label: 'Documents',    path: 'documents',    adminOnly: false },
  { label: 'Glossary',     path: 'glossary',     adminOnly: false },
  { label: "Grug's Notes", path: 'notes',        adminOnly: false },
  { label: 'Campaigns',    path: 'campaigns',    adminOnly: false },
];

export default function GuildLayout() {
  const { guildId } = useParams<{ guildId: string }>();
  const navigate = useNavigate();
  const { data: guilds } = useGuilds();
  const [copied, setCopied] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(Date.now());
  const location = useLocation();
  const queryClient = useQueryClient();

  const guild = guilds?.find((g) => g.id === guildId);
  const isAdmin = guild?.is_admin ?? false;
  const guildsLoaded = guilds !== undefined;

  const { data: guildConfig } = useQuery<GuildConfig>({
    queryKey: ['guild-config', guildId],
    queryFn: async () => {
      const res = await client.get<GuildConfig>(`/api/guilds/${guildId}/config`);
      return res.data;
    },
    enabled: !!guildId,
  });
  const timezone = guildConfig?.timezone ?? 'UTC';

  // Filter tabs based on admin status
  const visibleTabs = TABS.filter((t) => !t.adminOnly || isAdmin);

  // Global polling: periodically invalidate all active queries for this guild.
  // React Query only refetches queries with active observers (i.e. currently
  // mounted components), so only the data the user is currently viewing is
  // refreshed — keeping requests efficient.
  useEffect(() => {
    if (!guildId) return undefined;
    const timer = setInterval(() => {
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey.some((key) => key === guildId),
      });
      setLastRefreshedAt(Date.now());
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [guildId, queryClient]);

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

  // Only redirect once guild data has loaded — avoids a false redirect while
  // isAdmin is still false during the initial fetch (which would replace the
  // URL with /events on every page refresh for admin-only pages).
  const isAdminOnlyPage = TABS.find((t) => t.path === lastSegment)?.adminOnly;
  if (guildsLoaded && !isAdmin && isAdminOnlyPage) {
    return <Navigate to={`/guilds/${guildId}/events`} replace />;
  }

  function handleTabChange(_: React.SyntheticEvent, idx: number) {
    navigate(`/guilds/${guildId}/${visibleTabs[idx].path}`);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header area */}
      <Box sx={{ px: { xs: 2, sm: 4 }, pt: { xs: 2, sm: 3 }, pb: 0, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
          <Typography variant="h5" fontWeight={700} sx={{ fontSize: { xs: '1.25rem', sm: '1.5rem' } }}>
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
                  display: { xs: 'none', sm: 'inline' },
                  '&:hover': { color: 'text.secondary' },
                }}
              >
                {guildId}
              </Typography>
            </Tooltip>
          )}
          <PollingIndicator intervalMs={POLL_MS} dataUpdatedAt={lastRefreshedAt} />
        </Box>
        <Tabs
          value={activeTab === -1 ? 0 : activeTab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          sx={{
            minHeight: 40,
            '& .MuiTab-root': {
              minHeight: 40,
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.875rem',
              color: 'text.secondary',
              px: { xs: 1.5, sm: 2 },
              minWidth: { xs: 'auto', sm: 90 },
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
      <Box sx={{ flex: 1, overflow: 'auto', p: { xs: 2, sm: 4 } }}>
        <Outlet context={{ isAdmin, timezone }} />
      </Box>
    </Box>
  );
}
