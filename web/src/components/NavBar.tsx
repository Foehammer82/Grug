import BrightnessAutoOutlinedIcon from '@mui/icons-material/BrightnessAutoOutlined';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
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
                startIcon={<OpenInNewIcon />}
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
                <OpenInNewIcon fontSize="small" />
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
