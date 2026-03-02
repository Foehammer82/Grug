import { ThemeProvider, useMediaQuery } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { darkTheme, lightTheme } from '../theme';

export type ThemePreference = 'system' | 'light' | 'dark';

interface ThemeContextValue {
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  preference: 'system',
  setPreference: () => {},
});

export function useThemePreference() {
  return useContext(ThemeContext);
}

const STORAGE_KEY = 'grug-theme';

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(
    () => (localStorage.getItem(STORAGE_KEY) as ThemePreference) ?? 'system'
  );

  const systemPrefersDark = useMediaQuery('(prefers-color-scheme: dark)');

  const resolvedMode =
    preference === 'system' ? (systemPrefersDark ? 'dark' : 'light') : preference;

  const muiTheme = useMemo(
    () => (resolvedMode === 'dark' ? darkTheme : lightTheme),
    [resolvedMode]
  );

  useEffect(() => {
    if (preference === 'system') {
      delete document.documentElement.dataset.theme;
    } else {
      document.documentElement.dataset.theme = preference;
    }
  }, [preference]);

  function setPreference(p: ThemePreference) {
    localStorage.setItem(STORAGE_KEY, p);
    setPreferenceState(p);
  }

  return (
    <ThemeContext.Provider value={{ preference, setPreference }}>
      <ThemeProvider theme={muiTheme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeContext.Provider>
  );
}
