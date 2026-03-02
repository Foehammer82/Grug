import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import NavBar from '../components/NavBar';
import ServerSidebar from '../components/ServerSidebar';

/**
 * AppLayout — wraps all authenticated routes.
 *
 * ┌─────────────────────────────────┐
 * │           NavBar (top)          │
 * ├──────┬──────────────────────────┤
 * │Server│                          │
 * │ Rail │   <Outlet /> (pages)     │
 * │      │                          │
 * └──────┴──────────────────────────┘
 */
export default function AppLayout() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <NavBar />
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <ServerSidebar />
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
