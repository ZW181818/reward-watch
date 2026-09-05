import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import '@/global.css';
import { AppThemeProvider, useAppTheme } from '@/lib/app-theme';
import { LanguageProvider } from '@/lib/i18n';

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    MaterialSymbols_400Regular: require('../../assets/fonts/MaterialSymbols_400Regular.ttf'),
  });

  if (!fontsLoaded && !fontError) {
    return null;
  }

  return (
    <AppThemeProvider>
      <LanguageProvider>
        <ThemedNavigation />
      </LanguageProvider>
    </AppThemeProvider>
  );
}

function ThemedNavigation() {
  const { mode } = useAppTheme();

  return (
    <ThemeProvider value={mode === 'dark' ? DarkTheme : DefaultTheme}>
      <Stack screenOptions={{ headerShown: false }} />
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
    </ThemeProvider>
  );
}
