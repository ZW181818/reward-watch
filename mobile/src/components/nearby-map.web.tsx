import 'maplibre-gl/dist/maplibre-gl.css';

import { useEffect, useRef } from 'react';
import type { StyleSpecification } from 'maplibre-gl';

import { useAppTheme } from '@/lib/app-theme';

import type {
  MapSearchOrigin,
  NearbyMapPoint,
  NearbyMapProps,
} from './nearby-map-types';

const LIGHT_STYLE = 'https://tiles.openfreemap.org/styles/positron';
const DARK_STYLE = 'https://tiles.openfreemap.org/styles/dark';

function fallbackStyle(mode: 'light' | 'dark'): StyleSpecification {
  return {
    version: 8,
    sources: {
      openStreetMap: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© OpenStreetMap contributors',
      },
    },
    layers: [
      {
        id: 'fallback-background',
        type: 'background',
        paint: { 'background-color': mode === 'dark' ? '#111827' : '#E8EEF7' },
      },
      {
        id: 'fallback-map',
        type: 'raster',
        source: 'openStreetMap',
        paint:
          mode === 'dark'
            ? {
                'raster-brightness-max': 0.58,
                'raster-contrast': 0.18,
                'raster-saturation': -0.42,
              }
            : {},
      },
    ],
  };
}

type MapInstance = import('maplibre-gl').Map;
type MapMarker = import('maplibre-gl').Marker;

function fitAroundOrigin(map: MapInstance, origin: MapSearchOrigin, radiusKm: number) {
  const latitudeDelta = radiusKm / 111.32;
  const longitudeDelta = radiusKm / Math.max(
    20,
    111.32 * Math.cos((origin.latitude * Math.PI) / 180)
  );
  map.fitBounds(
    [
      [origin.longitude - longitudeDelta, origin.latitude - latitudeDelta],
      [origin.longitude + longitudeDelta, origin.latitude + latitudeDelta],
    ],
    { duration: 650, maxZoom: 12, padding: 54 }
  );
}

