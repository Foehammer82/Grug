import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import NavBar from './NavBar';

/**
 * Minimal wrapper for pages that don't require authentication.
 * Includes the NavBar (which gracefully handles unauthenticated users)
 * but no server sidebar or auth guard.
 */
export default function PublicLayout() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <NavBar />
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  );
}
