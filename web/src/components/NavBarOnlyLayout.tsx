import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import NavBar from './NavBar';

/**
 * NavBarOnlyLayout — minimal layout for full-screen focused views.
 *
 * Shows only the top NavBar with no server sidebar or guild-level tab bar.
 * Used for dedicated campaign pages and similar focused views where the guild
 * chrome would be distracting.
 */
export default function NavBarOnlyLayout() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <NavBar />
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  );
}
