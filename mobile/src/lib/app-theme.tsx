import { useColorScheme } from '@/hooks/use-color-scheme';
import { Platform } from 'react-native';
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export type AppThemeMode = 'light' | 'dark';

type AppThemeContextValue = {
  mode: AppThemeMode;
  toggleTheme: () => void;
};

const STORAGE_KEY = 'reward-watch-theme';
const AppThemeContext = createContext<AppThemeContextValue | null>(null);

function readStoredTheme(): AppThemeMode | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined') {
    return null;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

export function AppThemeProvider({ children }: PropsWithChildren) {
  const systemScheme = useColorScheme();
  const [preference, setPreference] = useState<AppThemeMode | null>(null);
  const mode = preference ?? (systemScheme === 'dark' ? 'dark' : 'light');

  useEffect(() => {
    setPreference(readStoredTheme());
  }, []);

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') {
      return;
    }

    document.documentElement.dataset.theme = mode;
    document.documentElement.style.colorScheme = mode;
  }, [mode]);

  const toggleTheme = useCallback(() => {
    setPreference((currentPreference) => {
      const currentMode = currentPreference ?? (systemScheme === 'dark' ? 'dark' : 'light');
      const nextMode = currentMode === 'dark' ? 'light' : 'dark';

      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.localStorage.setItem(STORAGE_KEY, nextMode);
      }

      return nextMode;
    });
  }, [systemScheme]);

  const value = useMemo(() => ({ mode, toggleTheme }), [mode, toggleTheme]);
  return <AppThemeContext.Provider value={value}>{children}</AppThemeContext.Provider>;
}

export function useAppTheme() {
  const context = useContext(AppThemeContext);
  if (!context) {
    throw new Error('useAppTheme must be used inside AppThemeProvider');
  }
  return context;
}
