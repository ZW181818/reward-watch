import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import type { OfficialSourceRecord, RewardCase, RewardCountry, RewardCurrency } from '@/types/reward-case';
import { getDefaultRewardCurrency } from '@/lib/case-display';


export const DEFAULT_CASE_WARNING =
  'Do not approach any individual. Submit information directly to the published source.';

export type AdminCaseFormValues = {
  title: string;
  agency: string;
  country: RewardCountry;
  regions: string;
  caseType: string;
  description: string;
  summary: string;
  reward: string;
  rewardCurrency: RewardCurrency;
  rewardText: string;
  status: string;
  warningMessage: string;
  aliases: string;
  age: string;
  dateOfBirth: string;
  placeOfBirth: string;
  sex: string;
  race: string;
  nationality: string;
  hair: string;
  eyes: string;
  height: string;
  weight: string;
  locations: string;
  distinguishingFeatures: string;
  fieldOffice: string;
  publishedDate: string;
  lastVerified: string;
  sourceUpdatedDate: string;
  sourceUrl: string;
  sourceTitle: string;
  sourceAuthor: string;
  sourceKind: 'official' | 'publisher';
  sourceRecordsJson: string;
};

export type AdminCaseMutation = Omit<RewardCase, 'id' | 'imageUrl' | 'imageUrls'>;

function optional(value: string) {
  return value.trim() || null;
}

function commaSeparated(value: string) {
  return Array.from(new Set(value.split(',').map((item) => item.trim()).filter(Boolean)));
}

export function emptyAdminCaseForm(): AdminCaseFormValues {
  const today = new Date().toISOString().slice(0, 10);
  return {
    title: '',
    agency: '',
    country: 'US',
    regions: '',
    caseType: 'Public reward notice',
    description: '',
    summary: '',
    reward: '',
    rewardCurrency: 'USD',
    rewardText: '',
    status: 'Information Requested',
    warningMessage: DEFAULT_CASE_WARNING,
    aliases: '',
    age: '',
    dateOfBirth: '',
    placeOfBirth: '',
    sex: '',
    race: '',
    nationality: '',
    hair: '',
    eyes: '',
    height: '',
    weight: '',
    locations: '',
    distinguishingFeatures: '',
    fieldOffice: '',
    publishedDate: today,
    lastVerified: today,
    sourceUpdatedDate: today,
    sourceUrl: '',
    sourceTitle: '',
    sourceAuthor: '',
    sourceKind: 'publisher',
    sourceRecordsJson: '[]',
  };
}

export function adminCaseFormFromCase(rewardCase: RewardCase): AdminCaseFormValues {
  return {
    title: rewardCase.title,
    agency: rewardCase.agency,
    country: rewardCase.country,
    regions: (rewardCase.regions ?? []).join(', '),
    caseType: rewardCase.caseType ?? '',
    description: rewardCase.description ?? '',
    summary: rewardCase.summary,
    reward: rewardCase.reward?.toString() ?? '',
    rewardCurrency: rewardCase.rewardCurrency ?? getDefaultRewardCurrency(rewardCase.country),
    rewardText: rewardCase.rewardText ?? '',
    status: rewardCase.status,
    warningMessage: rewardCase.warningMessage ?? '',
    aliases: (rewardCase.aliases ?? []).join(', '),
    age: rewardCase.age ?? '',
    dateOfBirth: rewardCase.dateOfBirth ?? '',
    placeOfBirth: rewardCase.placeOfBirth ?? '',
    sex: rewardCase.sex ?? '',
    race: rewardCase.race ?? '',
    nationality: rewardCase.nationality ?? '',
    hair: rewardCase.hair ?? '',
    eyes: rewardCase.eyes ?? '',
    height: rewardCase.height ?? '',
    weight: rewardCase.weight ?? '',
    locations: rewardCase.locations ?? '',
    distinguishingFeatures: rewardCase.distinguishingFeatures ?? '',
    fieldOffice: rewardCase.fieldOffice ?? '',
    publishedDate: rewardCase.publishedDate,
    lastVerified: rewardCase.lastVerified,
    sourceUpdatedDate: rewardCase.sourceUpdatedDate ?? '',
    sourceUrl: rewardCase.sourceUrl,
    sourceTitle: rewardCase.sourceTitle ?? '',
    sourceAuthor: rewardCase.sourceAuthor ?? rewardCase.agency,
    sourceKind: rewardCase.sourceKind ?? 'official',
    sourceRecordsJson: JSON.stringify(rewardCase.sourceRecords ?? [], null, 2),
  };
}

