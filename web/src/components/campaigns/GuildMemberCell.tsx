import { useQuery } from '@tanstack/react-query';
import { Avatar, Chip, Skeleton, Stack, Tooltip, Typography } from '@mui/material';
import client from '../../api/client';
import type { GuildMember } from '../../types';

interface GuildMemberCellProps {
  guildId: string;
  userId: string | null;
  displayName?: string | null;
}

/** Renders a guild member's avatar + display name, or a fallback for unassigned/custom names. */
export default function GuildMemberCell({ guildId, userId, displayName }: GuildMemberCellProps) {
  const { data, isLoading, isError } = useQuery<GuildMember>({
    queryKey: ['guild-member', guildId, userId],
    queryFn: async () => {
      const res = await client.get<GuildMember>(`/api/guilds/${guildId}/members/${userId}`);
      return res.data;
    },
    staleTime: 5 * 60_000,
    retry: false,
    enabled: !!userId,
  });

  if (!userId) {
    if (displayName) {
      return <Chip label={displayName} size="small" variant="outlined" />;
    }
    return (
      <Typography variant="caption" color="text.disabled" sx={{ fontStyle: 'italic' }}>
        Unassigned
      </Typography>
    );
  }

  if (isLoading) {
    return (
      <Stack direction="row" alignItems="center" spacing={0.75}>
        <Skeleton variant="circular" width={22} height={22} />
        <Skeleton width={65} height={13} />
      </Stack>
    );
  }

  if (isError || !data) {
    return (
      <Typography variant="caption" sx={{ fontFamily: 'monospace' }} color="text.disabled">
        {userId}
      </Typography>
    );
  }

  return (
    <Tooltip title={`@${data.username} · ${userId}`} placement="top">
      <Stack direction="row" alignItems="center" spacing={0.75} sx={{ cursor: 'default' }}>
        <Avatar
          src={data.avatar_url ?? undefined}
          alt={data.display_name}
          sx={{ width: 22, height: 22, fontSize: '0.65rem' }}
        >
          {data.display_name[0].toUpperCase()}
        </Avatar>
        <Typography variant="caption" fontWeight={500} noWrap>
          {data.display_name}
        </Typography>
      </Stack>
    </Tooltip>
  );
}
