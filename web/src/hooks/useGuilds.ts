import { useQuery } from '@tanstack/react-query';
import client from '../api/client';

export interface Guild {
  id: string;
  name: string;
  icon: string | null;
  is_admin: boolean;
}

export function useGuilds() {
  return useQuery<Guild[]>({
    queryKey: ['guilds'],
    queryFn: async () => {
      const res = await client.get<Guild[]>('/api/guilds');
      return res.data;
    },
    staleTime: 60_000,
  });
}