export function buildAdminCaseMutation(
  values: AdminCaseFormValues,
  { includeSourceRecords = true, manualCreate = false } = {}
): AdminCaseMutation {
  const rewardValue = values.reward.replace(/,/g, '').trim();
  const parsedReward = rewardValue ? Number(rewardValue) : null;
  if (parsedReward !== null && (!Number.isFinite(parsedReward) || parsedReward < 0)) {
    throw new Error('Reward amount must be a positive number or left blank.');
  }

  const regions = commaSeparated(values.regions);
  if (values.title.trim().length < 4) throw new Error('Display title must contain at least 4 characters.');
  if (values.summary.trim().length < 20) throw new Error('Summary must contain at least 20 characters.');
  if (!values.agency.trim()) throw new Error('Agency is required.');
  if (manualCreate && !regions.length) throw new Error('At least one state, province, or region is required.');
  if (!values.status.trim()) throw new Error('Status is required.');
  if (!values.publishedDate || !values.lastVerified) throw new Error('Published and verified dates are required.');
  if (!values.sourceAuthor.trim()) throw new Error('Source organization is required.');
  if (manualCreate && !values.sourceTitle.trim()) throw new Error('Source page title is required.');
  if (!/^https?:\/\//i.test(values.sourceUrl.trim())) throw new Error('Enter a valid public source URL.');
  if (manualCreate && !['Open', 'Information Requested', 'Closed'].includes(values.status.trim())) {
    throw new Error('New notices must use Open, Information Requested, or Closed status.');
  }

  let sourceRecords: OfficialSourceRecord[] = [];
  if (includeSourceRecords) {
    try {
      const parsed = JSON.parse(values.sourceRecordsJson || '[]');
      if (!Array.isArray(parsed)) throw new Error();
      sourceRecords = parsed as OfficialSourceRecord[];
    } catch {
      throw new Error('Source records must be a valid JSON array.');
    }
  }

  return {
    title: values.title.trim(),
    agency: values.agency.trim(),
    country: values.country,
    regions,
    caseType: optional(values.caseType),
    description: optional(values.description),
    reward: parsedReward,
    rewardCurrency: parsedReward === null ? null : values.rewardCurrency,
    rewardText: optional(values.rewardText),
    status: values.status.trim(),
    summary: values.summary.trim(),
    warningMessage: optional(values.warningMessage),
    aliases: commaSeparated(values.aliases),
    age: optional(values.age),
    dateOfBirth: optional(values.dateOfBirth),
    placeOfBirth: optional(values.placeOfBirth),
    sex: optional(values.sex),
    race: optional(values.race),
    nationality: optional(values.nationality),
    hair: optional(values.hair),
    eyes: optional(values.eyes),
    height: optional(values.height),
    weight: optional(values.weight),
    locations: optional(values.locations),
    distinguishingFeatures: optional(values.distinguishingFeatures),
    fieldOffice: optional(values.fieldOffice),
    publishedDate: values.publishedDate.trim(),
    lastVerified: values.lastVerified.trim(),
    sourceUpdatedDate: optional(values.sourceUpdatedDate),
    sourceUrl: values.sourceUrl.trim(),
    sourceTitle: optional(values.sourceTitle),
    sourceAuthor: optional(values.sourceAuthor),
    sourceKind: values.sourceKind,
    sourceRecords,
  };
}

export function AdminCaseFields({
  includeSourceRecords = true,
  manualCreate = false,
  onChange,
  values,
}: {
  includeSourceRecords?: boolean;
  manualCreate?: boolean;
  onChange: (values: AdminCaseFormValues) => void;
  values: AdminCaseFormValues;
}) {
  function setValue<Key extends keyof AdminCaseFormValues>(key: Key, value: AdminCaseFormValues[Key]) {
    onChange({ ...values, [key]: value });
  }

  return (
    <View style={styles.formStack}>
      <Section title="Public presentation">
        <Field label="Display title" required>
          <TextInput onChangeText={(value) => setValue('title', value)} style={styles.input} value={values.title} />
        </Field>
        <Field label="Summary" required>
          <TextInput multiline onChangeText={(value) => setValue('summary', value)} style={[styles.input, styles.largeArea]} textAlignVertical="top" value={values.summary} />
        </Field>
        <Field label="Short description / charges">
          <TextInput multiline onChangeText={(value) => setValue('description', value)} style={[styles.input, styles.mediumArea]} textAlignVertical="top" value={values.description} />
        </Field>
        <Field label="Safety warning">
          <TextInput multiline onChangeText={(value) => setValue('warningMessage', value)} style={[styles.input, styles.mediumArea]} textAlignVertical="top" value={values.warningMessage} />
        </Field>
      </Section>

      <Section title="Classification and reward">
        <View style={styles.columns}>
          <Field grow label="Agency" required>
            <TextInput onChangeText={(value) => setValue('agency', value)} style={styles.input} value={values.agency} />
          </Field>
          <Field grow label="Country" required>
            <Segment
              onChange={(value) => {
                setValue('country', value as RewardCountry);
                if (!values.reward) setValue('rewardCurrency', getDefaultRewardCurrency(value as RewardCountry));
              }}
              options={['US', 'Canada', 'China']}
              value={values.country}
            />
          </Field>
        </View>
        <View style={styles.columns}>
          <Field grow hint="Separate multiple values with commas." label="States / provinces / regions" required={manualCreate}>
            <TextInput onChangeText={(value) => setValue('regions', value)} style={styles.input} value={values.regions} />
          </Field>
          <Field grow label="Case type">
            <TextInput onChangeText={(value) => setValue('caseType', value)} style={styles.input} value={values.caseType} />
          </Field>
        </View>
        <View style={styles.columns}>
          <Field grow label="Status" required>
            <TextInput onChangeText={(value) => setValue('status', value)} style={styles.input} value={values.status} />
          </Field>
          <Field grow label="Field office">
            <TextInput onChangeText={(value) => setValue('fieldOffice', value)} style={styles.input} value={values.fieldOffice} />
          </Field>
        </View>
        <View style={styles.columns}>
          <Field grow label="Reward amount">
            <TextInput keyboardType="numeric" onChangeText={(value) => setValue('reward', value)} placeholder="Not published" placeholderTextColor="#98A2B3" style={styles.input} value={values.reward} />
          </Field>
          <Field grow label="Currency">
            <Segment onChange={(value) => setValue('rewardCurrency', value as RewardCurrency)} options={['USD', 'CAD', 'CNY']} value={values.rewardCurrency} />
          </Field>
        </View>
        <Field label="Official reward wording">
          <TextInput multiline onChangeText={(value) => setValue('rewardText', value)} style={[styles.input, styles.mediumArea]} textAlignVertical="top" value={values.rewardText} />
        </Field>
      </Section>

      <Section title="Identity and physical details">
        <Field hint="Separate multiple values with commas." label="Aliases">
          <TextInput onChangeText={(value) => setValue('aliases', value)} style={styles.input} value={values.aliases} />
        </Field>
        <View style={styles.columns}>
          <Field grow label="Age"><TextInput onChangeText={(value) => setValue('age', value)} style={styles.input} value={values.age} /></Field>
          <Field grow label="Date of birth"><TextInput onChangeText={(value) => setValue('dateOfBirth', value)} style={styles.input} value={values.dateOfBirth} /></Field>
          <Field grow label="Place of birth"><TextInput onChangeText={(value) => setValue('placeOfBirth', value)} style={styles.input} value={values.placeOfBirth} /></Field>
        </View>
        <View style={styles.columns}>
          <Field grow label="Sex"><TextInput onChangeText={(value) => setValue('sex', value)} style={styles.input} value={values.sex} /></Field>
          <Field grow label="Race / ethnicity"><TextInput onChangeText={(value) => setValue('race', value)} style={styles.input} value={values.race} /></Field>
          <Field grow label="Nationality"><TextInput onChangeText={(value) => setValue('nationality', value)} style={styles.input} value={values.nationality} /></Field>
        </View>
        <View style={styles.columns}>
          <Field grow label="Hair"><TextInput onChangeText={(value) => setValue('hair', value)} style={styles.input} value={values.hair} /></Field>
          <Field grow label="Eyes"><TextInput onChangeText={(value) => setValue('eyes', value)} style={styles.input} value={values.eyes} /></Field>
          <Field grow label="Height"><TextInput onChangeText={(value) => setValue('height', value)} style={styles.input} value={values.height} /></Field>
          <Field grow label="Weight"><TextInput onChangeText={(value) => setValue('weight', value)} style={styles.input} value={values.weight} /></Field>
        </View>
        <Field label="General locations">
          <TextInput onChangeText={(value) => setValue('locations', value)} placeholder="Broad public area only" placeholderTextColor="#98A2B3" style={styles.input} value={values.locations} />
        </Field>
        <Field label="Distinguishing features">
          <TextInput multiline onChangeText={(value) => setValue('distinguishingFeatures', value)} style={[styles.input, styles.mediumArea]} textAlignVertical="top" value={values.distinguishingFeatures} />
        </Field>
      </Section>

      <Section title="Source and verification">
        <View style={styles.columns}>
          <Field grow label="Published date" required><TextInput onChangeText={(value) => setValue('publishedDate', value)} placeholder="YYYY-MM-DD" placeholderTextColor="#98A2B3" style={styles.input} value={values.publishedDate} /></Field>
          <Field grow label="Last verified" required><TextInput onChangeText={(value) => setValue('lastVerified', value)} placeholder="YYYY-MM-DD" placeholderTextColor="#98A2B3" style={styles.input} value={values.lastVerified} /></Field>
          <Field grow label="Source updated"><TextInput onChangeText={(value) => setValue('sourceUpdatedDate', value)} placeholder="YYYY-MM-DD" placeholderTextColor="#98A2B3" style={styles.input} value={values.sourceUpdatedDate} /></Field>
        </View>
        <View style={styles.columns}>
          <Field grow label="Source organization" required><TextInput onChangeText={(value) => setValue('sourceAuthor', value)} style={styles.input} value={values.sourceAuthor} /></Field>
          <Field grow label="Source type"><Segment labels={['Official', 'Publisher']} onChange={(value) => setValue('sourceKind', value as 'official' | 'publisher')} options={['official', 'publisher']} value={values.sourceKind} /></Field>
        </View>
        <Field label="Source page title" required={manualCreate}><TextInput onChangeText={(value) => setValue('sourceTitle', value)} style={styles.input} value={values.sourceTitle} /></Field>
        <Field label="Public source URL" required><TextInput autoCapitalize="none" keyboardType="url" onChangeText={(value) => setValue('sourceUrl', value)} style={styles.input} value={values.sourceUrl} /></Field>
        {includeSourceRecords ? (
          <Field hint="Advanced: JSON array used by the public source list. Invalid JSON cannot be saved." label="Source records (JSON)">
            <TextInput autoCapitalize="none" multiline onChangeText={(value) => setValue('sourceRecordsJson', value)} style={[styles.input, styles.jsonArea]} textAlignVertical="top" value={values.sourceRecordsJson} />
          </Field>
        ) : null}
      </Section>
    </View>
  );
}

function Section({ children, title }: { children: React.ReactNode; title: string }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>;
}

function Field({ children, grow, hint, label, required }: { children: React.ReactNode; grow?: boolean; hint?: string; label: string; required?: boolean }) {
  return (
    <View style={[styles.field, grow && styles.fieldGrow]}>
      <Text style={styles.label}>{label}{required ? <Text style={styles.required}> *</Text> : null}</Text>
      {children}
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

function Segment({ labels, onChange, options, value }: { labels?: string[]; onChange: (value: string) => void; options: string[]; value: string }) {
  return (
    <View style={styles.segment}>
      {options.map((option, index) => (
        <Pressable key={option} onPress={() => onChange(option)} style={[styles.segmentButton, value === option && styles.segmentButtonActive]}>
          <Text style={[styles.segmentText, value === option && styles.segmentTextActive]}>{labels?.[index] ?? option}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  formStack: { gap: 14 },
  section: { backgroundColor: '#F8FAFC', borderColor: '#E4E7EC', borderRadius: 10, borderWidth: 1, gap: 13, padding: 15 },
  sectionTitle: { color: '#101828', fontSize: 13, fontWeight: '900' },
  columns: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  field: { gap: 7, minWidth: 0 },
  fieldGrow: { flex: 1, minWidth: 180 },
  label: { color: '#344054', fontSize: 12, fontWeight: '800' },
  required: { color: '#D92D20' },
  hint: { color: '#98A2B3', fontSize: 11, fontWeight: '600', lineHeight: 16 },
  input: { backgroundColor: '#FFFFFF', borderColor: '#D0D5DD', borderRadius: 8, borderWidth: 1, color: '#101828', fontSize: 14, minHeight: 44, paddingHorizontal: 12, paddingVertical: 10 },
  mediumArea: { minHeight: 82 },
  largeArea: { minHeight: 124 },
  jsonArea: { fontFamily: 'monospace', minHeight: 150 },
  segment: { alignSelf: 'flex-start', backgroundColor: '#EAECF0', borderRadius: 8, flexDirection: 'row', padding: 3 },
  segmentButton: { alignItems: 'center', borderRadius: 6, justifyContent: 'center', minHeight: 36, paddingHorizontal: 12 },
  segmentButtonActive: { backgroundColor: '#FFFFFF', boxShadow: '0 1px 3px rgba(16, 24, 40, 0.10)' },
  segmentText: { color: '#667085', fontSize: 12, fontWeight: '800' },
  segmentTextActive: { color: '#344054' },
});
