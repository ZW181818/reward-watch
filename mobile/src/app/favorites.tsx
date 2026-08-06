import { useEffect, useMemo, useState } from 'react';
import { Link } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { fetchCase } from '@/lib/cases';
import { formatCaseReward, getCaseSourceName, isPublisherNotice } from '@/lib/case-display';
import { isCaseFavorite, loadFavoriteIds } from '@/lib/favorites';
import { LanguageSelector } from '@/components/language-selector';
import { useLanguage } from '@/lib/i18n';
import type { RewardCase } from '@/types/reward-case';

export default function FavoritesScreen() {
  const { t } = useLanguage();
  const [cases, setCases] = useState<RewardCase[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { width } = useWindowDimensions();
  const isWide = width >= 820;

  useEffect(() => {
    let isMounted = true;

    loadFavoriteIds()
      .then(async (nextFavoriteIds) => {
        const results = await Promise.allSettled(nextFavoriteIds.map((id) => fetchCase(id)));
        const nextCases = results.flatMap((result) =>
          result.status === 'fulfilled' ? [result.value] : []
        );

        if (!isMounted) {
          return;
        }

        setCases(nextCases);
        setFavoriteIds(nextFavoriteIds);
        setError(null);
      })
      .catch((requestError: Error) => {
        if (!isMounted) {
          return;
        }

        setError(requestError.message);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const favoriteCases = useMemo(
    () => cases.filter((rewardCase) => isCaseFavorite(rewardCase, favoriteIds)),
    [cases, favoriteIds]
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.topBar}>
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
          <LanguageSelector />
        </View>

        <View style={styles.header}>
          <Text style={styles.title}>{t('savedCases')}</Text>
          <Text style={styles.subtitle}>{t('savedCasesSubtitle')}</Text>
        </View>

        {isLoading ? (
          <View style={styles.loadingArea}>
            <ActivityIndicator color="#6366F1" />
            <Text style={styles.loadingText}>{t('loadingSavedCases')}</Text>
          </View>
        ) : error ? (
          <View style={styles.stateCard}>
            <Text style={styles.stateTitle}>{t('unableToLoadSaved')}</Text>
            <Text style={styles.stateText}>{error}</Text>
          </View>
        ) : favoriteCases.length === 0 ? (
          <View style={styles.stateCard}>
            <SymbolView
              name={{ ios: 'bookmark', android: 'bookmark', web: 'bookmark' }}
              size={38}
              tintColor="#667085"
            />
            <Text style={styles.stateTitle}>{t('noSavedCasesTitle')}</Text>
            <Text style={styles.stateText}>{t('noSavedCasesBody')}</Text>
            <Link href="/cases" asChild>
              <Pressable accessibilityRole="link" style={styles.primaryButton}>
                <Text style={styles.primaryButtonText}>{t('browseCases')}</Text>
              </Pressable>
            </Link>
          </View>
        ) : (
          <View style={[styles.grid, isWide && styles.gridWide]}>
            {favoriteCases.map((rewardCase) => (
              <Link href={{ pathname: '/cases/detail', params: { id: rewardCase.id } }} asChild key={rewardCase.id}>
                <Pressable
                  accessibilityRole="link"
                  style={StyleSheet.flatten([styles.card, isWide && styles.cardWide])}>
                  <View style={styles.cardIcon}>
                    <SymbolView
                      name={{ ios: 'bookmark.fill', android: 'bookmark', web: 'bookmark' }}
                      size={24}
                      tintColor="#6C63FF"
                    />
                  </View>
                  <View style={styles.cardBody}>
                    <Text style={styles.sourceEyebrow}>
                      {t(isPublisherNotice(rewardCase) ? 'publisherSource' : 'officialSource')}
                    </Text>
                    <Text style={styles.sourceName} numberOfLines={1}>
                      {getCaseSourceName(rewardCase)}
                    </Text>
                    <Text style={styles.cardTitle} numberOfLines={2}>
                      {rewardCase.title}
                    </Text>
                    <Text style={styles.reward}>
                      {rewardCase.reward === null ? t('notPublished') : formatCaseReward(rewardCase)}
                    </Text>
                  </View>
                </Pressable>
              </Link>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
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
    maxWidth: 1040,
    paddingBottom: 52,
    paddingHorizontal: 22,
    paddingTop: 26,
    width: '100%',
  },
  topBar: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    position: 'relative',
    zIndex: 100,
  },
  backLink: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 7,
    paddingVertical: 6,
  },
  backLinkText: {
    color: '#6C63FF',
    fontSize: 14,
    fontWeight: '900',
  },
  header: {
    gap: 8,
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
    maxWidth: 620,
  },
  loadingArea: {
    alignItems: 'center',
    gap: 10,
    paddingVertical: 54,
  },
  loadingText: {
    color: '#667085',
    fontSize: 14,
    fontWeight: '700',
  },
  stateCard: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 16,
    borderWidth: 1,
    gap: 11,
    paddingHorizontal: 22,
    paddingVertical: 42,
  },
  stateTitle: {
    color: '#111827',
    fontSize: 20,
    fontWeight: '900',
    textAlign: 'center',
  },
  stateText: {
    color: '#667085',
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
    maxWidth: 430,
    textAlign: 'center',
  },
  primaryButton: {
    backgroundColor: '#6C63FF',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
  },
  grid: {
    gap: 12,
  },
  gridWide: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  card: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 15,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 14,
    padding: 16,
    width: '100%',
  },
  cardWide: {
    width: '49%',
  },
  cardIcon: {
    alignItems: 'center',
    backgroundColor: '#F0EFFF',
    borderRadius: 12,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  cardBody: {
    flex: 1,
    gap: 6,
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
  cardTitle: {
    color: '#111827',
    fontSize: 17,
    fontWeight: '900',
    lineHeight: 22,
  },
  reward: {
    color: '#B45309',
    fontSize: 15,
    fontWeight: '900',
  },
});
