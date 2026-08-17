import { useEffect, useState } from 'react';
import { Link } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { fetchCasePage, type CaseSortMode } from '@/lib/cases';
import {
  formatCaseReward,
  getCaseRegionLabel,
  getCaseSourceName,
  getCountryAccentColor,
  getCountryBadge,
  isPublisherNotice,
} from '@/lib/case-display';
import { ReliableCaseImage } from '@/components/reliable-case-image';
import { LanguageSelector } from '@/components/language-selector';
import { getLocalizedCountry, getLocalizedStatus, useLanguage } from '@/lib/i18n';
import type { CaseFacets, RewardCase, RewardCountry } from '@/types/reward-case';

type CountryFilter = 'All' | RewardCountry;
type StatusFilter = 'All' | string;
type RegionFilter = 'All' | string;
type SourceFilter = 'All' | string;
type SortMode = CaseSortMode;
type RegionOption = { count: number; label: string };

const countryFilters: CountryFilter[] = ['All', 'US', 'Canada', 'China'];
const pageSize = 12;
const emptyFacets: CaseFacets = { regions: [], sources: [], statuses: [] };

function useDebouncedValue(value: string, delayMs: number) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedValue(value.trim()), delayMs);
    return () => clearTimeout(timeout);
  }, [delayMs, value]);

  return debouncedValue;
}

