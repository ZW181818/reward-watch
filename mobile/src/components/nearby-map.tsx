import { StyleSheet, Text, View } from 'react-native';

import type { NearbyMapProps } from './nearby-map-types';

export default function NearbyMap({ labels }: NearbyMapProps) {
  return (
    <View style={styles.fallback}>
      <Text style={styles.fallbackText}>{labels.mapUnavailable}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  fallback: {
    alignItems: 'center',
    backgroundColor: '#EEF2F7',
    flex: 1,
    justifyContent: 'center',
    minHeight: 420,
    padding: 32,
  },
  fallbackText: {
    color: '#475467',
    fontSize: 16,
    lineHeight: 24,
    textAlign: 'center',
  },
});
