import { Box, Drawer, useMediaQuery, useTheme } from '@mui/material';
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import NavBar from '../components/NavBar';
import ServerSidebar from '../components/ServerSidebar';

/**
 * AppLayout — wraps all authenticated routes.
 *
 * Desktop:
 * ┌─────────────────────────────────┐
 * │           NavBar (top)          │
 * ├──────┬──────────────────────────┤
 * │Server│                          │
 * │ Rail │   <Outlet /> (pages)     │
 * │      │                          │
 * └──────┴──────────────────────────┘
 *
 * Mobile: sidebar hidden behind a hamburger menu in NavBar.
 */
export default function AppLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <NavBar onMenuClick={isMobile ? () => setSidebarOpen(true) : undefined} />
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {isMobile ? (
          <Drawer
            open={sidebarOpen}
            onClose={() => setSidebarOpen(false)}
            ModalProps={{ keepMounted: true }}
            PaperProps={{
              sx: { bgcolor: 'background.default' },
            }}
          >
            <ServerSidebar onNavigate={() => setSidebarOpen(false)} />
          </Drawer>
        ) : (
          <ServerSidebar />
        )}
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
