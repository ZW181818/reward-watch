import { useRef } from 'react';
import { SymbolView } from 'expo-symbols';
import { Pressable, StyleSheet, Text } from 'react-native';


export type AdminUploadFile = {
  blob: Blob;
  name: string;
};

export function AdminImagePicker({
  disabled,
  onFiles,
}: {
  disabled?: boolean;
  onFiles: (files: AdminUploadFile[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        accept="image/jpeg,image/png,image/webp"
        disabled={disabled}
        multiple
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files ?? []).slice(0, 8);
          onFiles(files.map((file) => ({ blob: file, name: file.name })));
          event.currentTarget.value = '';
        }}
        ref={inputRef}
        style={{ display: 'none' }}
        type="file"
      />
      <Pressable
        accessibilityRole="button"
        disabled={disabled}
        onPress={() => inputRef.current?.click()}
        style={[styles.button, disabled && styles.disabled]}>
        <SymbolView
          name={{ ios: 'photo.badge.plus', android: 'add_photo_alternate', web: 'add_photo_alternate' }}
          size={18}
          tintColor="#5B4DFF"
        />
        <Text style={styles.buttonText}>{disabled ? 'Uploading photos' : 'Upload photos'}</Text>
      </Pressable>
    </>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: '#F4F3FF',
    borderColor: '#D9D6FE',
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    minHeight: 42,
    paddingHorizontal: 13,
  },
  buttonText: {
    color: '#5B4DFF',
    fontSize: 12,
    fontWeight: '900',
  },
  disabled: {
    opacity: 0.55,
  },
});
