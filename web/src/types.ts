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
  upcoming_runs: string[];
  event_id: number | null;
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
  reminder_days: number[] | null;
  reminder_time: string | null;
  poll_advance_days: number | null;
  campaign_id: number | null;
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
  campaign_id: number | null;
  content_hash: string | null;
  is_public: boolean;
  file_path: string | null;
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
  gm_discord_user_id: string | null;
  schedule_mode: 'fixed' | 'poll';
  combat_tracker_depth: 'basic' | 'standard' | 'full';
  banking_enabled: boolean;
  player_banking_enabled: boolean;
  party_gold: number;
  allow_manual_dice_recording: boolean;
  /** Per-campaign Anthropic model override. null = use server default. */
  llm_model: string | null;
  created_by: string;
  created_at: string;
  deleted_at: string | null;
  character_count: number;
}

/* ── Session Notes ────────────────────────────────────────────────── */

export type SynthesisStatus = 'pending' | 'processing' | 'done' | 'failed';

export interface SessionNote {
  id: number;
  campaign_id: number;
  guild_id: string;
  session_date: string | null;
  title: string | null;
  raw_notes: string;
  clean_notes: string | null;
  synthesis_status: SynthesisStatus;
  synthesis_error: string | null;
  rag_document_id: number | null;
  submitted_by: string;
  created_at: string;
  updated_at: string;
}

/* ── Characters ───────────────────────────────────────────────────── */

export interface CharacterSheetHP {
  current?: number | null;
  max?: number | null;
  temp?: number | null;
}

export interface CharacterSheetAbilityScores {
  STR?: number | null;
  DEX?: number | null;
  CON?: number | null;
  INT?: number | null;
  WIS?: number | null;
  CHA?: number | null;
}

/** Structured data extracted from an uploaded character sheet. All fields optional. */
export interface CharacterSheet {
  _source?: string | null;
  system?: string | null;
  name?: string | null;
  player_name?: string | null;
  level?: number | null;
  class_and_subclass?: string | null;
  dual_class?: string | null;
  race_or_ancestry?: string | null;
  heritage?: string | null;
  background?: string | null;
  alignment?: string | null;
  deity?: string | null;
  size?: string | null;
  key_ability?: string | null;
  hp?: CharacterSheetHP | null;
  ability_scores?: CharacterSheetAbilityScores | null;
  armor_class?: number | null;
  speed?: string | null;
  initiative?: number | null;
  proficiency_bonus?: number | null;
  /** PF2e saving throw proficiency ranks (0–4). */
  saving_throws?: { fortitude?: number | null; reflex?: number | null; will?: number | null } | null;
  /** PF2e perception proficiency rank (0–4). */
  perception?: number | null;
  /** Full PF2e proficiency map (skills, weapons, armor, casting, classDC, etc.). Values are ranks 0–4. */
  proficiencies?: Record<string, number | null> | null;
  /** PF2e lore skills with proficiency rank. */
  lore_skills?: Array<{ name: string; rank: number }> | null;
  attacks?: Array<Record<string, unknown>> | null;
  /** Raw weapon data from Pathbuilder. */
  weapons?: Array<Record<string, unknown>> | null;
  /** Raw armor data from Pathbuilder. */
  armor?: Array<Record<string, unknown>> | null;
  spells?: Array<Record<string, unknown>> | null;
  features_and_traits?: unknown[] | null;
  inventory?: unknown[] | null;
  currency?: Record<string, number> | null;
  languages?: string[] | null;
  notes?: string | null;
  extra?: Record<string, unknown> | null;
}

