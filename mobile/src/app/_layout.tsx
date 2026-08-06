import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { useColorScheme } from 'react-native';

import { LanguageProvider } from '@/lib/i18n';

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const [fontsLoaded, fontError] = useFonts({
    MaterialSymbols_400Regular: require('../../assets/fonts/MaterialSymbols_400Regular.ttf'),
  });

  if (!fontsLoaded && !fontError) {
    return null;
  }

  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <LanguageProvider>
        <Stack screenOptions={{ headerShown: false }} />
      </LanguageProvider>
    </ThemeProvider>
  );
}
