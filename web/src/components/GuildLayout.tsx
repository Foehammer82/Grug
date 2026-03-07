import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { Box, Tab, Tabs, Tooltip, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useGuilds } from '../hooks/useGuilds';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';
import type { GuildConfig } from '../types';
import PollingIndicator from './PollingIndicator';

/** How often to refresh all active guild queries, in milliseconds. */
const POLL_MS = 30_000;

/**
 * Tab definitions.
 * - `adminOnly` tabs are hidden from non-admin guild members.
 * - `superAdminOnly` tabs are hidden from everyone except Grug super-admins.
 * - `requiresManager` tabs are additionally hidden when the manager feature is disabled.
 */
const TABS = [
  { label: 'Config',          path: 'config',   adminOnly: true,  superAdminOnly: false, requiresManager: false },
  { label: 'Calendar',        path: 'events',   adminOnly: false, superAdminOnly: false, requiresManager: false },
  { label: 'Scheduled Tasks', path: 'tasks',    adminOnly: true,  superAdminOnly: false, requiresManager: false },
  { label: 'Glossary',        path: 'glossary', adminOnly: false, superAdminOnly: false, requiresManager: false },
  { label: "Grug's Notes",    path: 'notes',    adminOnly: false, superAdminOnly: false, requiresManager: false },
  { label: 'Campaigns',       path: 'campaigns',adminOnly: false, superAdminOnly: false, requiresManager: false },
  { label: 'Manager',         path: 'manager',  adminOnly: false, superAdminOnly: true,  requiresManager: true  },
];

export default function GuildLayout() {
  const { guildId } = useParams<{ guildId: string }>();
  const navigate = useNavigate();
  const { data: guilds } = useGuilds();
  const { data: me } = useAuth();
  const [copied, setCopied] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(Date.now());
  const location = useLocation();
  const queryClient = useQueryClient();

  const guild = guilds?.find((g) => g.id === guildId);
  const isAdmin = guild?.is_admin ?? false;
  const isSuperAdmin = me?.is_super_admin ?? false;
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

  const { data: managerFeature } = useQuery<{ enabled: boolean }>({
    queryKey: ['manager-enabled'],
    queryFn: async () => (await client.get<{ enabled: boolean }>('/api/manager/enabled')).data,
    staleTime: 60_000,
  });
  const managerEnabled = managerFeature?.enabled ?? false;

  // Filter tabs based on admin / super-admin status and feature flags
  const visibleTabs = TABS.filter((t) => {
    if (t.requiresManager && !managerEnabled) return false;
    if (t.superAdminOnly) return isSuperAdmin;
    if (t.adminOnly) return isAdmin;
    return true;
  });

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
  const currentTabDef = TABS.find((t) => t.path === lastSegment);
  const isAdminOnlyPage = currentTabDef?.adminOnly;
  const isSuperAdminOnlyPage = currentTabDef?.superAdminOnly;
  if (guildsLoaded && !isAdmin && isAdminOnlyPage) {
    return <Navigate to={`/guilds/${guildId}/events`} replace />;
  }
  if (guildsLoaded && !isSuperAdmin && isSuperAdminOnlyPage) {
    return <Navigate to={`/guilds/${guildId}/events`} replace />;
  }

  function handleTabChange(_: React.SyntheticEvent, idx: number) {
    navigate(`/guilds/${guildId}/${visibleTabs[idx].path}`);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header area */}
      <Box sx={{ px: { xs: 2, sm: 4 }, pt: { xs: 2, sm: 3 }, pb: 0, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            mb: 1.5,
            '&:hover .guild-id-reveal': { opacity: 1 },
          }}
        >
          <Typography variant="h5" fontWeight={700} sx={{ fontSize: { xs: '1.25rem', sm: '1.5rem' } }}>
            {guild?.name ?? 'Loading…'}
          </Typography>
          {guildId && (
            <Tooltip title={copied ? 'Copied!' : 'Copy server ID'} placement="right">
              <Box
                className="guild-id-reveal"
                onClick={handleCopyId}
                sx={{
                  display: { xs: 'none', sm: 'flex' },
                  alignItems: 'center',
                  gap: 0.5,
                  cursor: 'pointer',
                  opacity: 0,
                  transition: 'opacity 0.15s ease',
                  color: 'text.disabled',
                  '&:hover': { color: 'text.secondary' },
                }}
              >
                <Typography
                  variant="caption"
                  color="inherit"
                  sx={{ fontFamily: 'monospace', userSelect: 'none', lineHeight: 1 }}
                >
                  {guildId}
                </Typography>
                <ContentCopyIcon sx={{ fontSize: '0.875rem' }} />
              </Box>
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
        <Outlet context={{ isAdmin, isSuperAdmin, timezone }} />
      </Box>
    </Box>
  );
}