export default function CasesScreen() {
  const { t } = useLanguage();
  const [cases, setCases] = useState<RewardCase[]>([]);
  const [query, setQuery] = useState('');
  const [country, setCountry] = useState<CountryFilter>('All');
  const [status, setStatus] = useState<StatusFilter>('All');
  const [region, setRegion] = useState<RegionFilter>('All');
  const [source, setSource] = useState<SourceFilter>('All');
  const [isRegionMenuOpen, setIsRegionMenuOpen] = useState(false);
  const [isSourceMenuOpen, setIsSourceMenuOpen] = useState(false);
  const [sortMode, setSortMode] = useState<SortMode>('published_desc');
  const [facets, setFacets] = useState<CaseFacets>(emptyFacets);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { width } = useWindowDimensions();
  const isWide = width >= 900;

  const debouncedQuery = useDebouncedValue(query, 300);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);

    fetchCasePage(
      {
        country: country === 'All' ? undefined : country,
        page: 1,
        pageSize,
        q: debouncedQuery || undefined,
        region: region === 'All' ? undefined : region,
        sort: sortMode,
        source: source === 'All' ? undefined : source,
        status: status === 'All' ? undefined : status,
      },
      controller.signal
    )
      .then((response) => {
        setCases(response.items);
        setFacets(response.facets);
        setTotal(response.total);
        setPage(response.page);
        setError(null);
      })
      .catch((requestError: Error) => {
        if (requestError.name !== 'AbortError') setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [country, debouncedQuery, region, sortMode, source, status]);

  const statusOptions = ['All', ...facets.statuses.map((option) => option.value)];
  const sortOptions: { label: string; value: SortMode }[] = [
    { label: t('newest'), value: 'published_desc' },
    { label: t('rewardHighToLow'), value: 'reward_desc' },
    { label: t('rewardLowToHigh'), value: 'reward_asc' },
    { label: t('titleAZ'), value: 'title_asc' },
  ];
  const regionOptions: RegionOption[] = facets.regions.map((option) => ({
    count: option.count,
    label: option.value,
  }));
  const sourceOptions: RegionOption[] = facets.sources.map((option) => ({
    count: option.count,
    label: option.value,
  }));
  const hasMore = cases.length < total;

  async function loadMoreCases() {
    if (isLoadingMore || !hasMore) return;

    setIsLoadingMore(true);
    try {
      const response = await fetchCasePage({
        country: country === 'All' ? undefined : country,
        page: page + 1,
        pageSize,
        q: debouncedQuery || undefined,
        region: region === 'All' ? undefined : region,
        sort: sortMode,
        source: source === 'All' ? undefined : source,
        status: status === 'All' ? undefined : status,
      });
      setCases((current) => [...current, ...response.items]);
      setPage(response.page);
      setTotal(response.total);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t('unableToLoadMore'));
    } finally {
      setIsLoadingMore(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={[styles.header, isWide && styles.headerWide]}>
          <View style={styles.headerCopy}>
            <Link href="/" asChild>
              <Pressable accessibilityRole="link" style={styles.backLink}>
                <SymbolView
                  name={{ ios: 'arrow.left', android: 'arrow_back', web: 'arrow_back' }}
                  size={16}
                  tintColor="#6C63FF"
                />
                <Text style={styles.backLinkText}>{t('home')}</Text>
              </Pressable>
            </Link>
            <Text style={styles.title}>{t('allCases')}</Text>
            <Text style={styles.subtitle}>{t('casesSubtitle')}</Text>
          </View>
          <View style={styles.headerAside}>
            <LanguageSelector />
            <View style={styles.resultSummary}>
              <Text style={styles.resultNumber}>{total}</Text>
              <Text style={styles.resultLabel}>{total === 1 ? t('result') : t('results')}</Text>
            </View>
          </View>
        </View>

        <View style={styles.searchBox}>
          <SymbolView
            name={{ ios: 'magnifyingglass', android: 'search', web: 'search' }}
            size={24}
            tintColor="#667085"
          />
          <TextInput
            accessibilityLabel={t('searchAllCases')}
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setQuery}
            placeholder={t('searchAllPlaceholder')}
            placeholderTextColor="#8A94A6"
            style={styles.searchInput}
            value={query}
          />
          {query.length > 0 && (
            <Pressable accessibilityRole="button" onPress={() => setQuery('')} style={styles.clearButton}>
              <Text style={styles.clearButtonText}>{t('clear')}</Text>
            </Pressable>
          )}
        </View>

        <View style={styles.filterSurface}>
          <FilterBlock label={t('country')}>
            <View style={styles.segmentedControl}>
              {countryFilters.map((filter) => (
                <FilterButton
                  isActive={country === filter}
                  key={filter}
                  label={getLocalizedCountry(filter, t)}
                  onPress={() => {
                    setCountry(filter);
                    setRegion('All');
                    setSource('All');
                    setIsRegionMenuOpen(false);
                    setIsSourceMenuOpen(false);
                  }}
                />
              ))}
            </View>
          </FilterBlock>

          <FilterBlock label={t('status')}>
            <View style={styles.chipRowWrap}>
              {statusOptions.map((option) => (
                <Chip
                  isActive={status === option}
                  key={option}
                  label={option === 'All' ? t('all') : getLocalizedStatus(option, t)}
                  onPress={() => setStatus(option)}
                />
              ))}
            </View>
          </FilterBlock>

          {country !== 'All' ? (
            <RegionSelect
              country={country}
              isOpen={isRegionMenuOpen}
              onSelect={(nextRegion) => {
                setRegion(nextRegion);
                setIsRegionMenuOpen(false);
              }}
              onToggle={() => setIsRegionMenuOpen((current) => !current)}
              options={regionOptions}
              value={region}
            />
          ) : null}

          <RegionSelect
            country={country === 'All' ? 'US' : country}
            isOpen={isSourceMenuOpen}
            label={t('source')}
            onSelect={(nextSource) => {
              setSource(nextSource);
              setIsSourceMenuOpen(false);
            }}
            onToggle={() => setIsSourceMenuOpen((current) => !current)}
            options={sourceOptions}
            value={source}
          />

          <FilterBlock label={t('sort')}>
            <View style={styles.chipRowWrap}>
              {sortOptions.map((option) => (
                <Chip
                  isActive={sortMode === option.value}
                  key={option.value}
                  label={option.label}
                  onPress={() => setSortMode(option.value)}
                />
              ))}
            </View>
          </FilterBlock>
        </View>

        {error && (
          <View style={styles.notice}>
            <Text style={styles.noticeTitle}>{t('unableToLoadCases')}</Text>
            <Text style={styles.noticeText}>{t('apiLoadHint')}</Text>
          </View>
        )}

        {isLoading ? (
          <View style={styles.loadingArea}>
            <ActivityIndicator color="#6366F1" />
            <Text style={styles.loadingText}>{t('loadingAllCases')}</Text>
          </View>
        ) : cases.length === 0 ? (
          <EmptyState onReset={() => {
            setQuery('');
            setCountry('All');
            setStatus('All');
            setRegion('All');
            setSource('All');
            setIsRegionMenuOpen(false);
            setIsSourceMenuOpen(false);
            setSortMode('published_desc');
          }} />
        ) : (
          <>
            <View style={styles.listHeader}>
              <Text style={styles.listTitle}>{t('cases')}</Text>
              <Text style={styles.listMeta}>
                {t('showingResults', { visible: cases.length, total })}
              </Text>
            </View>

            <View style={[styles.caseGrid, isWide && styles.caseGridWide]}>
              {cases.map((rewardCase, index) => (
                <CaseListCard
                  isWide={isWide}
                  key={rewardCase.id}
                  rewardCase={rewardCase}
                  showRegion={country !== 'All'}
                  visualIndex={index}
                />
              ))}
            </View>

            {hasMore && (
              <Pressable
                accessibilityRole="button"
                disabled={isLoadingMore}
                onPress={loadMoreCases}
                style={styles.loadMoreButton}>
                {isLoadingMore ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.loadMoreText}>{t('loadMoreCases')}</Text>
                )}
              </Pressable>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function FilterBlock({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <View style={styles.filterBlock}>
      <Text style={styles.filterLabel}>{label}</Text>
      {children}
    </View>
  );
}

function FilterButton({
  isActive,
  label,
  onPress,
}: {
  isActive: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.segmentButton, isActive && styles.segmentButtonActive]}>
      <Text style={[styles.segmentButtonText, isActive && styles.segmentButtonTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

function RegionSelect({
  country,
  isOpen,
  label,
  onSelect,
  onToggle,
  options,
  value,
}: {
  country: RewardCountry;
  isOpen: boolean;
  label?: string;
  onSelect: (value: RegionFilter) => void;
  onToggle: () => void;
  options: RegionOption[];
  value: RegionFilter;
}) {
  const { t } = useLanguage();
  const categoryLabel = label ?? (country === 'US' ? t('state') : t('province'));
  const allLabel = label ? t('allSources') : country === 'US' ? t('allStates') : t('allProvinces');

  return (
    <FilterBlock label={categoryLabel}>
      <View style={styles.regionSelect}>
        <Pressable
          accessibilityLabel={t('chooseValue', { label: categoryLabel })}
          accessibilityRole="button"
          onPress={onToggle}
          style={[styles.regionSelectButton, isOpen && styles.regionSelectButtonOpen]}>
          <View style={styles.regionSelectCopy}>
            <Text style={styles.regionSelectHint}>{categoryLabel}</Text>
            <Text style={styles.regionSelectValue} numberOfLines={1}>
              {value === 'All' ? allLabel : value}
            </Text>
          </View>
          <SymbolView
            name={{ ios: isOpen ? 'chevron.up' : 'chevron.down', android: isOpen ? 'expand_less' : 'expand_more', web: isOpen ? 'expand_less' : 'expand_more' }}
            size={18}
            tintColor="#667085"
          />
        </Pressable>

        {isOpen ? (
          <View style={styles.regionMenu}>
            <ScrollView nestedScrollEnabled style={styles.regionMenuScroll}>
              <RegionOptionRow
                count={null}
                isActive={value === 'All'}
                label={allLabel}
                onPress={() => onSelect('All')}
              />
              {options.map((option) => (
                <RegionOptionRow
                  count={option.count}
                  isActive={value === option.label}
                  key={option.label}
                  label={option.label}
                  onPress={() => onSelect(option.label)}
                />
              ))}
            </ScrollView>
          </View>
        ) : null}
      </View>
    </FilterBlock>
  );
}

function RegionOptionRow({
  count,
  isActive,
  label,
  onPress,
}: {
  count: number | null;
  isActive: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.regionOption, isActive && styles.regionOptionActive]}>
      <Text style={[styles.regionOptionText, isActive && styles.regionOptionTextActive]}>
        {label}
      </Text>
      {count !== null ? <Text style={styles.regionOptionCount}>{count}</Text> : null}
      {isActive ? (
        <SymbolView
          name={{ ios: 'checkmark', android: 'check', web: 'check' }}
          size={16}
          tintColor="#5B4DFF"
        />
      ) : null}
    </Pressable>
  );
}

function Chip({
  isActive,
  label,
  onPress,
}: {
  isActive: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.chip, isActive && styles.chipActive]}>
      <Text style={[styles.chipText, isActive && styles.chipTextActive]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

function EmptyState({ onReset }: { onReset: () => void }) {
  const { t } = useLanguage();

  return (
    <View style={styles.emptyState}>
      <SymbolView
        name={{ ios: 'doc.text.magnifyingglass', android: 'description', web: 'description' }}
        size={36}
        tintColor="#667085"
      />
      <Text style={styles.emptyTitle}>{t('emptyCasesTitle')}</Text>
      <Text style={styles.emptyText}>{t('emptyCasesBody')}</Text>
      <Pressable accessibilityRole="button" onPress={onReset} style={styles.resetButton}>
        <Text style={styles.resetButtonText}>{t('resetFilters')}</Text>
      </Pressable>
    </View>
  );
}

function CaseListCard({
  isWide,
  rewardCase,
  showRegion,
  visualIndex,
}: {
  isWide: boolean;
  rewardCase: RewardCase;
  showRegion: boolean;
  visualIndex: number;
}) {
  const { formatDate, t } = useLanguage();
  const statusStyle =
    rewardCase.status === 'Open'
      ? styles.statusOpen
      : rewardCase.status === 'Closed'
        ? styles.statusClosed
        : styles.statusInfo;
  const statusTextStyle =
    rewardCase.status === 'Open'
      ? styles.statusTextOpen
      : rewardCase.status === 'Closed'
        ? styles.statusTextClosed
        : styles.statusTextInfo;

  return (
    <Link href={{ pathname: '/cases/detail', params: { id: rewardCase.id } }} asChild>
    <Pressable
      accessibilityRole="link"
      style={StyleSheet.flatten([styles.caseCard, isWide && styles.caseCardWide])}>
      <View style={styles.cardTopRow}>
        <CaseVisual rewardCase={rewardCase} visualIndex={visualIndex} />
        <View style={styles.caseCardMain}>
          <View style={styles.metaRow}>
            <View style={styles.countryBadge}>
              <Text style={styles.countryBadgeText}>{getCountryBadge(rewardCase.country)}</Text>
            </View>
            <View style={styles.sourceStack}>
              <Text style={styles.sourceEyebrow}>
                {t(isPublisherNotice(rewardCase) ? 'publisherSource' : 'officialSource')}
              </Text>
              <Text style={styles.sourceName} numberOfLines={1}>
                {getCaseSourceName(rewardCase)}
              </Text>
              {showRegion && getCaseRegionLabel(rewardCase) ? (
                <Text style={styles.regionMeta} numberOfLines={1}>
                  {getCaseRegionLabel(rewardCase)}
                </Text>
              ) : null}
            </View>
          </View>
          <Text style={styles.caseTitle} numberOfLines={2}>
            {rewardCase.title}
          </Text>
          <Text style={styles.summary} numberOfLines={3}>
            {rewardCase.summary}
          </Text>
        </View>
        <View style={[styles.statusPill, statusStyle]}>
          <Text style={[styles.statusText, statusTextStyle]} numberOfLines={1}>
            {getLocalizedStatus(rewardCase.status, t)}
          </Text>
        </View>
      </View>

      <View style={styles.cardFooter}>
        <InfoItem
          label={t('reward')}
          value={rewardCase.reward === null ? t('notPublished') : formatCaseReward(rewardCase)}
          valueStyle={styles.rewardValue}
        />
        <InfoItem label={t('published')} value={formatDate(rewardCase.publishedDate)} />
        <InfoItem label={t('dataChecked')} value={formatDate(rewardCase.lastVerified)} />
      </View>
    </Pressable>
    </Link>
  );
}

function CaseVisual({ rewardCase, visualIndex }: { rewardCase: RewardCase; visualIndex: number }) {
  const backgroundColor = visualIndex % 2 === 0 ? '#DDEBFF' : '#E9F8F5';
  const iconColor = getCountryAccentColor(rewardCase.country);

  return (
    <View style={[styles.caseVisual, { backgroundColor }]}>
      <ReliableCaseImage
        contentFit="cover"
        fallback={
          <SymbolView
            name={{ ios: 'doc.text.magnifyingglass', android: 'description', web: 'description' }}
            size={30}
            tintColor={iconColor}
          />
        }
        loadDelayMs={visualIndex * 450}
        rewardCase={rewardCase}
        style={styles.caseVisualImage}
      />
    </View>
  );
}

function InfoItem({
  label,
  value,
  valueStyle,
}: {
  label: string;
  value: string;
  valueStyle?: object;
}) {
  return (
    <View style={styles.infoItem}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, valueStyle]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F6F8FC',
  },
  content: {
    alignSelf: 'center',
    gap: 18,
    maxWidth: 1180,
    paddingBottom: 52,
    paddingHorizontal: 22,
    paddingTop: 28,
    width: '100%',
  },
  header: {
    gap: 18,
    position: 'relative',
    zIndex: 100,
  },
  headerWide: {
    alignItems: 'flex-end',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  headerAside: {
    alignItems: 'flex-end',
    gap: 10,
  },
  headerCopy: {
    flex: 1,
    gap: 8,
    minWidth: 0,
  },
  backLink: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    flexDirection: 'row',
    gap: 7,
    paddingVertical: 4,
  },
  backLinkText: {
    color: '#6C63FF',
    fontSize: 14,
    fontWeight: '800',
  },
  title: {
    color: '#111827',
    fontSize: 34,
    fontWeight: '900',
    lineHeight: 40,
  },
  subtitle: {
    color: '#667085',
    fontSize: 15,
    fontWeight: '600',
    lineHeight: 22,
    maxWidth: 680,
  },
  resultSummary: {
    alignItems: 'flex-start',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 14,
    borderWidth: 1,
    minWidth: 130,
    paddingHorizontal: 18,
    paddingVertical: 14,
  },
  resultNumber: {
    color: '#111827',
    fontSize: 28,
    fontWeight: '900',
    lineHeight: 32,
  },
  resultLabel: {
    color: '#667085',
    fontSize: 13,
    fontWeight: '800',
  },
  searchBox: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    minHeight: 58,
    paddingHorizontal: 16,
    boxShadow: '0 12px 24px rgba(70, 91, 132, 0.06)',
  },
  searchInput: {
    color: '#111827',
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    minWidth: 0,
    paddingVertical: 14,
  },
  clearButton: {
    backgroundColor: '#F2F4F7',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  clearButtonText: {
    color: '#475467',
    fontSize: 13,
    fontWeight: '800',
  },
  filterSurface: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 16,
    borderWidth: 1,
    gap: 16,
    padding: 16,
  },
  filterBlock: {
    gap: 8,
  },
  filterLabel: {
    color: '#667085',
    fontSize: 12,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  segmentedControl: {
    backgroundColor: '#F1F4F9',
    borderRadius: 12,
    flexDirection: 'row',
    padding: 4,
  },
  segmentButton: {
    alignItems: 'center',
    borderRadius: 9,
    flex: 1,
    justifyContent: 'center',
    minHeight: 38,
    paddingHorizontal: 12,
  },
  segmentButtonActive: {
    backgroundColor: '#6C63FF',
  },
  segmentButtonText: {
    color: '#475467',
    fontSize: 14,
    fontWeight: '800',
  },
  segmentButtonTextActive: {
    color: '#FFFFFF',
  },
  chipRowWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    backgroundColor: '#F7F9FC',
    borderColor: '#E2E8F0',
    borderRadius: 999,
    borderWidth: 1,
    maxWidth: 280,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  chipActive: {
    backgroundColor: '#F0EFFF',
    borderColor: '#C7D2FE',
  },
  chipText: {
    color: '#475467',
    fontSize: 13,
    fontWeight: '800',
  },
  chipTextActive: {
    color: '#5B4DFF',
  },
  regionSelect: {
    gap: 8,
  },
  regionSelectButton: {
    alignItems: 'center',
    backgroundColor: '#F8FAFD',
    borderColor: '#DDE4F0',
    borderRadius: 11,
    borderWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 52,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  regionSelectButtonOpen: {
    borderColor: '#AFA9FF',
  },
  regionSelectCopy: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  regionSelectHint: {
    color: '#98A2B3',
    fontSize: 10,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  regionSelectValue: {
    color: '#344054',
    fontSize: 14,
    fontWeight: '900',
  },
  regionMenu: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 12,
    borderWidth: 1,
    overflow: 'hidden',
  },
  regionMenuScroll: {
    maxHeight: 260,
  },
  regionOption: {
    alignItems: 'center',
    borderBottomColor: '#EEF2F7',
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 10,
    minHeight: 44,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  regionOptionActive: {
    backgroundColor: '#F4F3FF',
  },
  regionOptionText: {
    color: '#475467',
    flex: 1,
    fontSize: 13,
    fontWeight: '800',
  },
  regionOptionTextActive: {
    color: '#5B4DFF',
  },
  regionOptionCount: {
    color: '#98A2B3',
    fontSize: 12,
    fontWeight: '800',
  },
  notice: {
    backgroundColor: '#FFF7ED',
    borderColor: '#FDBA74',
    borderRadius: 12,
    borderWidth: 1,
    gap: 4,
    padding: 14,
  },
  noticeTitle: {
    color: '#9A3412',
    fontSize: 14,
    fontWeight: '800',
  },
  noticeText: {
    color: '#9A3412',
    fontSize: 13,
    lineHeight: 18,
  },
  loadingArea: {
    alignItems: 'center',
    gap: 10,
    paddingVertical: 44,
  },
  loadingText: {
    color: '#667085',
    fontSize: 14,
    fontWeight: '700',
  },
  emptyState: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 16,
    borderWidth: 1,
    gap: 10,
    paddingHorizontal: 22,
    paddingVertical: 38,
  },
  emptyTitle: {
    color: '#111827',
    fontSize: 20,
    fontWeight: '900',
    textAlign: 'center',
  },
  emptyText: {
    color: '#667085',
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
    maxWidth: 420,
    textAlign: 'center',
  },
  resetButton: {
    backgroundColor: '#6C63FF',
    borderRadius: 11,
    marginTop: 4,
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  resetButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
  },
  listHeader: {
    alignItems: 'baseline',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between',
  },
  listTitle: {
    color: '#111827',
    fontSize: 24,
    fontWeight: '900',
  },
  listMeta: {
    color: '#667085',
    fontSize: 13,
    fontWeight: '800',
  },
  caseGrid: {
    gap: 12,
  },
  caseGridWide: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  caseCard: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 16,
    borderWidth: 1,
    gap: 14,
    padding: 16,
    width: '100%',
    boxShadow: '0 14px 28px rgba(70, 91, 132, 0.07)',
  },
  caseCardWide: {
    width: '49.2%',
  },
  cardTopRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 14,
  },
  caseVisual: {
    alignItems: 'center',
    borderColor: '#DDE4F0',
    borderRadius: 13,
    borderWidth: 1,
    flexShrink: 0,
    height: 76,
    justifyContent: 'center',
    width: 76,
  },
  caseVisualImage: {
    borderRadius: 12,
    height: '100%',
    width: '100%',
  },
  caseCardMain: {
    flex: 1,
    gap: 8,
    minWidth: 0,
  },
  metaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    minWidth: 0,
  },
  countryBadge: {
    backgroundColor: '#EFF2FF',
    borderColor: '#D9DFFD',
    borderRadius: 7,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  countryBadgeText: {
    color: '#1E293B',
    fontSize: 11,
    fontWeight: '900',
  },
  sourceStack: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  sourceEyebrow: {
    color: '#6C63FF',
    fontSize: 9,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  sourceName: {
    color: '#667085',
    fontSize: 12,
    fontWeight: '900',
  },
  regionMeta: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '700',
  },
  caseTitle: {
    color: '#111827',
    fontSize: 18,
    fontWeight: '900',
    lineHeight: 23,
  },
  summary: {
    color: '#536179',
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 19,
  },
  statusPill: {
    borderRadius: 999,
    flexShrink: 1,
    maxWidth: 164,
    paddingHorizontal: 11,
    paddingVertical: 7,
  },
  statusOpen: {
    backgroundColor: '#DDF7EA',
  },
  statusInfo: {
    backgroundColor: '#E6F0FF',
  },
  statusClosed: {
    backgroundColor: '#EEF0F3',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '900',
  },
  statusTextOpen: {
    color: '#078349',
  },
  statusTextInfo: {
    color: '#1B5CC7',
  },
  statusTextClosed: {
    color: '#667085',
  },
  cardFooter: {
    borderColor: '#EEF2F7',
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingTop: 13,
  },
  infoItem: {
    flex: 1,
    gap: 3,
    minWidth: 0,
  },
  infoLabel: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  infoValue: {
    color: '#344054',
    fontSize: 13,
    fontWeight: '800',
  },
  rewardValue: {
    color: '#B45309',
    fontSize: 15,
    fontWeight: '900',
  },
  loadMoreButton: {
    alignItems: 'center',
    alignSelf: 'center',
    backgroundColor: '#6C63FF',
    borderRadius: 12,
    justifyContent: 'center',
    paddingHorizontal: 18,
    paddingVertical: 12,
  },
  loadMoreText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
  },
});
