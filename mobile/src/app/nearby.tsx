import { Image } from 'expo-image';
import { Link } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import NearbyMap from '@/components/nearby-map';
import type {
  MapCoordinate,
  MapSearchOrigin,
  NearbyMapPoint,
} from '@/components/nearby-map-types';
import { LanguageSelector } from '@/components/language-selector';
import { ThemeToggle } from '@/components/theme-toggle';
import { formatRewardAmount } from '@/lib/case-display';
import { fetchCaseMap, resolveApiAssetUrl } from '@/lib/cases';
import { type LanguageCode, useLanguage } from '@/lib/i18n';
import { createThemedStyles, themedForeground } from '@/lib/themed-styles';
import type { CaseMapItem, CaseMapLocation } from '@/types/reward-case';


const radiusOptions = [25, 50, 100, 250, 500, 1000] as const;

const nearbyCopy = {
  en: {
    title: 'Rewards near you',
    subtitle: 'Use your location or choose the center of the map to explore relevant public reward notices nearby.',
    backHome: 'Home', allCases: 'All cases', locate: 'Use my location', locating: 'Finding you…',
    relocate: 'Update location', searchHere: 'Search this map area', radius: 'Search radius',
    privacy: 'Your coordinates stay in this browser and are never saved to Reward Watch.',
    beforeLocate: 'Find what is nearby', beforeLocateBody: 'Select “Use my location” to sort notices by distance. You can also move the map and search that area without sharing your location.',
    nearbyResults: 'Nearby notices', mappedCases: '{count} notices have usable city-level locations',
    noResults: 'No city-level notices were found in this range.', nearest: 'The nearest mapped notice is about {distance} km away.',
    expand: 'Expand to {radius} km', loadError: 'The map notices could not be loaded.', retry: 'Try again',
    denied: 'Location access was declined. Move the map and select “Search this map area”, or allow location in your browser settings.',
    unavailable: 'Your browser could not determine a location. You can still move the map and search that area.',
    insecure: 'Location requires a secure HTTPS connection.', deviceOrigin: 'Using your current location', mapOrigin: 'Using the center of the map',
    distance: '{distance} km away', underOneKm: 'Less than 1 km away', viewCase: 'View case',
    locationBasis: 'Matched location: {location}', safetyTitle: 'Location context matters',
    safetyBody: 'Pins show places named in public notices, such as an incident city or possible community. They do not show anyone’s live location. Do not approach any individual.',
    mapUnavailable: 'The interactive map is available on the website.', yourLocation: 'Your current location',
    searchCenter: 'Selected map center', caseLocation: 'Public notice location', clusterCases: 'Grouped notices',
    loading: 'Loading mapped notices…', mapDataNote: 'Only verified city-level locations are used for distance results.',
    notPublished: 'Reward not published', mapAttribution: 'Location names are matched with GeoNames data.',
  },
  zh: {
    title: '你附近的悬赏', subtitle: '使用当前位置，或选择地图中心，直观查看周边相关的公开悬赏公告。',
    backHome: '首页', allCases: '全部案件', locate: '使用我的位置', locating: '正在定位…', relocate: '重新定位',
    searchHere: '搜索地图中心附近', radius: '搜索范围', privacy: '你的坐标只留在当前浏览器，不会保存到 Reward Watch。',
    beforeLocate: '看看附近有什么', beforeLocateBody: '点击“使用我的位置”即可按距离排序；也可以移动地图后搜索该区域，无需分享自己的位置。',
    nearbyResults: '附近公告', mappedCases: '已有 {count} 条公告具备可用的城市级地点', noResults: '当前范围内没有找到城市级公告。',
    nearest: '最近一条地图公告距离约 {distance} 公里。', expand: '扩大到 {radius} 公里', loadError: '地图案件暂时无法加载。', retry: '重新加载',
    denied: '你拒绝了定位权限。可以移动地图后点击“搜索地图中心附近”，或在浏览器设置里允许定位。',
    unavailable: '浏览器暂时无法确定位置。你仍然可以移动地图并搜索该区域。', insecure: '定位功能需要安全的 HTTPS 连接。',
    deviceOrigin: '正在使用你的当前位置', mapOrigin: '正在使用地图中心', distance: '距你约 {distance} 公里', underOneKm: '距离不到 1 公里',
    viewCase: '查看案件', locationBasis: '匹配地点：{location}', safetyTitle: '请正确理解地图位置',
    safetyBody: '标记表示公开公告中提到的案发城市、可能出现社区等地点，不是任何人的实时位置。请勿接近或尝试接触相关人员。',
    mapUnavailable: '互动地图目前仅在网页版提供。', yourLocation: '你的当前位置', searchCenter: '选择的地图中心',
    caseLocation: '公开公告地点', clusterCases: '聚合案件', loading: '正在加载地图案件…',
    mapDataNote: '距离结果只使用经过确认的城市级地点。', notPublished: '悬赏金额未公布', mapAttribution: '地点名称使用 GeoNames 数据进行匹配。',
  },
  fr: {
    title: 'Récompenses près de vous', subtitle: 'Utilisez votre position ou le centre de la carte pour explorer les avis publics à proximité.',
    backHome: 'Accueil', allCases: 'Toutes les affaires', locate: 'Utiliser ma position', locating: 'Localisation…', relocate: 'Actualiser la position',
    searchHere: 'Rechercher autour de la carte', radius: 'Rayon', privacy: 'Vos coordonnées restent dans ce navigateur et ne sont jamais enregistrées.',
    beforeLocate: 'Voir les avis à proximité', beforeLocateBody: 'Utilisez votre position pour classer par distance, ou déplacez la carte sans partager votre position.',
    nearbyResults: 'Avis à proximité', mappedCases: '{count} avis ont une localisation urbaine utilisable', noResults: 'Aucun avis urbain dans ce rayon.',
    nearest: 'L’avis cartographié le plus proche est à environ {distance} km.', expand: 'Élargir à {radius} km', loadError: 'Impossible de charger les avis cartographiés.', retry: 'Réessayer',
    denied: 'L’accès à la position a été refusé. Déplacez la carte et recherchez cette zone.', unavailable: 'Votre position est indisponible. Vous pouvez rechercher autour du centre de la carte.',
    insecure: 'La localisation nécessite HTTPS.', deviceOrigin: 'Position actuelle utilisée', mapOrigin: 'Centre de la carte utilisé', distance: 'À environ {distance} km', underOneKm: 'À moins de 1 km',
    viewCase: 'Voir l’affaire', locationBasis: 'Lieu correspondant : {location}', safetyTitle: 'Bien comprendre les lieux',
    safetyBody: 'Les repères indiquent des lieux cités dans les avis publics, et non la position en direct d’une personne. N’approchez personne.',
    mapUnavailable: 'La carte interactive est disponible sur le site web.', yourLocation: 'Votre position', searchCenter: 'Centre choisi', caseLocation: 'Lieu de l’avis',
    clusterCases: 'Avis groupés', loading: 'Chargement de la carte…', mapDataNote: 'Seuls les lieux urbains vérifiés servent au calcul des distances.',
    notPublished: 'Récompense non publiée', mapAttribution: 'Les noms de lieux sont associés aux données GeoNames.',
  },
  es: {
    title: 'Recompensas cerca de ti', subtitle: 'Usa tu ubicación o el centro del mapa para explorar avisos públicos cercanos.',
    backHome: 'Inicio', allCases: 'Todos los casos', locate: 'Usar mi ubicación', locating: 'Localizando…', relocate: 'Actualizar ubicación',
    searchHere: 'Buscar en esta zona', radius: 'Radio de búsqueda', privacy: 'Tus coordenadas permanecen en este navegador y nunca se guardan.',
    beforeLocate: 'Descubre qué hay cerca', beforeLocateBody: 'Usa tu ubicación para ordenar por distancia o mueve el mapa sin compartirla.',
    nearbyResults: 'Avisos cercanos', mappedCases: '{count} avisos tienen una ubicación urbana utilizable', noResults: 'No hay avisos urbanos en este radio.',
    nearest: 'El aviso más cercano está a unos {distance} km.', expand: 'Ampliar a {radius} km', loadError: 'No se pudieron cargar los avisos del mapa.', retry: 'Reintentar',
    denied: 'Se rechazó el acceso a la ubicación. Mueve el mapa y busca esa zona.', unavailable: 'No se pudo determinar tu ubicación. Puedes buscar alrededor del centro del mapa.',
    insecure: 'La ubicación requiere HTTPS.', deviceOrigin: 'Usando tu ubicación actual', mapOrigin: 'Usando el centro del mapa', distance: 'A unos {distance} km', underOneKm: 'A menos de 1 km',
    viewCase: 'Ver caso', locationBasis: 'Ubicación coincidente: {location}', safetyTitle: 'Interpreta bien las ubicaciones',
    safetyBody: 'Los marcadores muestran lugares citados en avisos públicos, no la ubicación en vivo de una persona. No te acerques a nadie.',
    mapUnavailable: 'El mapa interactivo está disponible en la web.', yourLocation: 'Tu ubicación', searchCenter: 'Centro elegido', caseLocation: 'Lugar del aviso',
    clusterCases: 'Avisos agrupados', loading: 'Cargando el mapa…', mapDataNote: 'Solo se usan ubicaciones urbanas verificadas para las distancias.',
    notPublished: 'Recompensa no publicada', mapAttribution: 'Los nombres de lugares se asocian con datos de GeoNames.',
  },
} satisfies Record<LanguageCode, Record<string, string>>;