export interface Character {
  id: number;
  owner_discord_user_id: string | null;
  owner_display_name: string | null;
  campaign_id: number | null;
  name: string;
  system: string;
  structured_data: CharacterSheet | null;
  pathbuilder_id: number | null;
  file_path: string | null;
  notes: string | null;
  gold: number;
  pathbuilder_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

/** A Discord guild member resolved via the bot token. */
export interface GuildMember {
  discord_user_id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
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

/* ── Gold transactions ────────────────────────────────────────────── */

export interface GoldTransaction {
  id: number;
  campaign_id: number;
  character_id: number | null;
  /** Serialized as a string by the API to preserve Discord snowflake precision. */
  actor_discord_user_id: string;
  amount: number;
  reason: string | null;
  created_at: string;
}

/* ── Grug Notes ───────────────────────────────────────────────────── */

export interface GrugNote {
  id: number;
  guild_id: string | null;
  user_id: string | null;
  content: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

/* ── Dice Rolls ───────────────────────────────────────────────────── */

export type DiceRollType =
  | 'general'
  | 'attack'
  | 'damage'
  | 'saving_throw'
  | 'ability_check'
  | 'initiative'
  | 'death_save'
  | 'skill_check';

export const ROLL_TYPE_LABELS: Record<DiceRollType, string> = {
  general: 'General',
  attack: 'Attack',
  damage: 'Damage',
  saving_throw: 'Saving Throw',
  ability_check: 'Ability Check',
  initiative: 'Initiative',
  death_save: 'Death Save',
  skill_check: 'Skill Check',
};

export interface DiceRollIndividual {
  expression?: string;
  sides?: number;
  rolls?: number[];
  kept?: number[];
  total?: number;
  sign?: number;
  constant?: number;
  manual?: boolean;
}

export interface DiceRoll {
  id: number;
  guild_id: string;
  campaign_id: number | null;
  roller_discord_user_id: string;
  roller_display_name: string;
  character_name: string | null;
  expression: string;
  individual_rolls: DiceRollIndividual[];
  total: number;
  roll_type: DiceRollType;
  is_private: boolean;
  context_note: string | null;
  formatted: string;
  created_at: string;
}

/* ── Encounters / Initiative ──────────────────────────────────────── */

export type EncounterStatus = 'preparing' | 'active' | 'ended';

export type CombatTrackerDepth = 'basic' | 'standard' | 'full';

export interface MonsterSearchResult {
  name: string;
  source: string;
  system: string;
  hp: number | null;
  ac: number | null;
  initiative_modifier: number | null;
  cr: string | null;
  size: string | null;
  type: string | null;
  save_modifiers: Record<string, number> | null;
}

export interface Combatant {
  id: number;
  encounter_id: number;
  character_id: number | null;
  name: string;
  initiative_roll: number | null;
  initiative_modifier: number;
  is_enemy: boolean;
  is_hidden: boolean;
  sort_order: number;
  is_active: boolean;
  // HP / AC (standard+ depth)
  max_hp: number | null;
  current_hp: number | null;
  temp_hp: number;
  armor_class: number | null;
  conditions: string[] | null;
  save_modifiers: Record<string, number> | null;
  // Death saves & concentration (full depth)
  death_save_successes: number;
  death_save_failures: number;
  concentration_spell: string | null;
  created_at: string;
}

export interface CombatLogEntry {
  id: number;
  encounter_id: number;
  combatant_id: number;
  round_number: number;
  event_type: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface SavingThrowResult {
  combatant_id: number;
  combatant_name: string;
  roll: number;
  modifier: number;
  total: number;
  dc: number;
  passed: boolean;
}

export interface Encounter {
  id: number;
  campaign_id: number;
  guild_id: string;
  name: string;
  status: EncounterStatus;
  current_turn_index: number;
  round_number: number;
  channel_id: string | null;
  created_by: string;
  created_at: string;
  ended_at: string | null;
  combatants: Combatant[];
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

/* ── Manager agent ────────────────────────────────────────────────── */

export interface InstructionOverride {
  id: number;
  guild_id: string;
  channel_id: string | null;
  scope: 'guild' | 'channel';
  content: string;
  status: 'active' | 'pending' | 'rejected';
  source: 'admin' | 'manager';
  review_id: number | null;
  reason: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ManagerReview {
  id: number;
  guild_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  messages_reviewed: number;
  feedback_reviewed: number;
  summary: string | null;
  observations: Array<{
    category: string;
    severity: string;
    detail: string;
  }> | null;
  recommendations: Array<{
    action: string;
    content: string;
    reason: string;
  }> | null;
  webhook_sent: boolean;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}
