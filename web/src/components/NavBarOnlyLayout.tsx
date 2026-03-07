import { Box, Drawer, useMediaQuery, useTheme } from '@mui/material';
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import NavBar from './NavBar';
import ServerSidebar from './ServerSidebar';

/**
 * NavBarOnlyLayout — minimal layout for full-screen focused views.
 *
 * Shows only the top NavBar with no server sidebar or guild-level tab bar.
 * Used for dedicated campaign pages and similar focused views where the guild
 * chrome would be distracting.
 *
 * On mobile, retains the hamburger menu to open the server sidebar drawer so
 * users can switch servers without navigating away.
 */
export default function NavBarOnlyLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <NavBar onMenuClick={isMobile ? () => setSidebarOpen(true) : undefined} />
      {isMobile && (
        <Drawer
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          ModalProps={{ keepMounted: true }}
          PaperProps={{ sx: { bgcolor: 'background.default' } }}
        >
          <ServerSidebar onNavigate={() => setSidebarOpen(false)} />
        </Drawer>
      )}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  );
}
