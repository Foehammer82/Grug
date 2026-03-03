import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import grugNb from '../assets/grug_nb.png';

interface BotInfo {
  id: string;
  username: string;
  avatar_url: string | null;
}

/**
 * Returns the bot's Discord avatar URL, falling back to the bundled
 * placeholder image if the API is unavailable or the bot has no avatar.
 */
export function useBotAvatar(): string {
  const { data } = useQuery<BotInfo>({
    queryKey: ['bot-info'],
    queryFn: async () => {
      const res = await client.get<BotInfo>('/api/bot-info');
      return res.data;
    },
    staleTime: Infinity,
    retry: false,
  });

  return data?.avatar_url ?? grugNb;
}