type NearbyCopy = (typeof nearbyCopy)['en'];
type NearbyResult = { distanceKm: number; item: CaseMapItem; location: CaseMapLocation };

function interpolate(value: string, params: Record<string, number | string> = {}) {
  return Object.entries(params).reduce(
    (result, [key, replacement]) => result.replaceAll(`{${key}}`, String(replacement)),
    value
  );
}

function haversineDistance(first: MapCoordinate, second: MapCoordinate) {
  const earthRadiusKm = 6371;
  const latitudeDelta = ((second.latitude - first.latitude) * Math.PI) / 180;
  const longitudeDelta = ((second.longitude - first.longitude) * Math.PI) / 180;
  const firstLatitude = (first.latitude * Math.PI) / 180;
  const secondLatitude = (second.latitude * Math.PI) / 180;
  const value =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(firstLatitude) * Math.cos(secondLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return earthRadiusKm * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function nearestLocation(item: CaseMapItem, origin: MapCoordinate): NearbyResult | null {
  const preciseLocations = item.locations.filter((location) => location.precision === 'city');
  if (preciseLocations.length === 0) return null;
  return preciseLocations.reduce<NearbyResult | null>((nearest, location) => {
    const distanceKm = haversineDistance(origin, location);
    return !nearest || distanceKm < nearest.distanceKm ? { distanceKm, item, location } : nearest;
  }, null);
}

function resultPoints(results: NearbyResult[]): NearbyMapPoint[] {
  return results.flatMap(({ item }) =>
    item.locations
      .filter((location) => location.precision === 'city')
      .map((location) => ({
        approximate: location.approximate,
        caseId: item.id,
        label: location.label,
        latitude: location.latitude,
        longitude: location.longitude,
        precision: location.precision,
        reward: item.reward,
        title: item.title,
      }))
  );
}

function suggestedRadius(distanceKm: number) {
  return radiusOptions.find((radius) => radius >= distanceKm) ?? radiusOptions.at(-1)!;
}

export default function NearbyScreen() {
  const { language } = useLanguage();
  const copy = nearbyCopy[language] as NearbyCopy;
  const { width } = useWindowDimensions();
  const isWide = width >= 980;
  const [items, setItems] = useState<CaseMapItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [origin, setOrigin] = useState<MapSearchOrigin | null>(null);
  const [mapCenter, setMapCenter] = useState<MapCoordinate | null>(null);
  const [radiusKm, setRadiusKm] = useState<number>(100);
  const [locationState, setLocationState] = useState<'idle' | 'loading' | 'denied' | 'unavailable' | 'insecure'>('idle');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    fetchCaseMap(controller.signal)
      .then((response) => {
        setItems(response.items);
        setError(null);
      })
      .catch((requestError: Error) => {
        if (requestError.name !== 'AbortError') setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  const allResults = useMemo(() => {
    if (!origin) return [];
    return items
      .map((item) => nearestLocation(item, origin))
      .filter((result): result is NearbyResult => result !== null)
      .sort((left, right) => left.distanceKm - right.distanceKm);
  }, [items, origin]);
  const nearbyResults = useMemo(
    () => allResults.filter((result) => result.distanceKm <= radiusKm),
    [allResults, radiusKm]
  );
  const allPreciseResults = useMemo(() => {
    const neutralOrigin = { latitude: 44, longitude: -98 };
    return items
      .map((item) => nearestLocation(item, neutralOrigin))
      .filter((result): result is NearbyResult => result !== null);
  }, [items]);
  const preciseCaseCount = allPreciseResults.length;
  const points = useMemo(
    () => resultPoints(origin ? nearbyResults : allPreciseResults),
    [allPreciseResults, nearbyResults, origin]
  );
  const nearestOutside = allResults.find((result) => result.distanceKm > radiusKm) ?? null;
  const activeResults = selectedCaseId
    ? [...nearbyResults].sort((left, right) =>
        left.item.id === selectedCaseId ? -1 : right.item.id === selectedCaseId ? 1 : 0
      )
    : nearbyResults;

  function requestLocation() {
    if (typeof window === 'undefined' || !window.isSecureContext) {
      setLocationState('insecure');
      return;
    }
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setLocationState('unavailable');
      return;
    }
    setLocationState('loading');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin({
          accuracy: position.coords.accuracy,
          kind: 'device',
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
        setLocationState('idle');
        setSelectedCaseId(null);
      },
      (positionError) => {
        setLocationState(positionError.code === positionError.PERMISSION_DENIED ? 'denied' : 'unavailable');
      },
      { enableHighAccuracy: false, maximumAge: 300_000, timeout: 12_000 }
    );
  }

  function searchMapCenter() {
    if (!mapCenter) return;
    setOrigin({ ...mapCenter, kind: 'map' });
    setLocationState('idle');
    setSelectedCaseId(null);
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={[styles.header, isWide && styles.headerWide]} testID="nearby-header">
          <View style={styles.headerCopy}>
            <Link href="/" asChild>
              <Pressable accessibilityRole="link" style={styles.backLink}>
                <SymbolView name={{ ios: 'arrow.left', android: 'arrow_back', web: 'arrow_back' }} size={16} tintColor={themedForeground('#6C63FF')} />
                <Text style={styles.backLinkText}>{copy.backHome}</Text>
              </Pressable>
            </Link>
            <Text style={styles.title}>{copy.title}</Text>
            <Text style={styles.subtitle}>{copy.subtitle}</Text>
          </View>
          <View style={styles.headerActions}>
            <LanguageSelector />
            <ThemeToggle />
            <Link href="/cases" asChild>
              <Pressable accessibilityRole="link" style={styles.secondaryButton}>
                <Text style={styles.secondaryButtonText}>{copy.allCases}</Text>
              </Pressable>
            </Link>
          </View>
        </View>

        <View style={styles.controlSurface}>
          <View style={styles.controlTopRow}>
            <View style={styles.locationActions}>
              <Pressable
                accessibilityRole="button"
                disabled={locationState === 'loading'}
                onPress={requestLocation}
                style={({ pressed }) => [styles.primaryButton, pressed && styles.buttonPressed]}
              >
                {locationState === 'loading' ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : (
                  <SymbolView name={{ ios: 'location.fill', android: 'my_location', web: 'my_location' }} size={19} tintColor="#FFFFFF" />
                )}
                <Text style={styles.primaryButtonText}>
                  {locationState === 'loading' ? copy.locating : origin?.kind === 'device' ? copy.relocate : copy.locate}
                </Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                disabled={!mapCenter}
                onPress={searchMapCenter}
                style={({ pressed }) => [styles.mapSearchButton, !mapCenter && styles.buttonDisabled, pressed && styles.buttonPressed]}
              >
                <SymbolView name={{ ios: 'scope', android: 'center_focus_strong', web: 'center_focus_strong' }} size={18} tintColor={themedForeground('#5B4DFF')} />
                <Text style={styles.mapSearchButtonText}>{copy.searchHere}</Text>
              </Pressable>
            </View>
            <View style={styles.radiusBlock} testID="nearby-radius-block">
              <Text style={styles.controlLabel}>{copy.radius}</Text>
              <View style={styles.radiusOptions}>
                {radiusOptions.map((radius) => (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected: radiusKm === radius }}
                    key={radius}
                    onPress={() => setRadiusKm(radius)}
                    style={[styles.radiusChip, radiusKm === radius && styles.radiusChipActive]}
                  >
                    <Text style={[styles.radiusChipText, radiusKm === radius && styles.radiusChipTextActive]}>{radius} km</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          </View>
          <View style={styles.privacyRow}>
            <SymbolView name={{ ios: 'lock.shield', android: 'shield', web: 'shield' }} size={16} tintColor={themedForeground('#667085')} />
            <Text style={styles.privacyText}>{copy.privacy}</Text>
          </View>
          {locationState !== 'idle' && locationState !== 'loading' && (
            <View style={styles.inlineNotice}>
              <Text style={styles.inlineNoticeText}>
                {locationState === 'denied' ? copy.denied : locationState === 'insecure' ? copy.insecure : copy.unavailable}
              </Text>
            </View>
          )}
        </View>

        {error ? (
          <View style={styles.errorState}>
            <Text style={styles.errorTitle}>{copy.loadError}</Text>
            <Text style={styles.errorBody}>{error}</Text>
            <Pressable onPress={() => setReloadKey((value) => value + 1)} style={styles.retryButton}>
              <Text style={styles.retryButtonText}>{copy.retry}</Text>
            </Pressable>
          </View>
        ) : (
          <View style={[styles.workspace, isWide && styles.workspaceWide]} testID="nearby-workspace">
            <View
              style={[styles.mapCard, !isWide && styles.mapCardMobile]}
              testID="nearby-map-card"
            >
              {isLoading ? (
                <View style={styles.mapLoading}>
                  <ActivityIndicator color={themedForeground('#6C63FF')} size="large" />
                  <Text style={styles.loadingText}>{copy.loading}</Text>
                </View>
              ) : (
                <NearbyMap
                  labels={{
                    caseLocation: copy.caseLocation,
                    clusterCases: copy.clusterCases,
                    mapUnavailable: copy.mapUnavailable,
                    searchCenter: copy.searchCenter,
                    yourLocation: copy.yourLocation,
                  }}
                  onCenterChange={setMapCenter}
                  onSelectCase={setSelectedCaseId}
                  origin={origin}
                  points={points}
                  radiusKm={radiusKm}
                  selectedCaseId={selectedCaseId}
                />
              )}
              <View pointerEvents="none" style={styles.legend}>
                <View style={styles.legendRow}><View style={[styles.legendDot, styles.legendHigh]} /><Text style={styles.legendText}>$1M+</Text></View>
                <View style={styles.legendRow}><View style={[styles.legendDot, styles.legendMedium]} /><Text style={styles.legendText}>$25K+</Text></View>
                <View style={styles.legendRow}><View style={[styles.legendDot, styles.legendStandard]} /><Text style={styles.legendText}>{copy.caseLocation}</Text></View>
              </View>
            </View>

            <View
              style={[styles.resultsPanel, isWide && styles.resultsPanelWide]}
              testID="nearby-results-panel"
            >
              <View style={styles.resultsHeader}>
                <View>
                  <Text style={styles.resultsTitle}>{origin ? copy.nearbyResults : copy.beforeLocate}</Text>
                  {origin && <Text style={styles.originLabel}>{origin.kind === 'device' ? copy.deviceOrigin : copy.mapOrigin}</Text>}
                </View>
                {origin && <View style={styles.countBadge}><Text style={styles.countBadgeText}>{nearbyResults.length}</Text></View>}
              </View>

              {!origin ? (
                <View style={styles.onboardingCard}>
                  <SymbolView name={{ ios: 'map.fill', android: 'map', web: 'map' }} size={34} tintColor={themedForeground('#6C63FF')} />
                  <Text style={styles.onboardingTitle}>{copy.beforeLocate}</Text>
                  <Text style={styles.onboardingBody}>{copy.beforeLocateBody}</Text>
                  <Text style={styles.mappedCount}>{interpolate(copy.mappedCases, { count: preciseCaseCount })}</Text>
                </View>
              ) : activeResults.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Text style={styles.emptyTitle}>{copy.noResults}</Text>
                  {nearestOutside && (
                    <>
                      <Text style={styles.emptyBody}>{interpolate(copy.nearest, { distance: Math.round(nearestOutside.distanceKm) })}</Text>
                      <Pressable onPress={() => setRadiusKm(suggestedRadius(nearestOutside.distanceKm))} style={styles.expandButton}>
                        <Text style={styles.expandButtonText}>{interpolate(copy.expand, { radius: suggestedRadius(nearestOutside.distanceKm) })}</Text>
                      </Pressable>
                    </>
                  )}
                </View>
              ) : (
                <ScrollView
                  contentContainerStyle={styles.caseList}
                  nestedScrollEnabled
                  showsVerticalScrollIndicator={false}
                  style={styles.caseListScroll}
                >
                  {activeResults.slice(0, 50).map((result) => (
                    <MapCaseCard
                      copy={copy}
                      isSelected={selectedCaseId === result.item.id}
                      key={result.item.id}
                      onSelect={() => setSelectedCaseId(result.item.id)}
                      result={result}
                    />
                  ))}
                </ScrollView>
              )}
            </View>
          </View>
        )}

        <View style={styles.safetyNotice}>
          <View style={styles.safetyIcon}>
            <SymbolView name={{ ios: 'exclamationmark.triangle.fill', android: 'warning', web: 'warning' }} size={22} tintColor={themedForeground('#B54708')} />
          </View>
          <View style={styles.safetyCopy}>
            <Text style={styles.safetyTitle}>{copy.safetyTitle}</Text>
            <Text style={styles.safetyBody}>{copy.safetyBody}</Text>
            <Text style={styles.dataNote}>{copy.mapDataNote} {copy.mapAttribution}</Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function MapCaseCard({
  copy,
  isSelected,
  onSelect,
  result,
}: {
  copy: NearbyCopy;
  isSelected: boolean;
  onSelect: () => void;
  result: NearbyResult;
}) {
  const { item, location, distanceKm } = result;
  const distanceLabel = distanceKm < 1 ? copy.underOneKm : interpolate(copy.distance, { distance: Math.round(distanceKm) });
  const rewardLabel = item.reward === null
    ? copy.notPublished
    : formatRewardAmount(item.reward, item.rewardCurrency, item.country);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: isSelected }}
      onPress={onSelect}
      style={[styles.caseCard, isSelected && styles.caseCardSelected]}
    >
      {item.imageUrl ? (
        <Image contentFit="cover" source={{ uri: resolveApiAssetUrl(item.imageUrl) }} style={styles.caseImage} />
      ) : (
        <View style={styles.caseImageFallback}>
          <SymbolView name={{ ios: 'photo', android: 'image', web: 'image' }} size={22} tintColor={themedForeground('#98A2B3')} />
        </View>
      )}
      <View style={styles.caseCardBody}>
        <View style={styles.caseCardTopLine}>
          <Text numberOfLines={2} style={styles.caseTitle}>{item.title}</Text>
          <Text style={styles.distanceText}>{distanceLabel}</Text>
        </View>
        <Text numberOfLines={1} style={styles.agencyText}>{item.agency}</Text>
        <Text style={styles.rewardText}>{rewardLabel}</Text>
        <Text numberOfLines={2} style={styles.locationText}>{interpolate(copy.locationBasis, { location: location.label })}</Text>
        <Link href={{ pathname: '/cases/detail', params: { id: item.id } }} asChild>
          <Pressable accessibilityRole="link" style={styles.viewCaseLink}>
            <Text style={styles.viewCaseLinkText}>{copy.viewCase}</Text>
            <SymbolView name={{ ios: 'arrow.right', android: 'arrow_forward', web: 'arrow_forward' }} size={15} tintColor={themedForeground('#5B4DFF')} />
          </Pressable>
        </Link>
      </View>
    </Pressable>
  );
}

const styles = createThemedStyles({
  safeArea: { backgroundColor: '#F6F8FC', flex: 1 },
  content: { alignSelf: 'center', maxWidth: 1480, paddingBottom: 48, paddingHorizontal: 20, paddingTop: 28, width: '100%' },
  header: { gap: 20, marginBottom: 24 },
  headerWide: { alignItems: 'flex-start', flexDirection: 'row', justifyContent: 'space-between' },
  headerCopy: { flexShrink: 1, maxWidth: 820 },
  backLink: { alignItems: 'center', alignSelf: 'flex-start', flexDirection: 'row', gap: 7, marginBottom: 18 },
  backLinkText: { color: '#6C63FF', fontSize: 14, fontWeight: '800' },
  title: { color: '#101828', fontSize: 38, fontWeight: '900', letterSpacing: -1.1, lineHeight: 44 },
  subtitle: { color: '#536179', fontSize: 16, lineHeight: 25, marginTop: 9, maxWidth: 760 },
  headerActions: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  secondaryButton: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#DDE4F0', borderRadius: 13, borderWidth: 1, height: 44, justifyContent: 'center', paddingHorizontal: 17 },
  secondaryButtonText: { color: '#344054', fontSize: 14, fontWeight: '800' },
  controlSurface: { backgroundColor: '#FFFFFF', borderColor: '#DDE4F0', borderRadius: 20, borderWidth: 1, gap: 15, marginBottom: 18, padding: 18 },
  controlTopRow: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 18, justifyContent: 'space-between' },
  locationActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  primaryButton: { alignItems: 'center', backgroundColor: '#5B4DFF', borderRadius: 13, flexDirection: 'row', gap: 8, justifyContent: 'center', minHeight: 46, paddingHorizontal: 17 },
  primaryButtonText: { color: '#FFFFFF', fontSize: 14, fontWeight: '900' },
  mapSearchButton: { alignItems: 'center', backgroundColor: '#F3F4FF', borderColor: '#D9D6FE', borderRadius: 13, borderWidth: 1, flexDirection: 'row', gap: 8, justifyContent: 'center', minHeight: 46, paddingHorizontal: 16 },
  mapSearchButtonText: { color: '#5B4DFF', fontSize: 14, fontWeight: '800' },
  buttonPressed: { opacity: 0.78, transform: [{ scale: 0.985 }] },
  buttonDisabled: { opacity: 0.5 },
  radiusBlock: { flexBasis: '100%', gap: 8, minWidth: 0, width: '100%' },
  controlLabel: { color: '#667085', fontSize: 12, fontWeight: '800', textTransform: 'uppercase' },
  radiusOptions: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  radiusChip: { backgroundColor: '#F8FAFD', borderColor: '#DDE4F0', borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 8 },
  radiusChipActive: { backgroundColor: '#5B4DFF', borderColor: '#5B4DFF' },
  radiusChipText: { color: '#475467', fontSize: 12, fontWeight: '800' },
  radiusChipTextActive: { color: '#FFFFFF' },
  privacyRow: { alignItems: 'center', flexDirection: 'row', gap: 7 },
  privacyText: { color: '#667085', flexShrink: 1, fontSize: 12, lineHeight: 18 },
  inlineNotice: { backgroundColor: '#FFF9ED', borderColor: '#FEDF89', borderRadius: 12, borderWidth: 1, paddingHorizontal: 13, paddingVertical: 11 },
  inlineNoticeText: { color: '#9A3412', fontSize: 13, lineHeight: 19 },
  workspace: { gap: 16 },
  workspaceWide: { alignItems: 'stretch', flexDirection: 'row' },
  mapCard: { backgroundColor: '#FFFFFF', borderColor: '#DDE4F0', borderRadius: 22, borderWidth: 1, flex: 1, height: 660, minHeight: 520, overflow: 'hidden', position: 'relative' },
  mapCardMobile: { height: 520 },
  mapLoading: { alignItems: 'center', flex: 1, gap: 12, justifyContent: 'center' },
  loadingText: { color: '#667085', fontSize: 14, fontWeight: '700' },
  legend: { backgroundColor: 'rgba(255,255,255,0.82)', borderColor: '#DDE4F0', borderRadius: 12, borderWidth: 1, bottom: 12, gap: 7, left: 12, paddingHorizontal: 11, paddingVertical: 9, position: 'absolute' },
  legendRow: { alignItems: 'center', flexDirection: 'row', gap: 7 },
  legendDot: { borderColor: '#FFFFFF', borderRadius: 99, borderWidth: 2, height: 12, width: 12 },
  legendHigh: { backgroundColor: '#D92D20' }, legendMedium: { backgroundColor: '#F79009' }, legendStandard: { backgroundColor: '#6C63FF' },
  legendText: { color: '#344054', fontSize: 11, fontWeight: '800' },
  resultsPanel: { backgroundColor: '#FFFFFF', borderColor: '#DDE4F0', borderRadius: 22, borderWidth: 1, maxHeight: 660, overflow: 'hidden', padding: 16 },
  resultsPanelWide: { flexBasis: 390, width: 390 },
  resultsHeader: { alignItems: 'center', borderBottomColor: '#E5EAF3', borderBottomWidth: 1, flexDirection: 'row', justifyContent: 'space-between', paddingBottom: 14 },
  resultsTitle: { color: '#101828', fontSize: 20, fontWeight: '900' },
  originLabel: { color: '#667085', fontSize: 12, marginTop: 4 },
  countBadge: { alignItems: 'center', backgroundColor: '#F0EFFF', borderRadius: 999, height: 32, justifyContent: 'center', minWidth: 32, paddingHorizontal: 9 },
  countBadgeText: { color: '#5B4DFF', fontSize: 13, fontWeight: '900' },
  onboardingCard: { alignItems: 'center', gap: 11, paddingHorizontal: 14, paddingVertical: 42 },
  onboardingTitle: { color: '#101828', fontSize: 18, fontWeight: '900', textAlign: 'center' },
  onboardingBody: { color: '#667085', fontSize: 14, lineHeight: 22, maxWidth: 310, textAlign: 'center' },
  mappedCount: { color: '#5B4DFF', fontSize: 12, fontWeight: '800', marginTop: 4, textAlign: 'center' },
  caseListScroll: { maxHeight: 575 },
  caseList: { gap: 10, paddingBottom: 4, paddingTop: 13 },
  caseCard: { backgroundColor: '#F8FAFD', borderColor: '#E1E6EF', borderRadius: 15, borderWidth: 1, flexDirection: 'row', gap: 12, padding: 10 },
  caseCardSelected: { backgroundColor: '#F3F4FF', borderColor: '#AFA9FF', borderWidth: 2 },
  caseImage: { backgroundColor: '#E8EEF7', borderRadius: 11, height: 94, width: 78 },
  caseImageFallback: { alignItems: 'center', backgroundColor: '#E8EEF7', borderRadius: 11, height: 94, justifyContent: 'center', width: 78 },
  caseCardBody: { flex: 1, minWidth: 0 },
  caseCardTopLine: { alignItems: 'flex-start', flexDirection: 'row', gap: 8, justifyContent: 'space-between' },
  caseTitle: { color: '#101828', flex: 1, fontSize: 14, fontWeight: '900', lineHeight: 18 },
  distanceText: { color: '#5B4DFF', fontSize: 10, fontWeight: '900', maxWidth: 92, textAlign: 'right' },
  agencyText: { color: '#667085', fontSize: 11, marginTop: 3 },
  rewardText: { color: '#B54708', fontSize: 13, fontWeight: '900', marginTop: 6 },
  locationText: { color: '#475467', fontSize: 11, lineHeight: 16, marginTop: 3 },
  viewCaseLink: { alignItems: 'center', alignSelf: 'flex-start', flexDirection: 'row', gap: 5, marginTop: 8 },
  viewCaseLinkText: { color: '#5B4DFF', fontSize: 12, fontWeight: '900' },
  emptyCard: { alignItems: 'center', gap: 11, paddingHorizontal: 16, paddingVertical: 42 },
  emptyTitle: { color: '#101828', fontSize: 17, fontWeight: '900', textAlign: 'center' },
  emptyBody: { color: '#667085', fontSize: 14, lineHeight: 21, textAlign: 'center' },
  expandButton: { backgroundColor: '#F0EFFF', borderRadius: 11, marginTop: 4, paddingHorizontal: 14, paddingVertical: 10 },
  expandButtonText: { color: '#5B4DFF', fontSize: 13, fontWeight: '900' },
  safetyNotice: { alignItems: 'flex-start', backgroundColor: '#FFF9ED', borderColor: '#FEDF89', borderRadius: 18, borderWidth: 1, flexDirection: 'row', gap: 12, marginTop: 18, padding: 16 },
  safetyIcon: { alignItems: 'center', backgroundColor: '#FFF0CC', borderRadius: 10, height: 40, justifyContent: 'center', width: 40 },
  safetyCopy: { flex: 1 }, safetyTitle: { color: '#9A3412', fontSize: 14, fontWeight: '900' },
  safetyBody: { color: '#7A4A14', fontSize: 13, lineHeight: 20, marginTop: 4 },
  dataNote: { color: '#8A5A22', fontSize: 11, lineHeight: 17, marginTop: 7 },
  errorState: { alignItems: 'center', backgroundColor: '#FFFFFF', borderColor: '#DDE4F0', borderRadius: 20, borderWidth: 1, gap: 9, padding: 40 },
  errorTitle: { color: '#101828', fontSize: 18, fontWeight: '900' }, errorBody: { color: '#667085', fontSize: 13 },
  retryButton: { backgroundColor: '#5B4DFF', borderRadius: 11, marginTop: 5, paddingHorizontal: 15, paddingVertical: 10 }, retryButtonText: { color: '#FFFFFF', fontSize: 13, fontWeight: '900' },
});