export default function NearbyMap({
  labels,
  onCenterChange,
  onSelectCase,
  origin,
  points,
  radiusKm,
  selectedCaseId,
}: NearbyMapProps) {
  const { mode } = useAppTheme();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const pointsRef = useRef(points);
  const originRef = useRef(origin);
  const radiusRef = useRef(radiusKm);
  const onCenterChangeRef = useRef(onCenterChange);
  const onSelectCaseRef = useRef(onSelectCase);
  const labelsRef = useRef(labels);
  const modeRef = useRef(mode);
  const hasInitialFitRef = useRef(false);
  const fallbackActiveRef = useRef(false);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const caseMarkersRef = useRef<MapMarker[]>([]);
  const originMarkerRef = useRef<MapMarker | null>(null);
  const redrawCaseMarkersRef = useRef<() => void>(() => {});
  const redrawOriginMarkerRef = useRef<() => void>(() => {});

  useEffect(() => {
    pointsRef.current = points;
    originRef.current = origin;
    radiusRef.current = radiusKm;
    onCenterChangeRef.current = onCenterChange;
    onSelectCaseRef.current = onSelectCase;
    labelsRef.current = labels;
    modeRef.current = mode;
  }, [labels, mode, onCenterChange, onSelectCase, origin, points, radiusKm]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;

    import('maplibre-gl').then((maplibre) => {
      if (cancelled || !containerRef.current) return;
      const map = new maplibre.Map({
        center: [-98, 44],
        container: containerRef.current,
        maxZoom: 16,
        minZoom: 2,
        style: mode === 'dark' ? DARK_STYLE : LIGHT_STYLE,
        zoom: 2.7,
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');

      const clearCaseMarkers = () => {
        caseMarkersRef.current.forEach((marker) => marker.remove());
        caseMarkersRef.current = [];
      };

      const redrawCaseMarkers = () => {
        clearCaseMarkers();
        const canvas = map.getCanvas();
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        if (!width || !height) return;

        const groups = new Map<
          string,
          { latitude: number; longitude: number; points: NearbyMapPoint[] }
        >();
        const cellSize = map.getZoom() >= 9 ? 38 : 54;

        pointsRef.current.forEach((point) => {
          const pixel = map.project([point.longitude, point.latitude]);
          if (
            pixel.x < -cellSize ||
            pixel.y < -cellSize ||
            pixel.x > width + cellSize ||
            pixel.y > height + cellSize
          ) {
            return;
          }
          const key = `${Math.floor(pixel.x / cellSize)}:${Math.floor(pixel.y / cellSize)}`;
          const group = groups.get(key);
          if (group) {
            group.latitude += point.latitude;
            group.longitude += point.longitude;
            group.points.push(point);
          } else {
            groups.set(key, {
              latitude: point.latitude,
              longitude: point.longitude,
              points: [point],
            });
          }
        });

        groups.forEach((group) => {
          const representative = group.points[0];
          const count = group.points.length;
          const element = document.createElement('button');
          element.type = 'button';
          if (count > 1) {
            element.className = 'rw-map-cluster';
            element.textContent = count > 99 ? '99+' : String(count);
            element.setAttribute('aria-label', `${count} ${labelsRef.current.clusterCases}`);
            element.addEventListener('click', (event) => {
              event.stopPropagation();
              map.easeTo({
                center: [group.longitude / count, group.latitude / count],
                duration: 450,
                zoom: Math.min(14, map.getZoom() + 2),
              });
            });
          } else {
            const rewardTier =
              representative.reward === null
                ? 'unknown'
                : representative.reward >= 1_000_000
                  ? 'high'
                  : representative.reward >= 25_000
                    ? 'medium'
                    : 'standard';
            element.className = `rw-map-pin rw-map-pin-${rewardTier}`;
            element.setAttribute(
              'aria-label',
              `${representative.title}. ${representative.label}`
            );
            element.addEventListener('click', (event) => {
              event.stopPropagation();
              onSelectCaseRef.current(representative.caseId);
            });
          }

          const marker = new maplibre.Marker({ element })
            .setLngLat([group.longitude / count, group.latitude / count])
            .addTo(map);
          caseMarkersRef.current.push(marker);
        });

        if (containerRef.current) {
          containerRef.current.dataset.markerCount = String(caseMarkersRef.current.length);
        }
      };

      const redrawOriginMarker = () => {
        originMarkerRef.current?.remove();
        originMarkerRef.current = null;
        const currentOrigin = originRef.current;
        if (!currentOrigin) return;

        const root = document.createElement('div');
        root.className = `rw-map-origin rw-map-origin-${currentOrigin.kind}`;
        root.setAttribute(
          'aria-label',
          currentOrigin.kind === 'device'
            ? labelsRef.current.yourLocation
            : labelsRef.current.caseLocation
        );
        const radius = document.createElement('div');
        radius.className = 'rw-map-origin-radius';
        const dot = document.createElement('div');
        dot.className = 'rw-map-origin-dot';
        root.append(radius, dot);

        const longitudeDelta = radiusRef.current / Math.max(
          20,
          111.32 * Math.cos((currentOrigin.latitude * Math.PI) / 180)
        );
        const centerPixel = map.project([currentOrigin.longitude, currentOrigin.latitude]);
        const edgePixel = map.project([
          currentOrigin.longitude + longitudeDelta,
          currentOrigin.latitude,
        ]);
        const diameter = Math.min(
          2400,
          Math.max(18, Math.abs(edgePixel.x - centerPixel.x) * 2)
        );
        radius.style.height = `${diameter}px`;
        radius.style.width = `${diameter}px`;

        originMarkerRef.current = new maplibre.Marker({ element: root })
          .setLngLat([currentOrigin.longitude, currentOrigin.latitude])
          .addTo(map);
      };

      redrawCaseMarkersRef.current = redrawCaseMarkers;
      redrawOriginMarkerRef.current = redrawOriginMarker;

      const activateFallback = () => {
        if (fallbackActiveRef.current) return;
        fallbackActiveRef.current = true;
        if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
        fallbackTimerRef.current = null;
        map.setStyle(fallbackStyle(modeRef.current));
      };

      const scheduleFallbackCheck = () => {
        if (fallbackActiveRef.current) return;
        if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
        fallbackTimerRef.current = setTimeout(activateFallback, 4500);
      };

      const installMapContent = () => {
        if (!hasInitialFitRef.current && pointsRef.current.length > 0 && !originRef.current) {
          const bounds = new maplibre.LngLatBounds();
          pointsRef.current.forEach((point) => bounds.extend([point.longitude, point.latitude]));
          map.fitBounds(bounds, { duration: 0, maxZoom: 5, padding: 48 });
          hasInitialFitRef.current = true;
        }
        redrawCaseMarkers();
        redrawOriginMarker();
      };

      map.on('style.load', () => {
        installMapContent();
        scheduleFallbackCheck();
      });
      map.on('sourcedata', (event) => {
        if (
          !fallbackActiveRef.current &&
          event.sourceDataType === 'content' &&
          'tile' in event &&
          Boolean(event.tile) &&
          !['nearby-cases', 'search-origin', 'search-radius'].includes(event.sourceId)
        ) {
          if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
          fallbackTimerRef.current = null;
        }
      });
      map.on('moveend', () => {
        redrawCaseMarkers();
        redrawOriginMarker();
        const center = map.getCenter();
        onCenterChangeRef.current({ latitude: center.lat, longitude: center.lng });
      });
      map.on('error', (event) => {
        const message = event.error instanceof Error ? event.error.message : String(event.error);
        if (message.includes('openfreemap') || message.includes('ERR_BLOCKED_BY_CLIENT')) {
          activateFallback();
        }
        if (process.env.NODE_ENV !== 'production') {
          console.warn(labelsRef.current.mapUnavailable, event.error);
        }
      });

      resizeObserver = new ResizeObserver(() => {
        map.resize();
        redrawCaseMarkers();
        redrawOriginMarker();
      });
      resizeObserver.observe(containerRef.current);
    });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
      caseMarkersRef.current.forEach((marker) => marker.remove());
      caseMarkersRef.current = [];
      originMarkerRef.current?.remove();
      originMarkerRef.current = null;
      redrawCaseMarkersRef.current = () => {};
      redrawOriginMarkerRef.current = () => {};
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // Map creation is intentionally one-time; live values are read from refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    redrawCaseMarkersRef.current();
  }, [points]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    redrawOriginMarkerRef.current();
    if (origin) fitAroundOrigin(map, origin, radiusKm);
  }, [origin, radiusKm]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const styleUrl = mode === 'dark' ? DARK_STYLE : LIGHT_STYLE;
    map.setStyle(fallbackActiveRef.current ? fallbackStyle(mode) : styleUrl);
  }, [mode]);

  useEffect(() => {
    if (!selectedCaseId || !mapRef.current) return;
    const point = points.find((item) => item.caseId === selectedCaseId);
    if (point) {
      mapRef.current.easeTo({ center: [point.longitude, point.latitude], duration: 450 });
    }
  }, [points, selectedCaseId]);

  return (
    <div className="rw-nearby-map-shell">
      <div
        aria-label={origin?.kind === 'device' ? labels.yourLocation : labels.caseLocation}
        className="rw-nearby-map"
        ref={containerRef}
      />
    </div>
  );
}
