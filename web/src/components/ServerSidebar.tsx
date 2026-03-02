/**
 * ServerSidebar — Discord-style left server rail.
 *
 * Each server is shown as a 48 px avatar.  The active server has a white pill
 * indicator on the left edge.  Hovering morphs the avatar from a circle into a
 * rounded-square, just like Discord.
 */
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import { Box, Divider, Tooltip } from '@mui/material';
import { useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useGuilds } from '../hooks/useGuilds';
import GuildAvatar from './GuildAvatar';

const RAIL_WIDTH = 72;
const AVATAR_SIZE = 48;

interface ServerButtonProps {
  guildId: string;
  name: string;
  icon: string | null;
  active: boolean;
  isAdmin: boolean;
}

function ServerButton({ guildId, name, icon, active, isAdmin }: ServerButtonProps) {
  const [hovered, setHovered] = useState(false);
  const navigate = useNavigate();
  const defaultTab = isAdmin ? 'config' : 'events';

  return (
    <Tooltip title={name} placement="right" arrow>
      <Box
        onClick={() => navigate(`/guilds/${guildId}/${defaultTab}`)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        sx={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: RAIL_WIDTH,
          height: AVATAR_SIZE + 8,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {/* Active / hover pill indicator */}
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            width: 4,
            borderRadius: '0 4px 4px 0',
            bgcolor: 'text.primary',
            height: active ? '70%' : hovered ? '40%' : 0,
            top: '50%',
            transform: 'translateY(-50%)',
            transition: 'height 0.15s ease',
          }}
        />

        {/* Avatar with morph effect */}
        <Box
          sx={{
            borderRadius: active || hovered ? '30%' : '50%',
            overflow: 'hidden',
            transition: 'border-radius 0.15s ease, box-shadow 0.15s ease',
            boxShadow: active ? '0 0 0 3px rgba(255,255,255,0.15)' : 'none',
            flexShrink: 0,
            lineHeight: 0,
          }}
        >
          <GuildAvatar
            guildId={guildId}
            name={name}
            icon={icon}
            size={AVATAR_SIZE}
            // GuildAvatar already clips to circle; we override with parent
            square
          />
        </Box>
      </Box>
    </Tooltip>
  );
}

function DmButton() {
  const [hovered, setHovered] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const active = pathname.startsWith('/personal');

  return (
    <Tooltip title="Direct Messages" placement="right" arrow>
      <Box
        onClick={() => navigate('/personal/tasks')}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        sx={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: RAIL_WIDTH,
          height: AVATAR_SIZE + 8,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {/* Active / hover pill indicator */}
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            width: 4,
            borderRadius: '0 4px 4px 0',
            bgcolor: 'text.primary',
            height: active ? '70%' : hovered ? '40%' : 0,
            top: '50%',
            transform: 'translateY(-50%)',
            transition: 'height 0.15s ease',
          }}
        />
        {/* Icon avatar */}
        <Box
          sx={{
            width: AVATAR_SIZE,
            height: AVATAR_SIZE,
            borderRadius: active || hovered ? '30%' : '50%',
            transition: 'border-radius 0.15s ease, box-shadow 0.15s ease',
            boxShadow: active ? '0 0 0 3px rgba(255,255,255,0.15)' : 'none',
            bgcolor: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'primary.contrastText',
          }}
        >
          <ChatBubbleOutlineIcon fontSize="small" />
        </Box>
      </Box>
    </Tooltip>
  );
}

export default function ServerSidebar() {
  const { guildId: activeGuildId } = useParams<{ guildId?: string }>();
  const { data: guilds } = useGuilds();

  return (
    <Box
      component="nav"
      sx={{
        width: RAIL_WIDTH,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 0.5,
        pt: 1,
        pb: 2,
        bgcolor: 'background.default',
        borderRight: '1px solid',
        borderColor: 'divider',
        overflowY: 'auto',
        overflowX: 'hidden',
      }}
    >
      {/* DM button */}
      <DmButton />
      <Divider flexItem sx={{ width: '60%', mx: 'auto', my: 0.5 }} />

      {/* Server list */}
      {guilds?.map((g) => (
        <ServerButton
          key={g.id}
          guildId={g.id}
          name={g.name}
          icon={g.icon}
          active={g.id === activeGuildId}
          isAdmin={g.is_admin}
        />
      ))}
    </Box>
  );
}
