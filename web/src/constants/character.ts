/** Shared character & campaign constants used across the campaigns UI. */

/** Suggested systems shown in autocomplete — users may still type any value. */
export const SYSTEM_OPTIONS = ['pf2e', 'dnd5e'];

export const SYSTEM_LABELS: Record<string, string> = {
  pf2e: 'Pathfinder 2E',
  dnd5e: 'D&D 5e',
  unknown: 'Unknown',
};

export const ABILITY_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

/** File extensions accepted for character sheet uploads. */
export const SHEET_ACCEPTED = '.txt,.md,.rst,.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp';

/** Maximum upload size in MB. */
export const MAX_SHEET_MB = 20;

/** Compute the ability modifier string from an ability score. */
export function abilityMod(score: number | null | undefined): string {
  if (score == null) return '—';
  const mod = Math.floor((score - 10) / 2);
  return mod >= 0 ? `+${mod}` : String(mod);
}
