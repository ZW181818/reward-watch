import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocalSearchParams } from 'expo-router';
import { Image, type ImageProps } from 'expo-image';
import { SymbolView } from 'expo-symbols';
import {
  ActivityIndicator,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { API_BASE_URL, fetchCase, resolveApiAssetUrl } from '@/lib/cases';
import {
  formatCaseReward,
  formatRewardAmount,
  getCaseOfficialSources,
  getCaseRegionLabel,
  getCaseSourceName,
} from '@/lib/case-display';
import { isCaseFavorite, loadFavoriteIds, toggleFavoriteCase } from '@/lib/favorites';
import type { RewardCase } from '@/types/reward-case';

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

export default function CaseDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [rewardCase, setRewardCase] = useState<RewardCase | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { width } = useWindowDimensions();
  const isWide = width >= 900;

  useEffect(() => {
    let isMounted = true;

    if (!id) {
      setError('Missing case id');
      setIsLoading(false);
      return;
    }

    Promise.all([fetchCase(id), loadFavoriteIds()])
      .then(([nextCase, favoriteIds]) => {
        if (!isMounted) {
          return;
        }

        setRewardCase(nextCase);
        setIsFavorite(isCaseFavorite(nextCase, favoriteIds));
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
  }, [id]);

  async function handleToggleFavorite() {
    if (!rewardCase) {
      return;
    }

    const nextIds = await toggleFavoriteCase(rewardCase);
    setIsFavorite(isCaseFavorite(rewardCase, nextIds));
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.topBar}>
          <Link href="/cases" asChild>
            <Pressable accessibilityRole="link" style={styles.backLink}>
              <SymbolView
                name={{ ios: 'arrow.left', android: 'arrow_back', web: 'arrow_back' }}
                size={16}
                tintColor="#6C63FF"
              />
              <Text style={styles.backLinkText}>All Cases</Text>
            </Pressable>
          </Link>

          <Link href="/favorites" asChild>
            <Pressable accessibilityRole="link" style={styles.savedLink}>
              <Text style={styles.savedLinkText}>Saved</Text>
            </Pressable>
          </Link>
        </View>

        {isLoading ? (
          <View style={styles.loadingArea}>
            <ActivityIndicator color="#6366F1" />
            <Text style={styles.loadingText}>Loading case details</Text>
          </View>
        ) : error || !rewardCase ? (
          <View style={styles.errorState}>
            <Text style={styles.errorTitle}>Case unavailable</Text>
            <Text style={styles.errorText}>
              {error ?? `The API at ${API_BASE_URL} did not return this case.`}
            </Text>
          </View>
        ) : (
          <>
            <View style={[styles.hero, isWide && styles.heroWide]}>
              <CaseGallery isWide={isWide} rewardCase={rewardCase} />

              <View style={styles.heroCopy}>
                <View style={styles.metaRow}>
                  <View style={styles.countryBadge}>
                    <Text style={styles.countryBadgeText}>{rewardCase.country}</Text>
                  </View>
                  <View style={styles.sourceStack}>
                    <Text style={styles.sourceEyebrow}>Official source</Text>
                    <Text style={styles.sourceName} numberOfLines={1}>
                      {getCaseSourceName(rewardCase)}
                    </Text>
                    {getCaseRegionLabel(rewardCase) ? (
                      <Text style={styles.regionMeta} numberOfLines={1}>
                        {getCaseRegionLabel(rewardCase)}
                      </Text>
                    ) : null}
                    {rewardCase.caseType ? (
                      <Text style={styles.caseType} numberOfLines={1}>
                        {rewardCase.caseType}
                      </Text>
                    ) : null}
                  </View>
                </View>

                <Text style={styles.title}>{rewardCase.title}</Text>
                {rewardCase.description && rewardCase.description !== rewardCase.summary ? (
                  <Text style={styles.description}>{rewardCase.description}</Text>
                ) : null}

                <View style={styles.factGrid}>
                  <Fact label="Reward" value={formatCaseReward(rewardCase)} emphasis />
                  <Fact label="Status" value={rewardCase.status} />
                  <Fact label="Published" value={formatDate(rewardCase.publishedDate)} />
                  {rewardCase.sourceUpdatedDate ? (
                    <Fact label="Source updated" value={formatDate(rewardCase.sourceUpdatedDate)} />
                  ) : null}
                  <Fact label="Data checked" value={formatDate(rewardCase.lastVerified)} />
                </View>

                <View style={styles.actionRow}>
                  <Pressable
                    accessibilityRole="button"
                    onPress={handleToggleFavorite}
                    style={[styles.favoriteButton, isFavorite && styles.favoriteButtonActive]}>
                    <SymbolView
                      name={{ ios: isFavorite ? 'bookmark.fill' : 'bookmark', android: 'bookmark', web: 'bookmark' }}
                      size={18}
                      tintColor={isFavorite ? '#FFFFFF' : '#6C63FF'}
                    />
                    <Text
                      style={[
                        styles.favoriteButtonText,
                        isFavorite && styles.favoriteButtonTextActive,
                      ]}>
                      {isFavorite ? 'Saved' : 'Save case'}
                    </Text>
                  </Pressable>

                  <Pressable
                    accessibilityRole="link"
                    onPress={() => Linking.openURL(rewardCase.sourceUrl)}
                    style={styles.sourceButton}>
                    <Text style={styles.sourceButtonText}>Official source</Text>
                    <SymbolView
                      name={{ ios: 'arrow.up.right', android: 'open_in_new', web: 'open_in_new' }}
                      size={16}
                      tintColor="#6C63FF"
                    />
                  </Pressable>
                </View>
              </View>
            </View>

            {rewardCase.warningMessage ? (
              <View style={styles.officialWarning}>
                <View style={styles.officialWarningIcon}>
                  <SymbolView
                    name={{ ios: 'exclamationmark.triangle.fill', android: 'warning', web: 'warning' }}
                    size={20}
                    tintColor="#A15C00"
                  />
                </View>
                <View style={styles.officialWarningCopy}>
                  <Text style={styles.officialWarningLabel}>Official source warning</Text>
                  <Text style={styles.officialWarningText}>{rewardCase.warningMessage}</Text>
                </View>
              </View>
            ) : null}

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Case summary</Text>
              <Text style={styles.summary}>{rewardCase.summary}</Text>
              {rewardCase.rewardText ? (
                <View style={styles.rewardStatement}>
                  <Text style={styles.rewardStatementLabel}>Official reward notice</Text>
                  <Text style={styles.rewardStatementText}>{rewardCase.rewardText}</Text>
                </View>
              ) : null}
              <OfficialSources rewardCase={rewardCase} />
            </View>

            <CaseProfile rewardCase={rewardCase} />

            <View style={styles.safetyBanner}>
              <View style={styles.safetyIcon}>
                <SymbolView
                  name={{ ios: 'checkmark.shield.fill', android: 'verified_user', web: 'verified_user' }}
                  size={23}
                  tintColor="#FFFFFF"
                />
              </View>
              <Text style={styles.safetyText}>
                Do not approach any individual. Submit information directly to the official source.
              </Text>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function CaseGallery({ isWide, rewardCase }: { isWide: boolean; rewardCase: RewardCase }) {
  const images = useMemo(() => getCaseImages(rewardCase), [rewardCase]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [mainImageFailed, setMainImageFailed] = useState(false);
  const [mainRetryKey, setMainRetryKey] = useState(0);
  const [visibleThumbnailCount, setVisibleThumbnailCount] = useState(0);
  const { height } = useWindowDimensions();
  const selectedImage = images[selectedIndex] ?? images[0];

  useEffect(() => {
    setSelectedIndex(0);
    setIsViewerOpen(false);
  }, [rewardCase.id]);

  useEffect(() => {
    setMainImageFailed(false);
    setMainRetryKey(0);
  }, [selectedImage]);

  useEffect(() => {
    setVisibleThumbnailCount(0);

    if (images.length === 0) {
      return;
    }

    let nextCount = 0;
    const timer = setInterval(() => {
      nextCount += 1;
      setVisibleThumbnailCount(nextCount);

      if (nextCount >= images.length) {
        clearInterval(timer);
      }
    }, 180);

    return () => clearInterval(timer);
  }, [images.length, rewardCase.id]);

  function selectPrevious() {
    setSelectedIndex((current) => Math.max(0, current - 1));
  }

  function selectNext() {
    setSelectedIndex((current) => Math.min(images.length - 1, current + 1));
  }

  if (images.length === 0) {
    return (
      <View style={[styles.gallery, isWide && styles.galleryWide]}>
        <View style={styles.placeholderImage}>
          <SymbolView
            name={{ ios: 'doc.text.magnifyingglass', android: 'description', web: 'description' }}
            size={58}
            tintColor="#5A63D8"
          />
          <Text style={styles.placeholderText}>Official Notice</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.gallery, isWide && styles.galleryWide]}>
      <Pressable
        accessibilityLabel={
          mainImageFailed
            ? `Retry photo ${selectedIndex + 1} of ${images.length}`
            : `Open photo ${selectedIndex + 1} of ${images.length}`
        }
        accessibilityRole="button"
        onPress={() => {
          if (mainImageFailed) {
            setMainImageFailed(false);
            setMainRetryKey((current) => current + 1);
            return;
          }

          setIsViewerOpen(true);
        }}
        style={styles.mainImageButton}>
        <ReliableImage
          accessibilityLabel={`${rewardCase.title} official case image ${selectedIndex + 1}`}
          contentFit="cover"
          fallbackLabel="Tap to retry"
          onFinalError={() => setMainImageFailed(true)}
          onLoad={() => setMainImageFailed(false)}
          priority="high"
          retryKey={mainRetryKey}
          style={styles.caseImage}
          uri={selectedImage}
        />
        <View style={styles.photoCountBadge}>
          <SymbolView
            name={{ ios: 'photo.on.rectangle', android: 'collections', web: 'collections' }}
            size={15}
            tintColor="#FFFFFF"
          />
          <Text style={styles.photoCountText}>
            {images.length === 1 ? 'View photo' : `View all ${images.length}`}
          </Text>
        </View>
      </Pressable>

      {images.length > 1 && (
        <ScrollView
          contentContainerStyle={styles.thumbnailRow}
          horizontal
          showsHorizontalScrollIndicator={false}>
          {images.map((imageUrl, index) => (
            <Pressable
              accessibilityLabel={`Show photo ${index + 1}`}
              accessibilityRole="button"
              key={imageUrl}
              onPress={() => setSelectedIndex(index)}
              style={[
                styles.thumbnailButton,
                selectedIndex === index && styles.thumbnailButtonActive,
              ]}>
              {index < visibleThumbnailCount ? (
                <ReliableImage
                  accessibilityLabel={`${rewardCase.title} thumbnail ${index + 1}`}
                  contentFit="cover"
                  fallbackLabel=""
                  maxRetries={2}
                  priority={index === selectedIndex ? 'normal' : 'low'}
                  style={styles.thumbnailImage}
                  uri={imageUrl}
                />
              ) : (
                <View style={styles.thumbnailLoading} />
              )}
            </Pressable>
          ))}
        </ScrollView>
      )}

      <Modal
        animationType="fade"
        onRequestClose={() => setIsViewerOpen(false)}
        transparent
        visible={isViewerOpen}>
        <SafeAreaView style={styles.viewerBackdrop}>
          <View style={styles.viewerHeader}>
            <View>
              <Text style={styles.viewerTitle}>Case photos</Text>
              <Text style={styles.viewerCounter}>
                {selectedIndex + 1} of {images.length}
              </Text>
            </View>
            <Pressable
              accessibilityLabel="Close photo viewer"
              accessibilityRole="button"
              onPress={() => setIsViewerOpen(false)}
              style={styles.viewerCloseButton}>
              <SymbolView
                name={{ ios: 'xmark', android: 'close', web: 'close' }}
                size={22}
                tintColor="#344054"
              />
            </Pressable>
          </View>

          <View style={[styles.viewerStage, { minHeight: Math.max(280, height - 230) }]}>
            <Pressable
              accessibilityLabel="Previous photo"
              accessibilityRole="button"
              disabled={selectedIndex === 0}
              onPress={selectPrevious}
              style={[
                styles.viewerArrow,
                selectedIndex === 0 && styles.viewerArrowDisabled,
              ]}>
              <SymbolView
                name={{ ios: 'chevron.left', android: 'chevron_left', web: 'chevron_left' }}
                size={26}
                tintColor="#344054"
              />
            </Pressable>

            <ReliableImage
              accessibilityLabel={`${rewardCase.title} official case image ${selectedIndex + 1}`}
              contentFit="contain"
              priority="high"
              style={styles.viewerImage}
              uri={selectedImage}
            />

            <Pressable
              accessibilityLabel="Next photo"
              accessibilityRole="button"
              disabled={selectedIndex === images.length - 1}
              onPress={selectNext}
              style={[
                styles.viewerArrow,
                selectedIndex === images.length - 1 && styles.viewerArrowDisabled,
              ]}>
              <SymbolView
                name={{ ios: 'chevron.right', android: 'chevron_right', web: 'chevron_right' }}
                size={26}
                tintColor="#344054"
              />
            </Pressable>
          </View>

          {images.length > 1 && (
            <ScrollView
              contentContainerStyle={styles.viewerThumbnailRow}
              horizontal
              showsHorizontalScrollIndicator={false}>
              {images.map((imageUrl, index) => (
                <Pressable
                  accessibilityLabel={`View photo ${index + 1}`}
                  accessibilityRole="button"
                  key={imageUrl}
                  onPress={() => setSelectedIndex(index)}
                  style={[
                    styles.viewerThumbnailButton,
                    selectedIndex === index && styles.thumbnailButtonActive,
                  ]}>
                  {index < visibleThumbnailCount ? (
                    <ReliableImage
                      accessibilityLabel={`${rewardCase.title} viewer thumbnail ${index + 1}`}
                      contentFit="cover"
                      fallbackLabel=""
                      maxRetries={2}
                      priority={index === selectedIndex ? 'normal' : 'low'}
                      style={styles.thumbnailImage}
                      uri={imageUrl}
                    />
                  ) : (
                    <View style={styles.thumbnailLoading} />
                  )}
                </Pressable>
              ))}
            </ScrollView>
          )}
        </SafeAreaView>
      </Modal>
    </View>
  );
}

function getCaseImages(rewardCase: RewardCase) {
  const imageUrls = [rewardCase.imageUrl, ...(rewardCase.imageUrls ?? [])]
    .filter((imageUrl): imageUrl is string => Boolean(imageUrl))
    .map(resolveApiAssetUrl);

  return Array.from(new Set(imageUrls));
}

function ReliableImage({
  accessibilityLabel,
  contentFit,
  fallbackLabel = 'Image unavailable',
  maxRetries = 3,
  onFinalError,
  onLoad,
  priority = 'normal',
  retryKey = 0,
  style,
  uri,
}: {
  accessibilityLabel: string;
  contentFit: NonNullable<ImageProps['contentFit']>;
  fallbackLabel?: string;
  maxRetries?: number;
  onFinalError?: () => void;
  onLoad?: () => void;
  priority?: NonNullable<ImageProps['priority']>;
  retryKey?: number;
  style: ImageProps['style'];
  uri: string;
}) {
  const [attempt, setAttempt] = useState(0);
  const [hasFailed, setHasFailed] = useState(false);
  const loadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (loadTimer.current) {
      clearTimeout(loadTimer.current);
      loadTimer.current = null;
    }
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }

    setAttempt(0);
    setHasFailed(false);
  }, [retryKey, uri]);

  useEffect(
    () => () => {
      if (loadTimer.current) {
        clearTimeout(loadTimer.current);
      }
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
      }
    },
    []
  );

  function handleError() {
    if (loadTimer.current) {
      clearTimeout(loadTimer.current);
      loadTimer.current = null;
    }
    if (retryTimer.current) {
      return;
    }

    if (attempt >= maxRetries) {
      setHasFailed(true);
      onFinalError?.();
      return;
    }

    retryTimer.current = setTimeout(
      () => {
        retryTimer.current = null;
        setAttempt((current) => current + 1);
      },
      350 * 2 ** attempt
    );
  }

  if (hasFailed) {
    return (
      <View style={[style, styles.reliableImageFallback]}>
        <SymbolView
          name={{ ios: 'photo', android: 'image', web: 'image' }}
          size={24}
          tintColor="#8793A8"
        />
        {fallbackLabel ? (
          <Text style={styles.reliableImageFallbackText}>{fallbackLabel}</Text>
        ) : null}
      </View>
    );
  }

  return (
    <Image
      accessibilityLabel={accessibilityLabel}
      cachePolicy="memory-disk"
      contentFit={contentFit}
      key={`${uri}-${retryKey}-${attempt}`}
      onError={handleError}
      onLoad={() => {
        if (loadTimer.current) {
          clearTimeout(loadTimer.current);
          loadTimer.current = null;
        }
        if (retryTimer.current) {
          clearTimeout(retryTimer.current);
          retryTimer.current = null;
        }
        onLoad?.();
      }}
      onLoadStart={() => {
        if (loadTimer.current) {
          clearTimeout(loadTimer.current);
        }
        loadTimer.current = setTimeout(handleError, 5000);
      }}
      priority={priority}
      recyclingKey={`${uri}-${retryKey}-${attempt}`}
      source={{ uri }}
      style={style}
      transition={attempt === 0 ? 120 : 0}
    />
  );
}

function Fact({
  emphasis,
  label,
  value,
}: {
  emphasis?: boolean;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.fact}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={[styles.factValue, emphasis && styles.factValueEmphasis]} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

function CaseProfile({ rewardCase }: { rewardCase: RewardCase }) {
  const profileItems = [
    {
      label: rewardCase.country === 'US' ? 'State' : 'Province',
      value: getCaseRegionLabel(rewardCase),
    },
    { label: 'Aliases', value: rewardCase.aliases?.join(', ') },
    { label: 'Age', value: rewardCase.age },
    { label: 'Date of birth used', value: rewardCase.dateOfBirth },
    { label: 'Place of birth', value: rewardCase.placeOfBirth },
    { label: 'Sex', value: rewardCase.sex },
    { label: 'Race', value: rewardCase.race },
    { label: 'Nationality', value: rewardCase.nationality },
    { label: 'Hair', value: rewardCase.hair },
    { label: 'Eyes', value: rewardCase.eyes },
    { label: 'Height', value: rewardCase.height },
    { label: 'Weight', value: rewardCase.weight },
    { label: 'Possible communities', value: rewardCase.locations },
    { label: 'Identifying features', value: rewardCase.distinguishingFeatures },
  ].filter((item): item is { label: string; value: string } => Boolean(item.value));

  if (profileItems.length === 0) {
    return null;
  }

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Official case information</Text>
      <View style={styles.profileGrid}>
        {profileItems.map((item) => (
          <View key={item.label} style={styles.profileItem}>
            <Text style={styles.profileLabel}>{item.label}</Text>
            <Text style={styles.profileValue}>{item.value}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function OfficialSources({ rewardCase }: { rewardCase: RewardCase }) {
  const sources = getCaseOfficialSources(rewardCase);

  return (
    <View style={styles.sourceAttribution}>
      <Text style={styles.sourceAttributionLabel}>
        {sources.length > 1 ? `Official sources (${sources.length})` : 'Source attribution'}
      </Text>
      {sources.map((source) => (
        <Pressable
          accessibilityLabel={`Open official source from ${source.author}`}
          accessibilityRole="link"
          key={`${source.caseId}-${source.url}`}
          onPress={() => Linking.openURL(source.url)}
          style={styles.sourceRecord}>
          <View style={styles.sourceRecordCopy}>
            <Text style={styles.sourceRecordAuthor}>{source.author}</Text>
            {source.title ? (
              <Text style={styles.sourceAttributionText} numberOfLines={2}>
                {source.title}
              </Text>
            ) : null}
            <Text style={styles.sourceRecordReward}>
              {formatRewardAmount(
                source.reward,
                source.rewardCurrency,
                rewardCase.country
              )}
            </Text>
          </View>
          <SymbolView
            name={{ ios: 'arrow.up.right', android: 'open_in_new', web: 'open_in_new' }}
            size={16}
            tintColor="#6C63FF"
          />
        </Pressable>
      ))}
    </View>
  );
}

function formatDate(value: string) {
  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return dateFormatter.format(parsedDate);
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F6F8FC',
  },
  content: {
    alignSelf: 'center',
    gap: 18,
    maxWidth: 1120,
    paddingBottom: 52,
    paddingHorizontal: 22,
    paddingTop: 26,
    width: '100%',
  },
  topBar: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
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
  savedLink: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 13,
    paddingVertical: 8,
  },
  savedLinkText: {
    color: '#475467',
    fontSize: 13,
    fontWeight: '900',
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
  errorState: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 16,
    borderWidth: 1,
    gap: 8,
    padding: 24,
  },
  errorTitle: {
    color: '#111827',
    fontSize: 20,
    fontWeight: '900',
  },
  errorText: {
    color: '#667085',
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
  },
  hero: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 18,
    borderWidth: 1,
    gap: 18,
    padding: 18,
    boxShadow: '0 16px 32px rgba(70, 91, 132, 0.08)',
  },
  heroWide: {
    flexDirection: 'row',
  },
  gallery: {
    gap: 10,
    width: '100%',
  },
  galleryWide: {
    flexShrink: 0,
    width: 370,
  },
  mainImageButton: {
    backgroundColor: '#E5EAF3',
    borderRadius: 14,
    height: 310,
    overflow: 'hidden',
    position: 'relative',
    width: '100%',
  },
  caseImage: {
    height: '100%',
    width: '100%',
  },
  placeholderImage: {
    alignItems: 'center',
    backgroundColor: '#DDEBFF',
    borderColor: '#DDE4F0',
    borderRadius: 14,
    borderWidth: 1,
    gap: 10,
    height: 310,
    justifyContent: 'center',
    width: '100%',
  },
  placeholderText: {
    color: '#536179',
    fontSize: 14,
    fontWeight: '900',
  },
  photoCountBadge: {
    alignItems: 'center',
    backgroundColor: 'rgba(17, 24, 39, 0.78)',
    borderRadius: 9,
    bottom: 12,
    flexDirection: 'row',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 7,
    position: 'absolute',
    right: 12,
  },
  photoCountText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '900',
  },
  thumbnailRow: {
    gap: 8,
    paddingVertical: 2,
  },
  thumbnailButton: {
    backgroundColor: '#E5EAF3',
    borderColor: 'transparent',
    borderRadius: 9,
    borderWidth: 2,
    height: 58,
    overflow: 'hidden',
    width: 58,
  },
  thumbnailButtonActive: {
    borderColor: '#6C63FF',
  },
  thumbnailImage: {
    height: '100%',
    width: '100%',
  },
  thumbnailLoading: {
    backgroundColor: '#EEF2F7',
    height: '100%',
    width: '100%',
  },
  reliableImageFallback: {
    alignItems: 'center',
    backgroundColor: '#DDEBFF',
    gap: 8,
    justifyContent: 'center',
  },
  reliableImageFallbackText: {
    color: '#536179',
    fontSize: 13,
    fontWeight: '900',
    paddingHorizontal: 8,
    textAlign: 'center',
  },
  viewerBackdrop: {
    backgroundColor: 'rgba(248, 250, 252, 0.98)',
    flex: 1,
    paddingBottom: 18,
    paddingHorizontal: 18,
    paddingTop: 14,
  },
  viewerHeader: {
    alignItems: 'center',
    alignSelf: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    maxWidth: 1280,
    paddingBottom: 14,
    width: '100%',
  },
  viewerTitle: {
    color: '#111827',
    fontSize: 19,
    fontWeight: '900',
  },
  viewerCounter: {
    color: '#667085',
    fontSize: 13,
    fontWeight: '800',
    marginTop: 2,
  },
  viewerCloseButton: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 11,
    borderWidth: 1,
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  viewerStage: {
    alignItems: 'center',
    alignSelf: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'center',
    maxWidth: 1400,
    width: '100%',
  },
  viewerImage: {
    flex: 1,
    height: '100%',
    maxWidth: 1120,
  },
  viewerArrow: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 12,
    borderWidth: 1,
    flexShrink: 0,
    height: 46,
    justifyContent: 'center',
    width: 46,
  },
  viewerArrowDisabled: {
    opacity: 0.28,
  },
  viewerThumbnailRow: {
    alignSelf: 'center',
    gap: 8,
    maxWidth: 1120,
    paddingTop: 14,
  },
  viewerThumbnailButton: {
    backgroundColor: '#E5EAF3',
    borderColor: 'transparent',
    borderRadius: 9,
    borderWidth: 2,
    height: 64,
    overflow: 'hidden',
    width: 64,
  },
  heroCopy: {
    flex: 1,
    gap: 16,
    minWidth: 0,
  },
  metaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  sourceStack: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  countryBadge: {
    backgroundColor: '#EFF2FF',
    borderColor: '#D9DFFD',
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  countryBadgeText: {
    color: '#1E293B',
    fontSize: 12,
    fontWeight: '900',
  },
  sourceEyebrow: {
    color: '#6C63FF',
    fontSize: 9,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  sourceName: {
    color: '#475467',
    fontSize: 13,
    fontWeight: '900',
  },
  regionMeta: {
    color: '#667085',
    fontSize: 12,
    fontWeight: '800',
  },
  caseType: {
    color: '#98A2B3',
    fontSize: 12,
    fontWeight: '700',
  },
  title: {
    color: '#111827',
    fontSize: 31,
    fontWeight: '900',
    lineHeight: 38,
  },
  description: {
    color: '#536179',
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 22,
  },
  factGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  fact: {
    backgroundColor: '#F8FAFD',
    borderColor: '#E8EEF6',
    borderRadius: 12,
    borderWidth: 1,
    minWidth: 142,
    paddingHorizontal: 13,
    paddingVertical: 11,
  },
  factLabel: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  factValue: {
    color: '#344054',
    fontSize: 14,
    fontWeight: '900',
    marginTop: 4,
  },
  factValueEmphasis: {
    color: '#B45309',
    fontSize: 18,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  favoriteButton: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#C7D2FE',
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  favoriteButtonActive: {
    backgroundColor: '#6C63FF',
    borderColor: '#6C63FF',
  },
  favoriteButtonText: {
    color: '#6C63FF',
    fontSize: 14,
    fontWeight: '900',
  },
  favoriteButtonTextActive: {
    color: '#FFFFFF',
  },
  sourceButton: {
    alignItems: 'center',
    backgroundColor: '#F4F3FF',
    borderRadius: 12,
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  sourceButtonText: {
    color: '#6C63FF',
    fontSize: 14,
    fontWeight: '900',
  },
  officialWarning: {
    alignItems: 'flex-start',
    backgroundColor: '#FFF9ED',
    borderColor: '#F2D79C',
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  officialWarningIcon: {
    alignItems: 'center',
    backgroundColor: '#FFF0CC',
    borderRadius: 9,
    height: 34,
    justifyContent: 'center',
    width: 34,
  },
  officialWarningCopy: {
    flex: 1,
    gap: 4,
    minWidth: 0,
  },
  officialWarningLabel: {
    color: '#8A4B00',
    fontSize: 11,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  officialWarningText: {
    color: '#5F451F',
    fontSize: 14,
    fontWeight: '800',
    lineHeight: 20,
  },
  section: {
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F0',
    borderRadius: 16,
    borderWidth: 1,
    gap: 10,
    padding: 18,
  },
  sectionTitle: {
    color: '#111827',
    fontSize: 20,
    fontWeight: '900',
  },
  summary: {
    color: '#475467',
    fontSize: 15,
    fontWeight: '600',
    lineHeight: 23,
  },
  rewardStatement: {
    borderColor: '#EEF2F7',
    borderTopWidth: 1,
    gap: 5,
    marginTop: 4,
    paddingTop: 14,
  },
  rewardStatementLabel: {
    color: '#8A6A31',
    fontSize: 11,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  rewardStatementText: {
    color: '#475467',
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 21,
  },
  sourceAttribution: {
    borderColor: '#EEF2F7',
    borderTopWidth: 1,
    gap: 5,
    marginTop: 4,
    paddingTop: 14,
  },
  sourceAttributionLabel: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  sourceAttributionText: {
    color: '#667085',
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 19,
  },
  sourceRecord: {
    alignItems: 'center',
    borderColor: '#EEF2F7',
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'space-between',
    paddingVertical: 11,
  },
  sourceRecordCopy: {
    flex: 1,
    gap: 3,
    minWidth: 0,
  },
  sourceRecordAuthor: {
    color: '#344054',
    fontSize: 13,
    fontWeight: '900',
  },
  sourceRecordReward: {
    color: '#B45309',
    fontSize: 12,
    fontWeight: '900',
  },
  profileGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  profileItem: {
    borderColor: '#EEF2F7',
    borderBottomWidth: 1,
    gap: 4,
    minWidth: 210,
    paddingBottom: 12,
    paddingRight: 18,
    paddingTop: 10,
    width: '33.333%',
  },
  profileLabel: {
    color: '#98A2B3',
    fontSize: 11,
    fontWeight: '900',
    textTransform: 'uppercase',
  },
  profileValue: {
    color: '#344054',
    fontSize: 14,
    fontWeight: '800',
    lineHeight: 20,
  },
  safetyBanner: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#DDE4F2',
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 14,
    paddingHorizontal: 18,
    paddingVertical: 14,
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
});
