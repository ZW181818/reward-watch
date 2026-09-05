import { useEffect, useState } from 'react';
import { Link } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
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

import { fetchCase, fetchCasePage, fetchHomeSettings } from '@/lib/cases';
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
import { ThemeToggle } from '@/components/theme-toggle';
import { getLocalizedCountry, getLocalizedStatus, useLanguage } from '@/lib/i18n';
import { createThemedStyles, themedForeground } from '@/lib/themed-styles';
import type { RewardCase, RewardCountry } from '@/types/reward-case';

type CountryFilter = 'All' | RewardCountry;

const defaultHomeSettings = {
  brandSubtitle: 'Official and reviewed public reward notices from supported jurisdictions',
  safetyMessage: "Do not approach or attempt to detain any person. Submit information through the listed publisher's source page.",
  featuredCaseIds: [] as string[],
  recentCaseLimit: 4,
};

const countryFilters: CountryFilter[] = ['All', 'US', 'Canada', 'China'];

function useDebouncedValue(value: string, delayMs: number) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedValue(value.trim()), delayMs);
    return () => clearTimeout(timeout);
  }, [delayMs, value]);

  return debouncedValue;
}

export default function HomeScreen() {
  const { language, t } = useLanguage();
  const [recentCases, setRecentCases] = useState<RewardCase[]>([]);
  const [highestRewardCases, setHighestRewardCases] = useState<RewardCase[]>([]);
  const [visibleTotal, setVisibleTotal] = useState(0);
  const [featuredCases, setFeaturedCases] = useState<RewardCase[]>([]);
  const [homeSettings, setHomeSettings] = useState(defaultHomeSettings);
  const [query, setQuery] = useState('');
  const [country, setCountry] = useState<CountryFilter>('All');
  const [isCountryMenuOpen, setIsCountryMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { width } = useWindowDimensions();
  const isWide = width >= 820;
  const debouncedQuery = useDebouncedValue(query, 300);

  useEffect(() => {
    fetchHomeSettings()
      .then(async (settings) => {
        setHomeSettings(settings);
        const results = await Promise.allSettled(settings.featuredCaseIds.map((id) => fetchCase(id)));
        setFeaturedCases(results.flatMap((result) => result.status === 'fulfilled' ? [result.value] : []));
      })
      .catch(() => setHomeSettings(defaultHomeSettings));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const commonQuery = {
      country: country === 'All' ? undefined : country,
      q: debouncedQuery || undefined,
    };
    setIsLoading(true);

    Promise.all([
      fetchCasePage({ ...commonQuery, pageSize: homeSettings.recentCaseLimit, sort: 'published_desc' }, controller.signal),
      fetchCasePage({ ...commonQuery, pageSize: 3, sort: 'reward_desc' }, controller.signal),
    ])
      .then(([recentResponse, rewardResponse]) => {
        setRecentCases(recentResponse.items);
        setHighestRewardCases(rewardResponse.items.filter((rewardCase) => rewardCase.reward !== null));
        setVisibleTotal(recentResponse.total);
        setError(null);
      })
      .catch((requestError: Error) => {
        if (requestError.name !== 'AbortError') setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [country, debouncedQuery, homeSettings.recentCaseLimit]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={[styles.header, isWide && styles.headerWide]}>
          <View style={styles.brandRow}>
            <BrandIcon />
            <View style={styles.brandCopy}>
              <Text style={styles.title}>Reward Watch</Text>
              <Text style={styles.subtitle}>
                {language === 'en' ? homeSettings.brandSubtitle : t('homeSubtitle')}
              </Text>
            </View>
          </View>

          <View style={styles.headerActions}>
            <View style={styles.headerControlRow}>
              <LanguageSelector />
              <ThemeToggle />
              <View style={styles.marketFilterWrap}>
              <Pressable
                accessibilityLabel={t('chooseCountry')}
                accessibilityRole="button"
                onPress={() => setIsCountryMenuOpen((current) => !current)}
                style={[styles.marketBadge, isCountryMenuOpen && styles.marketBadgeActive]}>
                <SymbolView
                  name={{ ios: 'globe.americas.fill', android: 'globe', web: 'globe' }}
                  size={20}
                  tintColor={themedForeground('#5B5FF7')}
                />
                <Text style={styles.marketBadgeText}>{getLocalizedCountry(country, t)}</Text>
                <SymbolView
                  name={{ ios: 'chevron.down', android: 'keyboard_arrow_down', web: 'keyboard_arrow_down' }}
                  size={15}
                  tintColor={themedForeground('#7B8497')}
                />
              </Pressable>

              {isCountryMenuOpen && (
                <View style={styles.marketMenu}>
                  {countryFilters.map((filter) => {
                    const isSelected = country === filter;

                    return (
                      <Pressable
                        accessibilityLabel={`${t('chooseCountry')}: ${getLocalizedCountry(filter, t)}`}
                        accessibilityRole="button"
                        key={filter}
                        onPress={() => {
                          setCountry(filter);
                          setIsCountryMenuOpen(false);
                        }}
                        style={[styles.marketMenuItem, isSelected && styles.marketMenuItemActive]}>
                        <Text
                          style={[
                            styles.marketMenuItemText,
                            isSelected && styles.marketMenuItemTextActive,
                          ]}>
                          {getLocalizedCountry(filter, t)}
                        </Text>
                        {isSelected && (
                          <SymbolView
                            name={{ ios: 'checkmark', android: 'check', web: 'check' }}
                            size={16}
                            tintColor={themedForeground('#5B4DFF')}
                          />
                        )}
                      </Pressable>
                    );
                  })}
                </View>
              )}
              </View>
            </View>

            <Link href="/favorites" asChild>
              <Pressable accessibilityRole="link" style={styles.savedButton}>
                <SymbolView
                  name={{ ios: 'bookmark', android: 'bookmark', web: 'bookmark' }}
                  size={16}
                  tintColor={themedForeground('#5B4DFF')}
                />
                <Text style={styles.savedButtonText}>{t('saved')}</Text>
              </Pressable>
            </Link>
          </View>
        </View>

        <View style={styles.searchPanel}>
          <View style={[styles.searchBox, !isWide && styles.searchBoxMobile]}>
            <SymbolView
              fallback={<Text style={styles.searchIconFallback}>{t('searchCases')}</Text>}
              name={{ ios: 'magnifyingglass', android: 'search', web: 'search' }}
              size={isWide ? 39 : 30}
              tintColor={themedForeground('#6868FF')}
            />
            <TextInput
              accessibilityLabel={t('searchCases')}
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={setQuery}
              placeholder={isWide ? t('searchPlaceholder') : t('searchCases')}
              placeholderTextColor={themedForeground('#66738A')}
              style={[styles.searchInput, !isWide && styles.searchInputMobile]}
              value={query}
            />
            {isWide && (
              <View style={styles.keyboardHint}>
                <Text style={styles.keyboardHintText}>Cmd</Text>
                <Text style={styles.keyboardHintText}>K</Text>
              </View>
            )}
            {query.length > 0 && (
              <Pressable
                accessibilityRole="button"
                onPress={() => setQuery('')}
                style={styles.clearButton}>
                <Text style={styles.clearButtonText}>{t('clear')}</Text>
              </Pressable>
            )}
          </View>

        </View>

        <View style={[styles.metricRow, !isWide && styles.metricRowMobile]}>
          <Metric
            compact={!isWide}
            iconName={{ ios: 'folder.fill', android: 'folder', web: 'folder' }}
            label={t('visibleCases')}
            tone="violet"
            value={visibleTotal.toString()}
          />
          <Metric
            compact={!isWide}
            iconName={{ ios: 'dollarsign.circle.fill', android: 'attach_money', web: 'attach_money' }}
            label={t('highestReward')}
            tone="green"
            value={
              highestRewardCases[0]
                ? formatCaseReward(highestRewardCases[0])
                : t('notPublished')
            }
          />
          <Metric
            compact={!isWide}
            iconName={{ ios: 'globe.americas.fill', android: 'globe', web: 'globe' }}
            label={t('marketsCovered')}
            tone="blue"
            value={String(countryFilters.length - 1)}
          />
        </View>

        {error && (
          <View style={styles.notice}>
            <Text style={styles.noticeTitle}>{t('apiConnectionUnavailable')}</Text>
            <Text style={styles.noticeText}>{t('apiLoadHint')}</Text>
          </View>
        )}

        {isLoading ? (
          <View style={styles.loadingArea}>
            <ActivityIndicator color={themedForeground('#6366F1')} />
            <Text style={styles.loadingText}>{t('loadingCases')}</Text>
          </View>
        ) : (
          <>
            {featuredCases.length > 0 && country === 'All' && !debouncedQuery ? (
              <>
                <SectionTitle subtitle={t('selectedByEditors')} title={t('featuredCases')} />
                <View style={[styles.cardGrid, isWide && styles.cardGridWide]}>
                  {featuredCases.map((rewardCase, index) => (
                    <CaseCard isWide={isWide} key={rewardCase.id} rewardCase={rewardCase} showRegion={false} visualIndex={index} />
                  ))}
                </View>
              </>
            ) : null}
            <SectionTitle title={t('recentCases')} />
            {recentCases.length === 0 ? (
              <HomeEmptyState
                onReset={() => {
                  setQuery('');
                  setCountry('All');
                }}
              />
            ) : (
              <View style={[styles.cardGrid, isWide && styles.cardGridWide]}>
                {recentCases.map((rewardCase, index) => (
                  <CaseCard
                    isWide={isWide}
                    key={rewardCase.id}
                    rewardCase={rewardCase}
                    showRegion={country !== 'All'}
                    visualIndex={index}
                  />
                ))}
              </View>
            )}

            <Link href="/cases" asChild>
              <Pressable accessibilityRole="link" style={styles.viewAllButton}>
                <Text style={styles.viewAllButtonText}>{t('viewAllCases')}</Text>
                <SymbolView
                  name={{ ios: 'arrow.right', android: 'arrow_forward', web: 'arrow_forward' }}
                  size={17}
                  tintColor={themedForeground('#6C63FF')}
                />
              </Pressable>
            </Link>

            <SafetyBanner
              isWide={isWide}
              message={language === 'en' ? homeSettings.safetyMessage : t('safetyMessage')}
            />

            {highestRewardCases.length > 0 && (
              <>
                <SectionTitle subtitle={t('rankedByReward')} title={t('highestRewards')} />
                <View style={[styles.cardGrid, isWide && styles.cardGridWide]}>
                  {highestRewardCases.map((rewardCase, index) => (
                    <CaseCard
                      isWide={isWide}
                      key={rewardCase.id}
                      rewardCase={rewardCase}
                      showRegion={country !== 'All'}
                      visualIndex={recentCases.length + index}
                    />
                  ))}
                </View>
              </>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function BrandIcon() {
  return (
    <View style={styles.brandIcon}>
      <SymbolView
        name={{ ios: 'checkmark.shield.fill', android: 'verified_user', web: 'verified_user' }}
        size={32}
        tintColor={themedForeground('#FFFFFF')}
      />
    </View>
  );
}

function Metric({
  compact,
  iconName,
  label,
  tone,
  value,
}: {
  compact: boolean;
  iconName: SymbolViewProps['name'];
  label: string;
  tone: 'blue' | 'green' | 'violet';
  value: string;
}) {
  const iconStyle =
    tone === 'green' ? styles.metricIconGreen : tone === 'blue' ? styles.metricIconBlue : styles.metricIconViolet;
  const iconTint = tone === 'green' ? '#159A5B' : tone === 'blue' ? '#3C72F5' : '#7663F2';

  return (
    <View style={[styles.metric, compact && styles.metricCompact]}>
      <View style={[styles.metricIcon, compact && styles.metricIconCompact, iconStyle]}>
        <SymbolView name={iconName} size={compact ? 19 : 24} tintColor={themedForeground(iconTint)} />
      </View>
      <View style={styles.metricCopy}>
        <Text style={[styles.metricValue, compact && styles.metricValueCompact]} numberOfLines={1}>
          {value}
        </Text>
        <Text style={[styles.metricLabel, compact && styles.metricLabelCompact]} numberOfLines={2}>
          {label}
        </Text>
      </View>
    </View>
  );
}

function SectionTitle({ subtitle, title }: { subtitle?: string; title: string }) {
  return (
    <View style={styles.sectionHeader}>
      <SymbolView
        name={{ ios: 'sparkles', android: 'auto_awesome', web: 'auto_awesome' }}
        size={24}
        tintColor={themedForeground('#9B8CFF')}
      />
      <View style={styles.sectionCopy}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle && <Text style={styles.sectionSubtitle}>{subtitle}</Text>}
      </View>
    </View>
  );
}

function CaseCard({
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
      style={StyleSheet.flatten([
        styles.caseCard,
        !isWide && styles.caseCardMobile,
        isWide && styles.caseCardWide,
      ])}>
      <CaseVisual compact={!isWide} rewardCase={rewardCase} visualIndex={visualIndex} />

      <View style={styles.caseBody}>
        <View style={styles.caseHeaderRow}>
          <View style={styles.caseIdentity}>
            <View
              style={[
                styles.countryMark,
                rewardCase.country === 'Canada'
                  ? styles.countryMarkCanada
                  : rewardCase.country === 'China'
                    ? styles.countryMarkChina
                    : styles.countryMarkUs,
              ]}>
              <Text style={styles.countryMarkText}>
                {getCountryBadge(rewardCase.country)}
              </Text>
            </View>
            <View style={styles.caseMetaStack}>
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
              <Text style={styles.publishedDate} numberOfLines={1}>
                {formatDate(rewardCase.publishedDate)}
              </Text>
            </View>
          </View>
          <View style={[styles.statusPill, !isWide && styles.statusPillCompact, statusStyle]}>
            <Text style={[styles.statusText, statusTextStyle]} numberOfLines={1}>
              {getLocalizedStatus(rewardCase.status, t)}
            </Text>
          </View>
        </View>

        <Text style={styles.caseTitle} numberOfLines={2}>
          {rewardCase.title}
        </Text>
        <Text style={styles.caseSummary} numberOfLines={2}>
          {rewardCase.summary}
        </Text>
        <View style={styles.caseFooter}>
          <Text style={styles.reward}>
            {rewardCase.reward === null ? t('notPublished') : formatCaseReward(rewardCase)}
          </Text>
          <Text style={styles.rewardLabel}>{t('publicReward')}</Text>
        </View>
      </View>
    </Pressable>
    </Link>
  );
}

function CaseVisual({
  compact,
  rewardCase,
  visualIndex,
}: {
  compact: boolean;
  rewardCase: RewardCase;
  visualIndex: number;
}) {
  return (
    <View
      style={[
        styles.caseVisual,
        compact && styles.caseVisualCompact,
      ]}>
      <ReliableCaseImage
        contentFit="cover"
        fallback={
          <SymbolView
            name={{ ios: 'doc.text.magnifyingglass', android: 'description', web: 'description' }}
            size={compact ? 32 : 40}
            tintColor={themedForeground(getCountryAccentColor(rewardCase.country))}
          />
        }
        loadDelayMs={visualIndex * 450}
        rewardCase={rewardCase}
        style={styles.caseVisualImage}
      />
      <View style={styles.caseVisualBadge}>
        <Text style={styles.caseVisualBadgeText}>
          {getCountryBadge(rewardCase.country)}
        </Text>
      </View>
    </View>
  );
}

function SafetyBanner({ isWide, message }: { isWide: boolean; message: string }) {
  const { t } = useLanguage();

  return (
    <View style={styles.safetyBanner}>
      <View style={styles.safetyIcon}>
        <SymbolView
          name={{ ios: 'checkmark.shield.fill', android: 'verified_user', web: 'verified_user' }}
          size={23}
          tintColor={themedForeground('#FFFFFF')}
        />
      </View>
      <Text style={styles.safetyText}>{message}</Text>
      {isWide && (
        <View style={styles.learnMorePill}>
          <Text style={styles.learnMoreText}>{t('learnMore')}</Text>
          <SymbolView
            name={{ ios: 'arrow.right', android: 'arrow_forward', web: 'arrow_forward' }}
            size={14}
            tintColor={themedForeground('#6C63FF')}
          />
        </View>
      )}
    </View>
  );
}

function HomeEmptyState({ onReset }: { onReset: () => void }) {
  const { t } = useLanguage();

  return (
    <View style={styles.emptyState}>
      <SymbolView
        name={{ ios: 'doc.text.magnifyingglass', android: 'description', web: 'description' }}
        size={34}
        tintColor={themedForeground('#667085')}
      />
      <Text style={styles.emptyTitle}>{t('emptyHomeTitle')}</Text>
      <Text style={styles.emptyText}>{t('emptyHomeBody')}</Text>
      <Pressable accessibilityRole="button" onPress={onReset} style={styles.emptyButton}>
        <Text style={styles.emptyButtonText}>{t('reset')}</Text>
      </Pressable>
    </View>
  );
}

const styles = createThemedStyles({
  safeArea: {
    flex: 1,
    backgroundColor: '#F5F9FF',
    experimental_backgroundImage:
      'linear-gradient(140deg, #F8FBFF 0%, #F1F7FF 45%, #F8F7FF 100%)',
  },
  content: {
    alignSelf: 'center',
    gap: 24,
    maxWidth: 1180,
    paddingBottom: 52,
    paddingHorizontal: 26,
    paddingTop: 38,
    width: '100%',
  },
  header: {
    gap: 18,
    paddingBottom: 2,
    position: 'relative',
    zIndex: 100,
  },
  headerWide: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  headerActions: {
    alignItems: 'flex-end',
    gap: 10,
  },
  headerControlRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 8,
  },
  brandRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 20,
    minWidth: 0,
  },
  brandCopy: {
    flex: 1,
    gap: 8,
    minWidth: 0,
  },
  brandIcon: {
    alignItems: 'center',
    backgroundColor: '#6C74FF',
    borderRadius: 14,
    height: 46,
    justifyContent: 'center',
    width: 46,
    boxShadow: '0 14px 28px rgba(99, 102, 241, 0.25)',
  },
  title: {
    color: '#111827',
    fontSize: 36,
    fontWeight: '900',
    lineHeight: 42,
  },
  subtitle: {
    color: '#536179',
    fontSize: 17,
    fontWeight: '600',
    lineHeight: 24,
  },
  marketFilterWrap: {
    alignItems: 'flex-end',
    alignSelf: 'flex-start',
    position: 'relative',
    zIndex: 10,
  },
  marketBadge: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255, 255, 255, 0.72)',
    borderColor: '#DDE4F2',
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 11,
    boxShadow: '0 10px 24px rgba(81, 99, 143, 0.10)',
  },
  marketBadgeActive: {
    borderColor: '#C7D2FE',
  },
  marketBadgeText: {
    color: '#5B4DFF',
    fontSize: 15,
    fontWeight: '800',
  },
  marketMenu: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F2',
    borderRadius: 14,
    borderWidth: 1,
    gap: 4,
    minWidth: 190,
    padding: 6,
    position: 'absolute',
    right: 0,
    top: 50,
    zIndex: 20,
    boxShadow: '0 18px 36px rgba(50, 65, 100, 0.15)',
  },
  marketMenuItem: {
    alignItems: 'center',
    borderRadius: 10,
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 11,
  },
  marketMenuItemActive: {
    backgroundColor: '#F3F4FF',
  },
  marketMenuItemText: {
    color: '#475467',
    fontSize: 14,
    fontWeight: '800',
  },
  marketMenuItemTextActive: {
    color: '#5B4DFF',
  },
  savedButton: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255, 255, 255, 0.68)',
    borderColor: '#DDE4F2',
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 7,
    paddingHorizontal: 13,
    paddingVertical: 10,
  },
  savedButtonText: {
    color: '#5B4DFF',
    fontSize: 14,
    fontWeight: '900',
  },
  searchPanel: {
    gap: 22,
  },
  searchBox: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#D7E9FF',
    borderRadius: 22,
    borderWidth: 2,
    flexDirection: 'row',
    gap: 18,
    minHeight: 86,
    paddingHorizontal: 26,
    boxShadow: '0 22px 50px rgba(91, 111, 255, 0.13)',
  },
  searchBoxMobile: {
    borderRadius: 18,
    gap: 10,
    minHeight: 82,
    paddingHorizontal: 18,
  },
  searchIconFallback: {
    color: '#6366F1',
    fontSize: 12,
    fontWeight: '800',
  },
  searchInput: {
    color: '#111827',
    flex: 1,
    fontSize: 27,
    fontWeight: '700',
    minWidth: 0,
    paddingVertical: 18,
  },
  searchInputMobile: {
    fontSize: 15,
    lineHeight: 21,
  },
  keyboardHint: {
    alignItems: 'center',
    backgroundColor: '#F2F5FB',
    borderColor: '#E3E8F3',
    borderRadius: 9,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  keyboardHintText: {
    color: '#7C879A',
    fontSize: 14,
    fontWeight: '800',
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
  metricRow: {
    flexDirection: 'row',
    gap: 14,
    width: '100%',
  },
  metricRowMobile: {
    flexWrap: 'wrap',
  },
  metric: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.78)',
    borderColor: '#DDE4F0',
    borderRadius: 14,
    borderWidth: 1,
    flex: 1,
    flexDirection: 'row',
    gap: 18,
    minHeight: 92,
    minWidth: 0,
    paddingHorizontal: 22,
    paddingVertical: 16,
    boxShadow: '0 16px 32px rgba(83, 102, 143, 0.09)',
  },
  metricCompact: {
    alignItems: 'flex-start',
    flexBasis: '45%',
    flexDirection: 'column',
    gap: 9,
    minHeight: 108,
    minWidth: 140,
    paddingHorizontal: 12,
    paddingVertical: 14,
  },
  metricIcon: {
    alignItems: 'center',
    borderRadius: 15,
    height: 52,
    justifyContent: 'center',
    width: 52,
  },
  metricIconCompact: {
    borderRadius: 12,
    height: 40,
    width: 40,
  },
  metricIconViolet: {
    backgroundColor: '#EFEAFE',
  },
  metricIconGreen: {
    backgroundColor: '#DDF5EA',
  },
  metricIconBlue: {
    backgroundColor: '#E5F0FF',
  },
  metricCopy: {
    flex: 1,
    minWidth: 0,
  },
  metricValue: {
    color: '#111827',
    fontSize: 25,
    fontWeight: '900',
    lineHeight: 30,
  },
  metricValueCompact: {
    fontSize: 20,
    lineHeight: 24,
  },
  metricLabel: {
    color: '#536179',
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 19,
    marginTop: 2,
  },
  metricLabelCompact: {
    fontSize: 12,
    lineHeight: 16,
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
    backgroundColor: 'rgba(255, 255, 255, 0.78)',
    borderColor: '#DDE4F0',
    borderRadius: 15,
    borderWidth: 1,
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 30,
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
    maxWidth: 390,
    textAlign: 'center',
  },
  emptyButton: {
    backgroundColor: '#6C63FF',
    borderRadius: 11,
    marginTop: 3,
    paddingHorizontal: 15,
    paddingVertical: 10,
  },
  emptyButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
  },
  sectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 13,
    marginTop: 2,
  },
  sectionCopy: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  sectionTitle: {
    color: '#111827',
    fontSize: 25,
    fontWeight: '900',
    lineHeight: 30,
  },
  sectionSubtitle: {
    color: '#7C879A',
    fontSize: 13,
    fontWeight: '600',
  },
  cardGrid: {
    gap: 12,
  },
  cardGridWide: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  viewAllButton: {
    alignItems: 'center',
    alignSelf: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.82)',
    borderColor: '#DDE4F2',
    borderRadius: 13,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 9,
    justifyContent: 'center',
    marginTop: 2,
    paddingHorizontal: 18,
    paddingVertical: 12,
    boxShadow: '0 12px 24px rgba(91, 111, 255, 0.08)',
  },
  viewAllButtonText: {
    color: '#5B4DFF',
    fontSize: 14,
    fontWeight: '900',
  },
  caseCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.82)',
    borderColor: '#DDE4F0',
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 18,
    minHeight: 190,
    padding: 16,
    width: '100%',
    boxShadow: '0 16px 32px rgba(70, 91, 132, 0.10)',
  },
  caseCardMobile: {
    gap: 14,
    minHeight: 168,
    padding: 14,
  },
  caseCardWide: {
    width: '49.1%',
  },
  caseVisual: {
    alignItems: 'center',
    backgroundColor: '#E8EEF7',
    borderColor: '#DDE4F0',
    borderRadius: 13,
    borderWidth: 1,
    flexShrink: 0,
    height: 138,
    justifyContent: 'center',
    overflow: 'hidden',
    width: 126,
  },
  caseVisualImage: {
    height: '100%',
    width: '100%',
  },
  caseVisualCompact: {
    height: 118,
    width: 96,
  },
  caseVisualBadge: {
    backgroundColor: 'rgba(255, 255, 255, 0.75)',
    borderColor: '#DDE4F0',
    borderRadius: 999,
    borderWidth: 1,
    left: 10,
    paddingHorizontal: 8,
    paddingVertical: 4,
    position: 'absolute',
    top: 10,
  },
  caseVisualBadgeText: {
    color: '#39435A',
    fontSize: 11,
    fontWeight: '900',
  },
  caseBody: {
    flex: 1,
    gap: 12,
    minWidth: 0,
  },
  caseHeaderRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between',
  },
  caseIdentity: {
    alignItems: 'flex-start',
    flex: 1,
    flexDirection: 'row',
    gap: 10,
    minWidth: 0,
  },
  countryMark: {
    alignItems: 'center',
    borderRadius: 7,
    height: 27,
    justifyContent: 'center',
    width: 36,
  },
  countryMarkCanada: {
    backgroundColor: '#E8F5F9',
    borderColor: '#CDE8F0',
    borderWidth: 1,
  },
  countryMarkChina: {
    backgroundColor: '#FFF4E5',
    borderColor: '#FEDF89',
    borderWidth: 1,
  },
  countryMarkUs: {
    backgroundColor: '#EFF2FF',
    borderColor: '#D9DFFD',
    borderWidth: 1,
  },
  countryMarkText: {
    color: '#1E293B',
    fontSize: 12,
    fontWeight: '900',
  },
  caseMetaStack: {
    flex: 1,
    gap: 3,
    minWidth: 0,
  },
  sourceEyebrow: {
    color: '#6C63FF',
    fontSize: 9,
    fontWeight: '900',
    lineHeight: 12,
    textTransform: 'uppercase',
  },
  sourceName: {
    color: '#667085',
    fontSize: 12,
    fontWeight: '900',
    lineHeight: 16,
  },
  regionMeta: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 14,
  },
  publishedDate: {
    color: '#718096',
    fontSize: 12,
    fontWeight: '700',
  },
  statusPill: {
    borderRadius: 999,
    flexShrink: 1,
    maxWidth: 178,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  statusPillCompact: {
    maxWidth: 92,
    paddingHorizontal: 10,
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
  caseTitle: {
    color: '#0F172A',
    fontSize: 19,
    fontWeight: '900',
    lineHeight: 24,
  },
  caseSummary: {
    color: '#536179',
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 21,
  },
  caseFooter: {
    alignItems: 'baseline',
    flexDirection: 'row',
    gap: 14,
    marginTop: 'auto',
  },
  reward: {
    color: '#B45309',
    fontSize: 17,
    fontWeight: '900',
  },
  rewardLabel: {
    color: '#8090AA',
    fontSize: 12,
    fontWeight: '800',
  },
  safetyBanner: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.70)',
    borderColor: '#DDE4F2',
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 14,
    paddingHorizontal: 22,
    paddingVertical: 12,
  },
  safetyIcon: {
    alignItems: 'center',
    backgroundColor: '#6C74FF',
    borderRadius: 10,
    height: 34,
    justifyContent: 'center',
    width: 34,
  },
  safetyText: {
    color: '#697895',
    flex: 1,
    fontSize: 13,
    fontWeight: '800',
    lineHeight: 18,
  },
  learnMorePill: {
    alignItems: 'center',
    borderColor: '#DFE5F2',
    borderRadius: 10,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 13,
    paddingVertical: 8,
  },
  learnMoreText: {
    color: '#6C63FF',
    fontSize: 13,
    fontWeight: '900',
  },
});
