import { StyleSheet, Text, View } from 'react-native';

import type { AdminLocationMapProps } from './admin-location-map-types';

export default function AdminLocationMap({ coordinate }: AdminLocationMapProps) {
  return (
    <View style={styles.fallback}>
      <Text style={styles.title}>Map point selection is available in the web admin.</Text>
      <Text style={styles.text}>
        {coordinate
          ? `${coordinate.latitude.toFixed(6)}, ${coordinate.longitude.toFixed(6)}`
          : 'Enter latitude and longitude to define this location.'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  fallback: {
    alignItems: 'center',
    backgroundColor: '#EEF2F7',
    flex: 1,
    gap: 8,
    justifyContent: 'center',
    minHeight: 340,
    padding: 28,
  },
  title: { color: '#344054', fontSize: 14, fontWeight: '800', textAlign: 'center' },
  text: { color: '#667085', fontSize: 12, lineHeight: 18, textAlign: 'center' },
});
