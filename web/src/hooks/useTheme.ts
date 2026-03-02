import { useEffect, useState } from 'react';

export type ThemePreference = 'system' | 'light' | 'dark';

const STORAGE_KEY = 'grug-theme';

function applyTheme(pref: ThemePreference) {
  const root = document.documentElement;
  if (pref === 'system') {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = pref;
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemePreference>(() => {
    return (localStorage.getItem(STORAGE_KEY) as ThemePreference) ?? 'system';
  });

  // Apply on mount (covers hard refreshes with a saved pref).
  useEffect(() => {
    applyTheme(theme);
  }, []);

  function setTheme(pref: ThemePreference) {
    applyTheme(pref);
    localStorage.setItem(STORAGE_KEY, pref);
    setThemeState(pref);
  }

  function cycleTheme() {
    const next: ThemePreference =
      theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system';
    setTheme(next);
  }

  return { theme, setTheme, cycleTheme };
}
