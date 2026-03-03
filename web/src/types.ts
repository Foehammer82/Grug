/**
 * Shared TypeScript types used across multiple pages and components.
 *
 * Keep Discord snowflake IDs as `string` — they exceed Number.MAX_SAFE_INTEGER.
 */

/* ── Discord entities ─────────────────────────────────────────────── */

export interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

/* ── Scheduled tasks ──────────────────────────────────────────────── */

export interface ScheduledTask {
  id: number;
  guild_id: string;
  channel_id: string;
  user_id: string | null;
  type: 'once' | 'recurring';
  name: string | null;
  prompt: string;
  fire_at: string | null;
  cron_expression: string | null;
  source: string;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
  created_by: string;
  created_at: string;
}

/* ── Calendar events ──────────────────────────────────────────────── */

export interface CalendarEvent {
  id: number;
  guild_id: string;
  title: string;
  description: string | null;
  location: string | null;
  start_time: string;
  end_time: string | null;
  all_day: boolean;
  rrule: string | null;
  channel_id: string | null;
  occurrence_start?: string;
  occurrence_end?: string;
  /** original_start is present for recurring event occurrences */
  original_start?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/* ── Event RSVP ───────────────────────────────────────────────────── */

export type RSVPStatus = 'attending' | 'maybe' | 'declined';

export interface EventRSVP {
  id: number;
  event_id: number;
  discord_user_id: string;
  status: RSVPStatus;
  note: string | null;
  created_at: string;
  updated_at: string;
}

/* ── Event Notes ──────────────────────────────────────────────────── */

export interface EventNote {
  id: number;
  event_id: number;
  content: string;
  done: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/* ── Occurrence Overrides ─────────────────────────────────────────── */

export interface EventOccurrenceOverride {
  id: number;
  event_id: number;
  original_start: string;
  new_start: string | null;
  new_end: string | null;
  cancelled: boolean;
  created_at: string;
  updated_at: string;
}

/* ── Availability Polls ───────────────────────────────────────────── */

export interface PollOption {
  id: number;
  label: string;
  start_time?: string | null;
  end_time?: string | null;
}

export interface PollVote {
  id: number;
  poll_id: number;
  discord_user_id: string;
  option_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface AvailabilityPoll {
  id: number;
  guild_id: string;
  event_id: number | null;
  title: string;
  options: PollOption[];
  closes_at: string | null;
  winner_option_id: number | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  votes: PollVote[];
}

/* ── Guild config ─────────────────────────────────────────────────── */

export interface GuildConfig {
  guild_id: string;
  timezone: string;
  /** Returned as a string to preserve Discord snowflake precision (> MAX_SAFE_INTEGER). */
  announce_channel_id: string | null;
  context_cutoff: string | null;
  default_ttrpg_system: string | null;
}

/* ── Glossary ─────────────────────────────────────────────────────── */

export interface GlossaryTerm {
  id: number;
  guild_id: string;
  channel_id: string | null;
  term: string;
  definition: string;
  ai_generated: boolean;
  originally_ai_generated: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/* ── Documents ────────────────────────────────────────────────────── */

export interface Document {
  id: number;
  filename: string;
  description: string | null;
  chunk_count: number;
  content_hash: string | null;
  created_at: string;
}

export interface DocumentChunk {
  text: string;
  filename: string;
  chunk_index: number;
  distance: number;
}

export interface DocumentSearchResult {
  chunks: DocumentChunk[];
  error: boolean;
}

/* ── Campaigns ───────────────────────────────────────────────────── */

export interface Campaign {
  id: number;
  guild_id: string;
  channel_id: string;
  name: string;
  system: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

/* ── Characters ───────────────────────────────────────────────────── */

export interface Character {
  id: number;
  owner_discord_user_id: string;
  campaign_id: number | null;
  name: string;
  system: string;
  structured_data: Record<string, unknown> | null;
  file_path: string | null;
  created_at: string;
  updated_at: string;
}


/* ── Table styling ────────────────────────────────────────────────── */

/** Standardised header-cell styling for data tables. */
export const TABLE_HEADER_SX = {
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  fontSize: '0.75rem',
  letterSpacing: '0.05em',
  color: 'text.secondary',
} as const;

/* ── Rule Sources ─────────────────────────────────────────────────── */

export interface BuiltinRuleSource {
  source_id: string;
  name: string;
  description: string;
  system: string | null;
  url: string;
  enabled: boolean;
}

/* ── Datetime helpers ─────────────────────────────────────────────── */

/** Convert ISO UTC datetime string to datetime-local input value (e.g. "2026-03-01T20:00"). */
export function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toISOString().slice(0, 16);
  } catch {
    return '';
  }
}

/** Convert datetime-local input value (UTC assumed) to ISO string, or null if empty. */
export function localInputToIso(value: string): string | null {
  if (!value) return null;
  return new Date(value + ':00.000Z').toISOString();
}
