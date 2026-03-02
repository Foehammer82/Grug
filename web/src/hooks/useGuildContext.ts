import { useOutletContext } from 'react-router-dom';

interface GuildContext {
  isAdmin: boolean;
}

/**
 * Access the guild-level context (isAdmin) passed through GuildLayout's Outlet.
 */
export function useGuildContext(): GuildContext {
  return useOutletContext<GuildContext>();
}
