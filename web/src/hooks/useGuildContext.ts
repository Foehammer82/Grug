import { useOutletContext } from 'react-router-dom';

interface GuildContext {
  isAdmin: boolean;
  /** IANA timezone string from the guild's server config (e.g. "America/Chicago"). */
  timezone: string;
}

/**
 * Access the guild-level context (isAdmin, timezone) passed through GuildLayout's Outlet.
 */
export function useGuildContext(): GuildContext {
  return useOutletContext<GuildContext>();
}
