import { Image } from 'expo-image';
import { SymbolView } from 'expo-symbols';
import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { AdminImagePicker, type AdminUploadFile } from '@/components/admin-image-picker';
import { fetchAdminMediaStatus, resolveAdminImage, uploadAdminImage } from '@/lib/admin-api';
import { createThemedStyles, themedForeground } from '@/lib/themed-styles';


const MAX_CASE_IMAGES = 8;

type PendingUpload = AdminUploadFile & {
  error?: string;
  id: string;
  status: 'failed' | 'uploading';
};

export function normalizeCaseImages(coverUrl?: string | null, imageUrls: string[] = []) {
  return Array.from(new Set([coverUrl, ...imageUrls].filter((url): url is string => Boolean(url))));
}

export function AdminPhotoManager({
  coverUrl,
  imageUrls,
  onBusyChange,
  onChange,
  onMessage,
  onPreviewChange,
  token,
}: {
  coverUrl: string;
  imageUrls: string[];
  onBusyChange: (busy: boolean) => void;
  onChange: (imageUrls: string[], coverUrl: string) => void;
  onMessage: (message: string | null) => void;
  onPreviewChange?: (imageUrls: string[], coverUrl: string) => void;
  token: string;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([]);
  const [remoteUrl, setRemoteUrl] = useState('');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const pendingIdRef = useRef(0);
  const pendingUploadsRef = useRef<PendingUpload[]>([]);
  const onPreviewChangeRef = useRef(onPreviewChange);

  useEffect(() => {
    onPreviewChangeRef.current = onPreviewChange;
  }, [onPreviewChange]);

  useEffect(() => {
    let active = true;
    fetchAdminMediaStatus(token)
      .then((status) => {
        if (!active) return;
        setStorageWarning(status.ready
          ? null
          : `Persistent image storage is unavailable. Configure ${status.missing.join(', ')} in Render before publishing uploaded photos.`);
      })
      .catch(() => {
        if (active) setStorageWarning('Unable to verify persistent image storage. Uploads may require a retry.');
      });
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    const localPreviews = pendingUploads
      .map((file) => file.previewUrl)
      .filter((url): url is string => Boolean(url));
    const previewImages = normalizeCaseImages(coverUrl, [...imageUrls, ...localPreviews]);
    onPreviewChangeRef.current?.(
      previewImages,
      coverUrl || localPreviews[0] || previewImages[0] || ''
    );
  }, [coverUrl, imageUrls, pendingUploads]);

  useEffect(() => () => {
    pendingUploadsRef.current.forEach((file) => {
      if (file.previewUrl) URL.revokeObjectURL?.(file.previewUrl);
    });
  }, []);

  function replacePendingUploads(next: PendingUpload[]) {
    pendingUploadsRef.current = next;
    setPendingUploads(next);
    onBusyChange(next.length > 0);
  }

  async function uploadFiles(files: PendingUpload[]) {
    if (!files.length) return;
    const targetIds = new Set(files.map((file) => file.id));
    replacePendingUploads(pendingUploadsRef.current.map((file) => (
      targetIds.has(file.id) ? { ...file, error: undefined, status: 'uploading' } : file
    )));
    setIsUploading(true);
    setUploadError(null);
    onMessage('Uploading photos…');

    const uploaded: string[] = [];
    const failed: PendingUpload[] = [];
    for (const file of files) {
      try {
        const response = await uploadAdminImage(token, file.blob, file.name);
        if (!response.url) throw new Error('The upload completed without an image URL.');
        uploaded.push(response.url);
      } catch (requestError) {
        failed.push({
          ...file,
          error: requestError instanceof Error ? requestError.message : 'Unable to upload photo',
          status: 'failed',
        });
      }
    }

    if (uploaded.length) {
      const nextImages = normalizeCaseImages(coverUrl, [...imageUrls, ...uploaded]);
      onChange(nextImages, coverUrl || uploaded[0] || '');
    }

    const failedById = new Map(failed.map((file) => [file.id, file]));
    const nextPending = pendingUploadsRef.current.flatMap((file) => {
      if (!targetIds.has(file.id)) return [file];
      const failure = failedById.get(file.id);
      if (failure) return [failure];
      if (file.previewUrl) URL.revokeObjectURL?.(file.previewUrl);
      return [];
    });
    replacePendingUploads(nextPending);
    setIsUploading(false);

    if (failed.length) {
      const firstError = failed[0].error ?? 'Unable to upload photo';
      const message = `${failed.length} photo${failed.length === 1 ? '' : 's'} could not be uploaded. The preview has been kept so you can retry or remove it. ${firstError}`;
      setUploadError(message);
      onMessage(message);
    } else {
      const message = `${uploaded.length} photo${uploaded.length === 1 ? '' : 's'} uploaded. Review the preview, then save the draft.`;
      setUploadError(null);
      onMessage(message);
    }
  }

  async function handleFiles(files: AdminUploadFile[]) {
    if (!files.length) return;
    if (imageUrls.length + pendingUploadsRef.current.length + files.length > MAX_CASE_IMAGES) {
      files.forEach((file) => file.previewUrl && URL.revokeObjectURL?.(file.previewUrl));
      onMessage(`A case can contain up to ${MAX_CASE_IMAGES} photos.`);
      return;
    }

    const pending = files.map((file, index): PendingUpload => ({
      ...file,
      id: `pending-${pendingIdRef.current++}-${index}-${file.name}`,
      status: 'uploading',
    }));
    replacePendingUploads([...pendingUploadsRef.current, ...pending]);
    await uploadFiles(pending);
  }

  function removePendingUpload(id: string) {
    const target = pendingUploadsRef.current.find((file) => file.id === id);
    if (!target || target.status === 'uploading') return;
    if (target.previewUrl) URL.revokeObjectURL?.(target.previewUrl);
    const nextPending = pendingUploadsRef.current.filter((file) => file.id !== id);
    replacePendingUploads(nextPending);
    if (!nextPending.length) {
      setUploadError(null);
      onMessage(null);
    }
  }

  async function retryFailedUploads() {
    await uploadFiles(pendingUploadsRef.current.filter((file) => file.status === 'failed'));
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
    if (imageUrls.length + pendingUploads.length >= MAX_CASE_IMAGES) {
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
        <Text style={styles.count}>{imageUrls.length + pendingUploads.length}/{MAX_CASE_IMAGES}</Text>
      </View>

      {imageUrls.length || pendingUploads.length ? (
        <ScrollView contentContainerStyle={styles.gallery} horizontal showsHorizontalScrollIndicator={false}>
          {imageUrls.map((url, index) => (
            <View key={url} style={[styles.imageCard, coverUrl === url && styles.imageCardCover]}>
              <Pressable accessibilityLabel={`Use photo ${index + 1} as cover`} onPress={() => onChange(imageUrls, url)}>
                <Image contentFit="cover" source={resolveAdminImage(url)} style={styles.image} />
                {coverUrl === url ? <Text style={styles.coverBadge}>Cover</Text> : null}
              </Pressable>
              <Pressable accessibilityLabel={`Remove photo ${index + 1}`} onPress={() => removeImage(url)} style={styles.removeButton}>
                <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={13} tintColor={themedForeground('#FFFFFF')} />
              </Pressable>
            </View>
          ))}
          {pendingUploads.map((file, index) => (
            <View key={file.id} style={[styles.imageCard, styles.pendingCard, file.status === 'failed' && styles.failedCard]}>
              <Image contentFit="cover" source={file.previewUrl} style={styles.image} />
              <Text style={[styles.uploadingBadge, file.status === 'failed' && styles.failedBadge]}>
                {file.status === 'uploading' ? `Uploading ${index + 1}` : 'Retry required'}
              </Text>
              <Pressable
                accessibilityLabel={`Remove pending photo ${index + 1}`}
                disabled={file.status === 'uploading'}
                onPress={() => removePendingUpload(file.id)}
                style={[styles.removeButton, file.status === 'uploading' && styles.disabled]}>
                <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={13} tintColor={themedForeground('#FFFFFF')} />
              </Pressable>
            </View>
          ))}
        </ScrollView>
      ) : (
        <View style={styles.emptyGallery}>
          <SymbolView name={{ ios: 'photo.on.rectangle.angled', android: 'photo_library', web: 'photo_library' }} size={24} tintColor={themedForeground('#98A2B3')} />
          <Text style={styles.emptyText}>No photos attached</Text>
        </View>
      )}

      <View style={styles.actions}>
        <AdminImagePicker disabled={isUploading || imageUrls.length + pendingUploads.length >= MAX_CASE_IMAGES} onFiles={handleFiles} />
        {pendingUploads.some((file) => file.status === 'failed') ? (
          <Pressable disabled={isUploading} onPress={retryFailedUploads} style={[styles.retryButton, isUploading && styles.disabled]}>
            <SymbolView name={{ ios: 'arrow.clockwise', android: 'refresh', web: 'refresh' }} size={17} tintColor={themedForeground('#B54708')} />
            <Text style={styles.retryButtonText}>Retry failed uploads</Text>
          </Pressable>
        ) : null}
        <View style={styles.urlRow}>
          <TextInput
            autoCapitalize="none"
            editable={!isUploading && imageUrls.length + pendingUploads.length < MAX_CASE_IMAGES}
            keyboardType="url"
            onChangeText={setRemoteUrl}
            onSubmitEditing={addRemoteUrl}
            placeholder="Or paste an image URL"
            placeholderTextColor={themedForeground('#98A2B3')}
            style={styles.urlInput}
            value={remoteUrl}
          />
          <Pressable disabled={!remoteUrl.trim() || isUploading} onPress={addRemoteUrl} style={[styles.addButton, (!remoteUrl.trim() || isUploading) && styles.disabled]}>
            <Text style={styles.addButtonText}>Add URL</Text>
          </Pressable>
        </View>
      </View>
      {uploadError ? (
        <View style={styles.uploadError}>
          <SymbolView name={{ ios: 'exclamationmark.triangle.fill', android: 'warning', web: 'warning' }} size={16} tintColor={themedForeground('#B54708')} />
          <Text style={styles.uploadErrorText}>{uploadError}</Text>
        </View>
      ) : null}
      {storageWarning ? (
        <View style={styles.storageWarning}>
          <SymbolView name={{ ios: 'externaldrive.badge.exclamationmark', android: 'cloud_off', web: 'cloud_off' }} size={16} tintColor={themedForeground('#B42318')} />
          <Text style={styles.storageWarningText}>{storageWarning}</Text>
        </View>
      ) : null}
      <Text style={styles.metadataNote}>Uploads are resized, re-encoded, and stripped of metadata by the API.</Text>
    </View>
  );
}

const styles = createThemedStyles({
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
  failedCard: { borderColor: '#F79009', opacity: 1 },
  image: { backgroundColor: '#EAECF0', borderRadius: 5, height: 108, width: 92 },
  coverBadge: { backgroundColor: '#5B4DFF', borderRadius: 999, bottom: 7, color: '#FFFFFF', fontSize: 9, fontWeight: '900', left: 7, overflow: 'hidden', paddingHorizontal: 7, paddingVertical: 3, position: 'absolute' },
  uploadingBadge: { backgroundColor: '#344054', borderRadius: 999, bottom: 7, color: '#FFFFFF', fontSize: 9, fontWeight: '900', left: 7, overflow: 'hidden', paddingHorizontal: 7, paddingVertical: 3, position: 'absolute' },
  failedBadge: { backgroundColor: '#B54708' },
  removeButton: { alignItems: 'center', backgroundColor: '#344054', borderRadius: 12, height: 24, justifyContent: 'center', position: 'absolute', right: -8, top: -8, width: 24 },
  emptyGallery: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderStyle: 'dashed', borderWidth: 1, gap: 6, justifyContent: 'center', minHeight: 96 },
  emptyText: { color: '#98A2B3', fontSize: 11, fontWeight: '700' },
  actions: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  urlRow: { flex: 1, flexDirection: 'row', gap: 8, minWidth: 260 },
  urlInput: { backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, color: '#101828', flex: 1, fontSize: 13, minHeight: 42, minWidth: 0, paddingHorizontal: 11 },
  addButton: { alignItems: 'center', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, justifyContent: 'center', minHeight: 42, paddingHorizontal: 12 },
  addButtonText: { color: '#475467', fontSize: 11, fontWeight: '900' },
  retryButton: { alignItems: 'center', backgroundColor: '#FFFAEB', borderColor: '#FEDF89', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 7, minHeight: 42, paddingHorizontal: 12 },
  retryButtonText: { color: '#B54708', fontSize: 11, fontWeight: '900' },
  disabled: { opacity: 0.45 },
  uploadError: { alignItems: 'flex-start', backgroundColor: '#FFFAEB', borderColor: '#FEDF89', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 8, padding: 10 },
  uploadErrorText: { color: '#B54708', flex: 1, fontSize: 11, fontWeight: '700', lineHeight: 17 },
  storageWarning: { alignItems: 'flex-start', backgroundColor: '#FEF3F2', borderColor: '#FECDCA', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 8, padding: 10 },
  storageWarningText: { color: '#B42318', flex: 1, fontSize: 11, fontWeight: '700', lineHeight: 17 },
  metadataNote: { color: '#98A2B3', fontSize: 10, fontWeight: '600' },
});
