/**
 * Shared TTRPG system labels and helpers used across multiple pages.
 */

/** Human-readable names for known TTRPG system tags. */
export const SYSTEM_LABELS: Record<string, string> = {
  pf2e: 'Pathfinder 2E',
  dnd5e: 'D&D 5e',
  unknown: 'Unknown',
};

/** System tags offered in autocomplete dropdowns (subset of SYSTEM_LABELS). */
export const SYSTEM_OPTIONS = Object.keys(SYSTEM_LABELS).filter((k) => k !== 'unknown');

/** MUI color mappings for system chips. */
export const SYSTEM_COLORS: Record<string, 'error' | 'primary' | 'default' | 'secondary' | 'info' | 'success' | 'warning'> = {
  pf2e: 'error',
  dnd5e: 'primary',
  unknown: 'default',
};

/** Return a display label for a system tag, falling back to the raw value. */
export function systemLabel(sys: string | null): string {
  if (!sys) return 'All systems';
  return SYSTEM_LABELS[sys] ?? sys;
}
