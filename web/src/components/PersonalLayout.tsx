import { Box, Tab, Tabs, Typography } from '@mui/material';
import { Outlet, useNavigate } from 'react-router-dom';

const TABS = [
  { label: 'Config', path: 'config' },
  { label: 'Tasks', path: 'tasks' },
  { label: 'Notes', path: 'notes' },
];

export default function PersonalLayout() {
  const navigate = useNavigate();

  const lastSegment = location.pathname.split('/').pop() ?? '';
  const activeTab = TABS.findIndex((t) => t.path === lastSegment);

  function handleTabChange(_: React.SyntheticEvent, idx: number) {
    navigate(`/personal/${TABS[idx].path}`);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <Box sx={{ px: { xs: 2, sm: 4 }, pt: { xs: 2, sm: 3 }, pb: 0, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 1.5, fontSize: { xs: '1.25rem', sm: '1.5rem' } }}>
          Direct Messages
        </Typography>
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
          {TABS.map((t) => (
            <Tab key={t.path} label={t.label} disableRipple disableFocusRipple />
          ))}
        </Tabs>
      </Box>

      {/* Page content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: { xs: 2, sm: 4 } }}>
        <Outlet />
      </Box>
    </Box>
  );
}
