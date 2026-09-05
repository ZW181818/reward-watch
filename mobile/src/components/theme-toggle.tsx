import { SymbolView } from 'expo-symbols';
import { Platform, Pressable, StyleSheet } from 'react-native';

import { useAppTheme } from '@/lib/app-theme';

export function ThemeToggle() {
  const { mode, toggleTheme } = useAppTheme();

  if (Platform.OS !== 'web') {
    return null;
  }

  const isDark = mode === 'dark';
  return (
    <Pressable
      accessibilityHint={isDark ? 'Switch to the light color theme' : 'Switch to the dark color theme'}
      accessibilityLabel={isDark ? 'Use light mode' : 'Use dark mode'}
      accessibilityRole="button"
      onPress={toggleTheme}
      style={({ pressed }) => [
        styles.button,
        isDark ? styles.buttonDark : styles.buttonLight,
        pressed && styles.buttonPressed,
      ]}>
      <SymbolView
        name={isDark
          ? { ios: 'sun.max.fill', android: 'light_mode', web: 'light_mode' }
          : { ios: 'moon.stars.fill', android: 'dark_mode', web: 'dark_mode' }}
        size={19}
        tintColor={isDark ? '#F8FAFC' : '#344054'}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    borderRadius: 10,
    borderWidth: 1,
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  buttonLight: {
    backgroundColor: 'rgba(255, 255, 255, 0.94)',
    borderColor: '#D8DFEA',
    boxShadow: '0 8px 24px rgba(34, 42, 68, 0.18)',
  },
  buttonDark: {
    backgroundColor: 'rgba(24, 33, 49, 0.96)',
    borderColor: '#3A4860',
    boxShadow: '0 8px 26px rgba(0, 0, 0, 0.44)',
  },
  buttonPressed: {
    opacity: 0.72,
    transform: [{ scale: 0.96 }],
  },
});
