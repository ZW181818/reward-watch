import { Image } from 'expo-image';
import { SymbolView } from 'expo-symbols';
import { Text, View } from 'react-native';

import type { AdminCaseFormValues } from '@/components/admin-case-fields';
import { resolveAdminImage } from '@/lib/admin-api';
import { createThemedStyles, themedForeground } from '@/lib/themed-styles';


const CURRENCY_SYMBOLS = { CAD: 'CA$', CNY: '¥', USD: '$' } as const;

function rewardLabel(form: AdminCaseFormValues) {
  const rawReward = form.reward.replace(/,/g, '').trim();
  if (!rawReward) return form.rewardText.trim() || 'Not published';
  const parsed = Number(rawReward);
  if (!Number.isFinite(parsed)) return form.reward.trim();
  return `${CURRENCY_SYMBOLS[form.rewardCurrency]}${parsed.toLocaleString()}`;
}

export function AdminNoticePreview({
  coverUrl,
  form,
  imageUrls,
}: {
  coverUrl: string;
  form: AdminCaseFormValues;
  imageUrls: string[];
}) {
  const title = form.title.trim() || 'Untitled notice';
  const source = form.sourceAuthor.trim() || form.agency.trim() || 'Source organization';
  const region = form.regions.split(',').map((item) => item.trim()).filter(Boolean).join(' · ');
  const previewCover = coverUrl || imageUrls[0] || '';

  return (
    <View style={styles.wrapper}>
      <View style={styles.headingRow}>
        <View style={styles.headingCopy}>
          <Text style={styles.eyebrow}>PUBLIC PAGE PREVIEW</Text>
          <Text style={styles.heading}>Review before saving</Text>
        </View>
        <Text style={styles.draftBadge}>Hidden draft</Text>
      </View>

      <View style={styles.hero}>
        {previewCover ? (
          <Image accessibilityLabel={`${title} preview cover`} contentFit="cover" source={resolveAdminImage(previewCover)} style={styles.cover} />
        ) : (
          <View style={styles.coverPlaceholder}>
            <SymbolView name={{ ios: 'photo', android: 'image', web: 'image' }} size={27} tintColor={themedForeground('#98A2B3')} />
            <Text style={styles.placeholderText}>Add a photo to preview the cover</Text>
          </View>
        )}
        <View style={styles.heroCopy}>
          <Text style={styles.source}>{source}{region ? ` · ${region}` : ''}</Text>
          <Text style={styles.title}>{title}</Text>
          <Text numberOfLines={4} style={styles.summary}>{form.summary.trim() || 'The public summary will appear here as you type.'}</Text>
          <View style={styles.facts}>
            <View style={styles.fact}><Text style={styles.factLabel}>Reward</Text><Text style={styles.factValue}>{rewardLabel(form)}</Text></View>
            <View style={styles.fact}><Text style={styles.factLabel}>Status</Text><Text style={styles.factValue}>{form.status.trim() || 'Not set'}</Text></View>
            <View style={styles.fact}><Text style={styles.factLabel}>Published</Text><Text style={styles.factValue}>{form.publishedDate || 'Not set'}</Text></View>
          </View>
        </View>
      </View>

      {imageUrls.length > 1 ? (
        <View style={styles.gallery}>
          {imageUrls.slice(0, 5).map((url, index) => (
            <Image accessibilityLabel={`${title} preview photo ${index + 1}`} contentFit="cover" key={url} source={resolveAdminImage(url)} style={styles.thumbnail} />
          ))}
          {imageUrls.length > 5 ? <Text style={styles.morePhotos}>+{imageUrls.length - 5}</Text> : null}
        </View>
      ) : null}

      <View style={styles.previewFooter}>
        <Text style={styles.previewFooterLabel}>Source</Text>
        <Text numberOfLines={2} style={styles.previewFooterValue}>{form.sourceTitle.trim() || form.sourceUrl.trim() || 'Source details will appear here.'}</Text>
      </View>
    </View>
  );
}

const styles = createThemedStyles({
  wrapper: { backgroundColor: '#F8FAFC', borderColor: '#C7C2FF', borderRadius: 10, borderWidth: 1, gap: 14, padding: 15 },
  headingRow: { alignItems: 'center', flexDirection: 'row', gap: 12 },
  headingCopy: { flex: 1, gap: 2, minWidth: 0 },
  eyebrow: { color: '#6C63FF', fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  heading: { color: '#101828', fontSize: 14, fontWeight: '900' },
  draftBadge: { backgroundColor: '#FFF4E5', borderRadius: 999, color: '#B54708', fontSize: 10, fontWeight: '900', overflow: 'hidden', paddingHorizontal: 9, paddingVertical: 5 },
  hero: { alignItems: 'stretch', flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  cover: { backgroundColor: '#EAECF0', borderRadius: 9, height: 180, width: 150 },
  coverPlaceholder: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 9, borderStyle: 'dashed', borderWidth: 1, gap: 8, height: 180, justifyContent: 'center', padding: 15, width: 150 },
  placeholderText: { color: '#98A2B3', fontSize: 10, fontWeight: '700', lineHeight: 15, textAlign: 'center' },
  heroCopy: { flex: 1, gap: 8, minWidth: 240 },
  source: { color: '#667085', fontSize: 10, fontWeight: '800' },
  title: { color: '#101828', fontSize: 23, fontWeight: '900', lineHeight: 29 },
  summary: { color: '#475467', fontSize: 12, fontWeight: '600', lineHeight: 18 },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 3 },
  fact: { backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, gap: 3, minWidth: 105, paddingHorizontal: 10, paddingVertical: 8 },
  factLabel: { color: '#98A2B3', fontSize: 9, fontWeight: '900', textTransform: 'uppercase' },
  factValue: { color: '#344054', fontSize: 11, fontWeight: '900' },
  gallery: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  thumbnail: { backgroundColor: '#EAECF0', borderRadius: 7, height: 62, width: 54 },
  morePhotos: { color: '#667085', fontSize: 11, fontWeight: '900' },
  previewFooter: { backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderRadius: 8, borderWidth: 1, gap: 3, padding: 10 },
  previewFooterLabel: { color: '#98A2B3', fontSize: 9, fontWeight: '900', textTransform: 'uppercase' },
  previewFooterValue: { color: '#475467', fontSize: 11, fontWeight: '700', lineHeight: 16 },
});
