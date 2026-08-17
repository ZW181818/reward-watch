import { Image } from 'expo-image';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { AdminImagePicker, type AdminUploadFile } from '@/components/admin-image-picker';
import { resolveAdminImage, uploadAdminImage } from '@/lib/admin-api';


const MAX_CASE_IMAGES = 8;

export function normalizeCaseImages(coverUrl?: string | null, imageUrls: string[] = []) {
  return Array.from(new Set([coverUrl, ...imageUrls].filter((url): url is string => Boolean(url))));
}

export function AdminPhotoManager({
  coverUrl,
  imageUrls,
  onBusyChange,
  onChange,
  onMessage,
  token,
}: {
  coverUrl: string;
  imageUrls: string[];
  onBusyChange: (busy: boolean) => void;
  onChange: (imageUrls: string[], coverUrl: string) => void;
  onMessage: (message: string | null) => void;
  token: string;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [pendingPreviews, setPendingPreviews] = useState<string[]>([]);
  const [remoteUrl, setRemoteUrl] = useState('');

  async function handleFiles(files: AdminUploadFile[]) {
    if (!files.length) return;
    if (imageUrls.length + files.length > MAX_CASE_IMAGES) {
      files.forEach((file) => file.previewUrl && URL.revokeObjectURL?.(file.previewUrl));
      onMessage(`A case can contain up to ${MAX_CASE_IMAGES} photos.`);
      return;
    }

    const previews = files.map((file) => file.previewUrl).filter((url): url is string => Boolean(url));
    setPendingPreviews(previews);
    setIsUploading(true);
    onBusyChange(true);
    onMessage('Uploading photos…');
    try {
      const uploaded: string[] = [];
      for (const file of files) {
        const response = await uploadAdminImage(token, file.blob, file.name);
        uploaded.push(response.url);
      }
      const nextImages = normalizeCaseImages(coverUrl, [...imageUrls, ...uploaded]);
      onChange(nextImages, coverUrl || uploaded[0] || '');
      onMessage(`${uploaded.length} photo${uploaded.length === 1 ? '' : 's'} uploaded. Save the case to publish the change.`);
    } catch (requestError) {
      onMessage(requestError instanceof Error ? requestError.message : 'Unable to upload photos');
    } finally {
      previews.forEach((url) => URL.revokeObjectURL?.(url));
      setPendingPreviews([]);
      setIsUploading(false);
      onBusyChange(false);
    }
  }

  function removeImage(url: string) {
    const nextImages = imageUrls.filter((item) => item !== url);
    onChange(nextImages, coverUrl === url ? nextImages[0] ?? '' : coverUrl);
  }

  function addRemoteUrl() {
    const url = remoteUrl.trim();
    if (!url) return;
    if (!/^(?:https?:\/\/|\/media\/)/i.test(url)) {
      onMessage('Image URLs must use http(s) or begin with /media/.');
      return;
    }
    if (imageUrls.length >= MAX_CASE_IMAGES) {
      onMessage(`A case can contain up to ${MAX_CASE_IMAGES} photos.`);
      return;
    }
    const nextImages = normalizeCaseImages(coverUrl, [...imageUrls, url]);
    onChange(nextImages, coverUrl || url);
    setRemoteUrl('');
    onMessage('Image URL added. Save the case to publish the change.');
  }

  return (
    <View style={styles.wrapper}>
      <View style={styles.headingRow}>
        <View style={styles.headingCopy}>
          <Text style={styles.title}>Photos</Text>
          <Text style={styles.hint}>Preview, choose a cover, or remove individual images. Up to 8 JPEG, PNG, or WebP files.</Text>
        </View>
        <Text style={styles.count}>{imageUrls.length}/{MAX_CASE_IMAGES}</Text>
      </View>

      {imageUrls.length || pendingPreviews.length ? (
        <ScrollView contentContainerStyle={styles.gallery} horizontal showsHorizontalScrollIndicator={false}>
          {imageUrls.map((url, index) => (
            <View key={url} style={[styles.imageCard, coverUrl === url && styles.imageCardCover]}>
              <Pressable accessibilityLabel={`Use photo ${index + 1} as cover`} onPress={() => onChange(imageUrls, url)}>
                <Image contentFit="cover" source={resolveAdminImage(url)} style={styles.image} />
                {coverUrl === url ? <Text style={styles.coverBadge}>Cover</Text> : null}
              </Pressable>
              <Pressable accessibilityLabel={`Remove photo ${index + 1}`} onPress={() => removeImage(url)} style={styles.removeButton}>
                <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={13} tintColor="#FFFFFF" />
              </Pressable>
            </View>
          ))}
          {pendingPreviews.map((url, index) => (
            <View key={url} style={[styles.imageCard, styles.pendingCard]}>
              <Image contentFit="cover" source={url} style={styles.image} />
              <Text style={styles.uploadingBadge}>Uploading {index + 1}</Text>
            </View>
          ))}
        </ScrollView>
      ) : (
        <View style={styles.emptyGallery}>
          <SymbolView name={{ ios: 'photo.on.rectangle.angled', android: 'photo_library', web: 'photo_library' }} size={24} tintColor="#98A2B3" />
          <Text style={styles.emptyText}>No photos attached</Text>
        </View>
      )}

      <View style={styles.actions}>
        <AdminImagePicker disabled={isUploading || imageUrls.length >= MAX_CASE_IMAGES} onFiles={handleFiles} />
        <View style={styles.urlRow}>
          <TextInput
            autoCapitalize="none"
            editable={!isUploading && imageUrls.length < MAX_CASE_IMAGES}
            keyboardType="url"
            onChangeText={setRemoteUrl}
            onSubmitEditing={addRemoteUrl}
            placeholder="Or paste an image URL"
            placeholderTextColor="#98A2B3"
            style={styles.urlInput}
            value={remoteUrl}
          />
          <Pressable disabled={!remoteUrl.trim() || isUploading} onPress={addRemoteUrl} style={[styles.addButton, (!remoteUrl.trim() || isUploading) && styles.disabled]}>
            <Text style={styles.addButtonText}>Add URL</Text>
          </Pressable>
        </View>
      </View>
      <Text style={styles.metadataNote}>Uploads are resized, re-encoded, and stripped of metadata by the API.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { backgroundColor: '#F8FAFC', borderColor: '#E4E7EC', borderRadius: 10, borderWidth: 1, gap: 13, padding: 15 },
  headingRow: { alignItems: 'flex-start', flexDirection: 'row', gap: 12 },
  headingCopy: { flex: 1, gap: 3, minWidth: 0 },
  title: { color: '#101828', fontSize: 13, fontWeight: '900' },
  hint: { color: '#667085', fontSize: 11, fontWeight: '600', lineHeight: 16 },
  count: { backgroundColor: '#EAECF0', borderRadius: 999, color: '#475467', fontSize: 10, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 8, paddingVertical: 5 },
  gallery: { gap: 10, padding: 2 },
  imageCard: { borderColor: '#D0D5DD', borderRadius: 9, borderWidth: 2, overflow: 'visible', padding: 2, position: 'relative' },
  imageCardCover: { borderColor: '#5B4DFF' },
  pendingCard: { borderColor: '#98A2B3', opacity: 0.78 },
  image: { backgroundColor: '#EAECF0', borderRadius: 5, height: 108, width: 92 },
  coverBadge: { backgroundColor: '#5B4DFF', borderRadius: 999, bottom: 7, color: '#FFFFFF', fontSize: 9, fontWeight: '900', left: 7, overflow: 'hidden', paddingHorizontal: 7, paddingVertical: 3, position: 'absolute' },
  uploadingBadge: { backgroundColor: '#344054', borderRadius: 999, bottom: 7, color: '#FFFFFF', fontSize: 9, fontWeight: '900', left: 7, overflow: 'hidden', paddingHorizontal: 7, paddingVertical: 3, position: 'absolute' },
  removeButton: { alignItems: 'center', backgroundColor: '#344054', borderRadius: 12, height: 24, justifyContent: 'center', position: 'absolute', right: -8, top: -8, width: 24 },
  emptyGallery: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderStyle: 'dashed', borderWidth: 1, gap: 6, justifyContent: 'center', minHeight: 96 },
  emptyText: { color: '#98A2B3', fontSize: 11, fontWeight: '700' },
  actions: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  urlRow: { flex: 1, flexDirection: 'row', gap: 8, minWidth: 260 },
  urlInput: { backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, color: '#101828', flex: 1, fontSize: 13, minHeight: 42, minWidth: 0, paddingHorizontal: 11 },
  addButton: { alignItems: 'center', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, justifyContent: 'center', minHeight: 42, paddingHorizontal: 12 },
  addButtonText: { color: '#475467', fontSize: 11, fontWeight: '900' },
  disabled: { opacity: 0.45 },
  metadataNote: { color: '#98A2B3', fontSize: 10, fontWeight: '600' },
});
