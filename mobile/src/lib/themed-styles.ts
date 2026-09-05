import { Platform, StyleSheet } from 'react-native';

type ColorRole = 'bg' | 'border' | 'fg';

function colorVariable(role: ColorRole, value: string) {
  if (Platform.OS !== 'web') {
    return value;
  }

  const token = value.toLowerCase().replace(/[^a-z0-9]+/g, '');
  return `var(--rw-${role}-${token}, ${value})`;
}

export function themedForeground(value: string) {
  return colorVariable('fg', value);
}

export function themedBackground(value: string) {
  return colorVariable('bg', value);
}

export function themedBorder(value: string) {
  return colorVariable('border', value);
}

export function createThemedStyles<
  T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<unknown>,
>(definitions: T & StyleSheet.NamedStyles<unknown>): T {
  if (Platform.OS !== 'web') {
    return StyleSheet.create(definitions) as T;
  }

  const themed = Object.fromEntries(
    Object.entries(definitions).map(([styleName, definition]) => {
      const nextDefinition = Object.fromEntries(
        Object.entries(definition as Record<string, unknown>).map(([property, value]) => {
          if (typeof value !== 'string') {
            return [property, value];
          }

          if (property === 'experimental_backgroundImage' && value.includes('linear-gradient')) {
            return [property, `var(--rw-home-gradient, ${value})`];
          }

          if (!value.startsWith('#') && !value.startsWith('rgb')) {
            return [property, value];
          }

          if (property === 'backgroundColor') {
            return [property, themedBackground(value)];
          }
          if (property === 'color') {
            return [property, themedForeground(value)];
          }
          if (property.toLowerCase().includes('border') && property.toLowerCase().endsWith('color')) {
            return [property, themedBorder(value)];
          }

          return [property, value];
        }),
      );

      return [styleName, nextDefinition];
    }),
  );

  return StyleSheet.create(themed) as T;
}
