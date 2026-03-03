import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import grugNb from '../assets/grug_nb.png';

interface BotInfo {
  id: string;
  username: string;
  avatar_url: string | null;
}

/**
 * Returns the bot's Discord username and avatar URL.
 * Falls back to "Grug" / the bundled placeholder image if the API is
 * unavailable or the bot has no avatar set.
 */
export function useBotInfo(): { name: string; avatarUrl: string } {
  const { data } = useQuery<BotInfo>({
    queryKey: ['bot-info'],
    queryFn: async () => {
      const res = await client.get<BotInfo>('/api/bot-info');
      return res.data;
    },
    staleTime: Infinity,
    retry: false,
  });

  return {
    name: data?.username ?? 'Grug',
    avatarUrl: data?.avatar_url ?? grugNb,
  };
}

/** Convenience wrapper — returns just the avatar URL (backwards compat). */
export function useBotAvatar(): string {
  return useBotInfo().avatarUrl;
}
