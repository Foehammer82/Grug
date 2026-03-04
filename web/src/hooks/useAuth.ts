import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';

export interface User {
  id: string;
  username: string;
  discriminator: string;
  avatar: string | null;
  is_super_admin: boolean;
  can_invite: boolean;
  // Impersonation fields — only populated when a super-admin is impersonating.
  impersonating: boolean;
  impersonator_id: string | null;
  impersonator_username: string | null;
}

export function useAuth() {
  const navigate = useNavigate();
  const query = useQuery<User>({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await client.get<User>('/auth/me');
      return res.data;
    },
    retry: false,
  });

  useEffect(() => {
    if (query.isError) {
      navigate('/login');
    }
  }, [query.isError, navigate]);

  return query;
}
