import BrightnessAutoOutlinedIcon from '@mui/icons-material/BrightnessAutoOutlined';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import SettingsIcon from '@mui/icons-material/Settings';
import WbSunnyOutlinedIcon from '@mui/icons-material/WbSunnyOutlined';
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useBotInfo } from '../hooks/useBotAvatar';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ThemePreference, useThemePreference } from '../context/ThemeContext';

const DiscordIcon = () => (
  <svg width="20" height="20" viewBox="0 0 127.14 96.36" fill="currentColor" style={{ flexShrink: 0 }}>
    <path d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0a105.89 105.89 0 0 0-26.25 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15ZM42.45 65.69C36.18 65.69 31 60 31 53s5-12.74 11.43-12.74S54 46 53.89 53s-5.05 12.69-11.44 12.69Zm42.24 0C78.41 65.69 73.25 60 73.25 53s5-12.74 11.44-12.74S96.23 46 96.12 53s-5.04 12.69-11.43 12.69Z" />
  </svg>
);

const THEME_CYCLE: ThemePreference[] = ['light', 'dark', 'system'];

const THEME_ICON: Record<ThemePreference, React.ReactElement> = {
  light:  <WbSunnyOutlinedIcon fontSize="small" />,
  dark:   <DarkModeOutlinedIcon fontSize="small" />,
  system: <BrightnessAutoOutlinedIcon fontSize="small" />,
};

const THEME_LABEL: Record<ThemePreference, string> = {
  light:  'Light mode',
  dark:   'Dark mode',
  system: 'System mode',
};

interface NavBarProps {
  onMenuClick?: () => void;
}

export default function NavBar({ onMenuClick }: NavBarProps) {
  const { data: user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { preference, setPreference } = useThemePreference();
  const { name: botName, avatarUrl: botAvatar } = useBotInfo();

  const canInvite = user?.is_super_admin || user?.can_invite;

  const { data: inviteData } = useQuery<{ url: string }>({
    queryKey: ['invite-url'],
    queryFn: async () => {
      const res = await client.get<{ url: string }>('/api/invite-url');
      return res.data;
    },
    enabled: !!canInvite,
  });

  const stopImpersonating = useMutation({
    mutationFn: async () => {
      await client.post('/api/admin/stop-impersonate');
    },
    onSuccess: () => {
      qc.invalidateQueries();
      navigate('/admin');
    },
  });

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  function cycleTheme() {
    const next = THEME_CYCLE[(THEME_CYCLE.indexOf(preference) + 1) % THEME_CYCLE.length];
    setPreference(next);
  }

  const avatarUrl =
    user?.avatar && user?.id
      ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=64`
      : undefined;

  async function handleLogout() {
    setAnchorEl(null);
    await client.post('/auth/logout');
    navigate('/login');
  }

  return (
    <>
      <AppBar position="sticky" color="default">
        <Toolbar sx={{ gap: 1 }}>
          {/* Hamburger menu — mobile only */}
          {onMenuClick && (
            <IconButton onClick={onMenuClick} size="small" edge="start" sx={{ mr: 0.5 }}>
              <MenuIcon />
            </IconButton>
          )}

          {/* Grug home button + wordmark */}
          <Tooltip title="Home">
            <IconButton onClick={() => navigate('/dashboard')} size="small" sx={{ p: 0.5 }}>
              <Box
                component="img"
                src={botAvatar}
                alt="Home"
                sx={{ width: 38, height: 38, objectFit: 'contain', borderRadius: '50%' }}
              />
            </IconButton>
          </Tooltip>

          <Typography
            variant="h6"
            fontWeight={700}
            sx={{ letterSpacing: '0.02em', color: 'text.primary', cursor: 'default', userSelect: 'none', lineHeight: 1 }}
          >
            {botName}
          </Typography>
          <Typography
            variant="h6"
            fontWeight={400}
            sx={{ color: 'text.secondary', cursor: 'default', userSelect: 'none', lineHeight: 1, display: { xs: 'none', sm: 'block' } }}
          >
            Agent Dashboard
          </Typography>

          <Box sx={{ flexGrow: 1 }} />

          {/* Invite Grug to a server */}
          {canInvite && inviteData?.url && (
            <Tooltip title="Add Grug to another Discord server">
              <Button
                variant="outlined"
                size="small"
                startIcon={<DiscordIcon />}
                href={inviteData.url}
                target="_blank"
                rel="noopener noreferrer"
                sx={{ textTransform: 'none', whiteSpace: 'nowrap', display: { xs: 'none', sm: 'inline-flex' } }}
              >
                Invite Grug
              </Button>
            </Tooltip>
          )}
          {canInvite && inviteData?.url && (
            <Tooltip title="Add Grug to another Discord server">
              <IconButton
                component="a"
                href={inviteData.url}
                target="_blank"
                rel="noopener noreferrer"
                size="small"
                sx={{ color: 'text.secondary', display: { xs: 'inline-flex', sm: 'none' } }}
              >
                <DiscordIcon />
              </IconButton>
            </Tooltip>
          )}

          {/* Theme toggle */}
          <Tooltip title={THEME_LABEL[preference]}>
            <IconButton onClick={cycleTheme} size="small" sx={{ color: 'text.secondary' }}>
              {THEME_ICON[preference]}
            </IconButton>
          </Tooltip>

          {/* Admin gear — super-admins only */}
          {user?.is_super_admin && (
            <Tooltip title="Admin">
              <IconButton onClick={() => navigate('/admin')} size="small" sx={{ color: 'text.secondary' }}>
                <SettingsIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

          {/* User avatar menu */}
          {user && (
            <>
              <Tooltip title={user.username}>
                <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} size="small" sx={{ p: 0.5 }}>
                  <Avatar src={avatarUrl} sx={{ width: 32, height: 32, fontSize: '0.85rem' }}>
                    {user.username[0].toUpperCase()}
                  </Avatar>
                </IconButton>
              </Tooltip>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={() => setAnchorEl(null)}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                slotProps={{ paper: { elevation: 3, sx: { minWidth: 180, mt: 0.5 } } }}
              >
                <Box sx={{ px: 2, py: 1 }}>
                  <Typography variant="subtitle2" fontWeight={700}>{user.username}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>{user.id}</Typography>
                </Box>
                <Divider />
                <MenuItem onClick={handleLogout} sx={{ gap: 1, color: 'error.main', mt: 0.5 }}>
                  <ListItemIcon sx={{ color: 'error.main', minWidth: 'auto' }}>
                    <LogoutIcon fontSize="small" />
                  </ListItemIcon>
                  Logout
                </MenuItem>
              </Menu>
            </>
          )}
        </Toolbar>
      </AppBar>

      {/* Impersonation banner */}
      {user?.impersonating && (
        <Box
          role="status"
          aria-label={`Impersonating ${user.username}`}
          sx={{
            bgcolor: 'warning.main',
            color: 'warning.contrastText',
            px: 2,
            py: 0.75,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
          }}
        >
          <Typography variant="body2" fontWeight={600}>
            Impersonating {user.username} — viewing as this user
          </Typography>
          <Button
            variant="outlined"
            size="small"
            onClick={() => stopImpersonating.mutate()}
            disabled={stopImpersonating.isPending}
            sx={{
              color: 'inherit',
              borderColor: 'inherit',
              '&:hover': { borderColor: 'inherit', bgcolor: 'action.hover' },
              textTransform: 'none',
            }}
          >
            Stop Impersonating
          </Button>
        </Box>
      )}
    </>
  );
}
