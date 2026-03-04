import { Avatar, Box, Chip, IconButton, Skeleton, Stack, Tooltip, Typography } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { useQuery } from '@tanstack/react-query';
import client from '../../api/client';
import { SYSTEM_LABELS } from '../../constants/character';
import CharacterTable from './CharacterTable';
import type { Campaign, DiscordChannel, GuildMember } from '../../types';

interface CampaignCardProps {
  campaign: Campaign;
  channels: DiscordChannel[];
  isAdmin: boolean;
  currentUserId: string;
  allCampaigns: Campaign[];
  onEdit: (c: Campaign) => void;
  onDelete: (c: Campaign) => void;
}

/** A compact header Chip showing the campaign's Game Master. */
function GmChip({ guildId, userId }: { guildId: string; userId: string }) {
  const { data, isLoading } = useQuery<GuildMember>({
    queryKey: ['guild-member', guildId, userId],
    queryFn: async () => {
      const res = await client.get<GuildMember>(`/api/guilds/${guildId}/members/${userId}`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });

  if (isLoading) {
    return <Skeleton variant="rounded" width={80} height={20} />;
  }

  const label = data?.display_name ?? userId;
  const avatarSrc = data?.avatar_url ?? undefined;
  const initials = (data?.display_name ?? userId)[0]?.toUpperCase();

  return (
    <Tooltip title="Game Master" placement="top">
      <Chip
        size="small"
        variant="outlined"
        label={label}
        avatar={
          <Avatar src={avatarSrc} sx={{ bgcolor: 'primary.main', fontSize: '0.55rem' }}>
            {initials}
          </Avatar>
        }
        sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
      />
    </Tooltip>
  );
}

/** Renders a single campaign card with its header bar and always-visible character table. */
export default function CampaignCard({
  campaign,
  channels,
  isAdmin,
  currentUserId,
  allCampaigns,
  onEdit,
  onDelete,
}: CampaignCardProps) {
  const c = campaign;
  const channelName = channels.find((ch) => ch.id === c.channel_id)?.name;

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
        opacity: c.is_active ? 1 : 0.55,
        transition: 'opacity 0.15s',
      }}
    >
      {/* Campaign header bar */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1.5}
        sx={{
          px: 2,
          py: 1,
          bgcolor: 'action.hover',
          borderBottom: '1px solid',
          borderColor: 'divider',
          minHeight: 44,
        }}
      >
        <Typography variant="body2" fontWeight={600} noWrap sx={{ flex: '0 1 auto' }}>
          {c.name}
        </Typography>
        {c.character_count > 0 && (
          <Chip
            label={`${c.character_count} ${c.character_count === 1 ? 'character' : 'characters'}`}
            size="small"
            variant="outlined"
            sx={{ height: 18, fontSize: '0.65rem', pointerEvents: 'none', flexShrink: 0 }}
          />
        )}
        <Box sx={{ flex: 1 }} />
        <Chip
          label={SYSTEM_LABELS[c.system] ?? c.system}
          size="small"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
        />
        {channelName && (
          <Chip
            label={`#${channelName}`}
            size="small"
            variant="outlined"
            sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0, color: 'text.secondary' }}
          />
        )}
        {c.gm_discord_user_id && (
          <GmChip guildId={c.guild_id} userId={c.gm_discord_user_id} />
        )}
        <Chip
          label={c.is_active ? 'Active' : 'Inactive'}
          size="small"
          color={c.is_active ? 'success' : 'default'}
          sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
        />
        {isAdmin && (
          <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
            <Tooltip title="Edit campaign">
              <IconButton size="small" onClick={() => onEdit(c)}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete campaign">
              <IconButton size="small" color="error" onClick={() => onDelete(c)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        )}
      </Stack>

      {/* Character table — always visible */}
      <Box sx={{ px: 2, py: 1.5 }}>
        <CharacterTable
          guildId={c.guild_id}
          campaignId={c.id}
          campaignSystem={c.system}
          isAdmin={isAdmin}
          currentUserId={currentUserId}
          allCampaigns={allCampaigns}
        />
      </Box>
    </Box>
  );
}
