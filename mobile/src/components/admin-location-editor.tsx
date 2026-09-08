import { SymbolView } from 'expo-symbols';
import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';

import AdminLocationMap from '@/components/admin-location-map';
import {
  resetAdminMapLocations,
  updateAdminMapLocations,
  type AdminMapLocationDetail,
} from '@/lib/admin-api';
import { createThemedStyles, themedForeground } from '@/lib/themed-styles';

type EditableLocation = {
  label: string;
  latitude: string;
  longitude: string;
};

type AdminLocationEditorProps = {
  caseId: string;
  location: AdminMapLocationDetail;
  onChanged: () => Promise<void>;
  sourceLocation?: string | null;
  token: string;
};

function editableLocations(location: AdminMapLocationDetail): EditableLocation[] {
  const source = location.manualLocations ?? location.effectiveLocations;
  if (!source.length) return [{ label: '', latitude: '', longitude: '' }];
  return source.map((item) => ({
    label: item.label,
    latitude: String(item.latitude),
    longitude: String(item.longitude),
  }));
}

const STATUS_LABELS = {
  automatic: 'Automatic city match',
  broad: 'Broad region only',
  manual: 'Manually reviewed',
  unresolved: 'Needs review',
} as const;

export function AdminLocationEditor({
  caseId,
  location,
  onChanged,
  sourceLocation,
  token,
}: AdminLocationEditorProps) {
  const [locations, setLocations] = useState(() => editableLocations(location));
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [note, setNote] = useState(location.note ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setLocations(editableLocations(location));
    setSelectedIndex(0);
    setNote(location.note ?? '');
  }, [caseId, location]);

  const selected = locations[selectedIndex] ?? locations[0];
  const coordinate = useMemo(() => {
    if (!selected) return null;
    if (!selected.latitude.trim() || !selected.longitude.trim()) return null;
    const latitude = Number(selected.latitude);
    const longitude = Number(selected.longitude);
    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180
    ) {
      return null;
    }
    return { latitude, longitude };
  }, [selected]);

  function updateLocation(index: number, patch: Partial<EditableLocation>) {
    setLocations((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    );
  }

  function addLocation() {
    if (locations.length >= 8) return;
    setLocations((current) => [...current, { label: '', latitude: '', longitude: '' }]);
    setSelectedIndex(locations.length);
  }

  function removeLocation(index: number) {
    setLocations((current) => {
      const next = current.filter((_, itemIndex) => itemIndex !== index);
      return next.length ? next : [{ label: '', latitude: '', longitude: '' }];
    });
    setSelectedIndex((current) => {
      if (current > index) return current - 1;
      if (current === index) return Math.max(0, current - 1);
      return current;
    });
  }

  async function save() {
    const normalized = locations.map((item) => ({
      label: item.label.trim(),
      latitude: Number(item.latitude),
      longitude: Number(item.longitude),
    }));
    const invalid = normalized.some(
      (item, index) =>
        item.label.length < 2 ||
        !locations[index].latitude.trim() ||
        !locations[index].longitude.trim() ||
        !Number.isFinite(item.latitude) ||
        !Number.isFinite(item.longitude) ||
        item.latitude < -90 ||
        item.latitude > 90 ||
        item.longitude < -180 ||
        item.longitude > 180
    );
    if (invalid) {
      setMessage('Every location needs a label and valid latitude/longitude values.');
      return;
    }
    setIsSaving(true);
    setMessage(null);
    try {
      await updateAdminMapLocations(token, caseId, {
        locations: normalized,
        note: note.trim() || null,
      });
      setMessage('Map location saved and published to the nearby index.');
      await onChanged();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to save location');
    } finally {
      setIsSaving(false);
    }
  }

  async function reset() {
    setIsSaving(true);
    setMessage(null);
    try {
      await resetAdminMapLocations(token, caseId);
      setMessage('Manual location removed. Automatic matching is active again.');
      await onChanged();
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : 'Unable to reset location');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <View style={styles.card}>
      <View style={styles.headingRow}>
        <View style={styles.headingCopy}>
          <Text style={styles.eyebrow}>NEARBY MAP</Text>
          <Text style={styles.title}>Map location</Text>
          <Text style={styles.subtitle}>
            Choose a public city or general area. Never enter a home, live position, or precise movement history.
          </Text>
        </View>
        <Text style={[styles.status, styles[`status_${location.status}`]]}>
          {STATUS_LABELS[location.status]}
        </Text>
      </View>

      <View style={styles.referenceBox}>
        <SymbolView
          name={{ ios: 'doc.text.magnifyingglass', android: 'find_in_page', web: 'find_in_page' }}
          size={18}
          tintColor={themedForeground('#5B4DFF')}
        />
        <View style={styles.referenceCopy}>
          <Text style={styles.referenceLabel}>Official notice says</Text>
          <Text style={styles.referenceValue}>{sourceLocation || 'No location text supplied by the source'}</Text>
          {location.automaticLocations.length ? (
            <Text style={styles.referenceMeta}>
              Automatic result: {location.automaticLocations.map((item) => item.label).join(' · ')}
            </Text>
          ) : null}
        </View>
      </View>

      <View style={styles.locationTabs}>
        {locations.map((item, index) => (
          <Pressable
            key={`${index}-${item.label}`}
            onPress={() => setSelectedIndex(index)}
            style={[styles.locationTab, selectedIndex === index && styles.locationTabActive]}>
            <Text
              numberOfLines={1}
              style={[styles.locationTabText, selectedIndex === index && styles.locationTabTextActive]}>
              {item.label.trim() || `Location ${index + 1}`}
            </Text>
            {locations.length > 1 ? (
              <Pressable
                accessibilityLabel={`Remove location ${index + 1}`}
                onPress={() => removeLocation(index)}
                style={styles.removeButton}>
                <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={13} tintColor={themedForeground('#667085')} />
              </Pressable>
            ) : null}
          </Pressable>
        ))}
        {locations.length < 8 ? (
          <Pressable onPress={addLocation} style={styles.addButton}>
            <SymbolView name={{ ios: 'plus', android: 'add', web: 'add' }} size={14} tintColor={themedForeground('#5B4DFF')} />
            <Text style={styles.addButtonText}>Add area</Text>
          </Pressable>
        ) : null}
      </View>

      {selected ? (
        <View style={styles.fieldsRow}>
          <View style={styles.labelField}>
            <Text style={styles.fieldLabel}>Public label</Text>
            <TextInput
              maxLength={180}
              onChangeText={(value) => updateLocation(selectedIndex, { label: value })}
              placeholder="e.g. Seattle, Washington"
              placeholderTextColor={themedForeground('#98A2B3')}
              style={styles.input}
              value={selected.label}
            />
          </View>
          <View style={styles.coordinateField}>
            <Text style={styles.fieldLabel}>Latitude</Text>
            <TextInput
              keyboardType="numbers-and-punctuation"
              onChangeText={(value) => updateLocation(selectedIndex, { latitude: value })}
              placeholder="47.6062"
              placeholderTextColor={themedForeground('#98A2B3')}
              style={styles.input}
              value={selected.latitude}
            />
          </View>
          <View style={styles.coordinateField}>
            <Text style={styles.fieldLabel}>Longitude</Text>
            <TextInput
              keyboardType="numbers-and-punctuation"
              onChangeText={(value) => updateLocation(selectedIndex, { longitude: value })}
              placeholder="-122.3321"
              placeholderTextColor={themedForeground('#98A2B3')}
              style={styles.input}
              value={selected.longitude}
            />
          </View>
        </View>
      ) : null}

      <View style={styles.mapWrap}>
        <AdminLocationMap
          coordinate={coordinate}
          onCoordinateChange={(next) =>
            updateLocation(selectedIndex, {
              latitude: next.latitude.toFixed(6),
              longitude: next.longitude.toFixed(6),
            })
          }
        />
        <View pointerEvents="none" style={styles.mapHint}>
          <Text style={styles.mapHintText}>Click the map or drag the pin</Text>
        </View>
      </View>

      <View style={styles.noteField}>
        <Text style={styles.fieldLabel}>Review note (optional)</Text>
        <TextInput
          maxLength={1000}
          multiline
          onChangeText={setNote}
          placeholder="How this city/area was verified"
          placeholderTextColor={themedForeground('#98A2B3')}
          style={[styles.input, styles.noteInput]}
          textAlignVertical="top"
          value={note}
        />
      </View>

      {message ? <Text style={styles.message}>{message}</Text> : null}
      <View style={styles.actions}>
        {location.manualLocations ? (
          <Pressable disabled={isSaving} onPress={reset} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>Use automatic result</Text>
          </Pressable>
        ) : null}
        <Pressable disabled={isSaving} onPress={save} style={[styles.primaryButton, isSaving && styles.disabled]}>
          {isSaving ? (
            <ActivityIndicator color={themedForeground('#FFFFFF')} />
          ) : (
            <Text style={styles.primaryButtonText}>Save map location</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = createThemedStyles({
  card: { backgroundColor: '#F8FAFC', borderColor: '#DCE3ED', borderRadius: 10, borderWidth: 1, gap: 14, padding: 16 },
  headingRow: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  headingCopy: { flex: 1, gap: 3, minWidth: 240 },
  eyebrow: { color: '#7F75FF', fontSize: 9, fontWeight: '900' },
  title: { color: '#101828', fontSize: 16, fontWeight: '900' },
  subtitle: { color: '#667085', fontSize: 11, fontWeight: '600', lineHeight: 17, maxWidth: 700 },
  status: { borderRadius: 999, fontSize: 10, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 9, paddingVertical: 5 },
  status_manual: { backgroundColor: '#ECFDF3', color: '#027A48' },
  status_automatic: { backgroundColor: '#EEF4FF', color: '#3538CD' },
  status_broad: { backgroundColor: '#FFF6ED', color: '#B93815' },
  status_unresolved: { backgroundColor: '#FEF3F2', color: '#B42318' },
  referenceBox: { alignItems: 'flex-start', backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, flexDirection: 'row', gap: 10, padding: 12 },
  referenceCopy: { flex: 1, gap: 2, minWidth: 0 },
  referenceLabel: { color: '#667085', fontSize: 10, fontWeight: '900', textTransform: 'uppercase' },
  referenceValue: { color: '#344054', fontSize: 12, fontWeight: '800', lineHeight: 18 },
  referenceMeta: { color: '#98A2B3', fontSize: 10, fontWeight: '700', marginTop: 2 },
  locationTabs: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  locationTab: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 999, borderWidth: 1, flexDirection: 'row', gap: 5, maxWidth: 190, minHeight: 34, paddingHorizontal: 10 },
  locationTabActive: { backgroundColor: '#F0EFFF', borderColor: '#B8B3FF' },
  locationTabText: { color: '#667085', flexShrink: 1, fontSize: 10, fontWeight: '800' },
  locationTabTextActive: { color: '#5B4DFF' },
  removeButton: { alignItems: 'center', height: 22, justifyContent: 'center', width: 22 },
  addButton: { alignItems: 'center', flexDirection: 'row', gap: 4, minHeight: 34, paddingHorizontal: 8 },
  addButtonText: { color: '#5B4DFF', fontSize: 10, fontWeight: '900' },
  fieldsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  labelField: { flex: 2, gap: 6, minWidth: 220 },
  coordinateField: { flex: 1, gap: 6, minWidth: 130 },
  noteField: { gap: 6 },
  fieldLabel: { color: '#344054', fontSize: 11, fontWeight: '800' },
  input: { backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, color: '#101828', fontSize: 13, minHeight: 42, paddingHorizontal: 11, paddingVertical: 9 },
  noteInput: { minHeight: 70 },
  mapWrap: { borderColor: '#D0D5DD', borderRadius: 10, borderWidth: 1, height: 390, overflow: 'hidden', position: 'relative' },
  mapHint: { backgroundColor: '#101828', borderRadius: 999, bottom: 12, left: 12, opacity: 0.88, paddingHorizontal: 11, paddingVertical: 6, position: 'absolute' },
  mapHintText: { color: '#FFFFFF', fontSize: 10, fontWeight: '900' },
  message: { color: '#475467', fontSize: 11, fontWeight: '700' },
  actions: { alignItems: 'center', borderTopColor: '#E4E7EC', borderTopWidth: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 9, justifyContent: 'flex-end', paddingTop: 13 },
  secondaryButton: { alignItems: 'center', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, justifyContent: 'center', minHeight: 42, paddingHorizontal: 13 },
  secondaryButtonText: { color: '#475467', fontSize: 11, fontWeight: '900' },
  primaryButton: { alignItems: 'center', backgroundColor: '#5B4DFF', borderRadius: 8, justifyContent: 'center', minHeight: 42, minWidth: 150, paddingHorizontal: 14 },
  primaryButtonText: { color: '#FFFFFF', fontSize: 11, fontWeight: '900' },
  disabled: { opacity: 0.45 },
});
