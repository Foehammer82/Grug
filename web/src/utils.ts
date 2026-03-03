import cronstrue from 'cronstrue';

/**
 * Convert a 5-field cron expression to a human-readable English description.
 * Returns null if the expression is empty/null or cannot be parsed.
 */
export function cronToHuman(cron: string | null | undefined): string | null {
  if (!cron?.trim()) return null;
  try {
    return cronstrue.toString(cron, { use24HourTimeFormat: false });
  } catch {
    return null;
  }
}
