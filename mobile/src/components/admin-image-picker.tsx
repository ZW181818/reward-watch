import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';


export type AdminUploadFile = {
  blob: Blob;
  name: string;
  previewUrl?: string;
};

export function AdminImagePicker({ disabled }: { disabled?: boolean; onFiles: (files: AdminUploadFile[]) => void }) {
  return (
    <View style={[styles.notice, disabled && styles.disabled]}>
      <SymbolView
        name={{ ios: 'desktopcomputer', android: 'computer', web: 'computer' }}
        size={18}
        tintColor="#667085"
      />
      <Text style={styles.noticeText}>Photo uploads are available in the web admin console.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  notice: {
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderColor: '#E4E7EC',
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    minHeight: 42,
    paddingHorizontal: 12,
  },
  noticeText: {
    color: '#667085',
    fontSize: 12,
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.55,
  },
});
