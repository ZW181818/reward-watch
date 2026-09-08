import 'maplibre-gl/dist/maplibre-gl.css';

import { useEffect, useRef } from 'react';
import type { StyleSpecification } from 'maplibre-gl';

import { useAppTheme } from '@/lib/app-theme';

import type { AdminLocationMapProps } from './admin-location-map-types';

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

export default function AdminLocationMap({
  coordinate,
  onCoordinateChange,
}: AdminLocationMapProps) {
  const { mode } = useAppTheme();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const markerRef = useRef<MapMarker | null>(null);
  const coordinateRef = useRef(coordinate);
  const onCoordinateChangeRef = useRef(onCoordinateChange);
  const modeRef = useRef(mode);
  const fallbackActiveRef = useRef(false);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const renderMarkerRef = useRef<() => void>(() => {});

  useEffect(() => {
    coordinateRef.current = coordinate;
    onCoordinateChangeRef.current = onCoordinateChange;
  }, [coordinate, onCoordinateChange]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;

    import('maplibre-gl').then((maplibre) => {
      if (cancelled || !containerRef.current) return;
      const initial = coordinateRef.current;
      const map = new maplibre.Map({
        center: initial ? [initial.longitude, initial.latitude] : [-98, 44],
        container: containerRef.current,
        maxZoom: 17,
        minZoom: 2,
        style: modeRef.current === 'dark' ? DARK_STYLE : LIGHT_STYLE,
        zoom: initial ? 10 : 2.7,
      });
      mapRef.current = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');

      const renderMarker = () => {
        markerRef.current?.remove();
        markerRef.current = null;
        const current = coordinateRef.current;
        if (!current) return;
        const element = document.createElement('div');
        element.className = 'rw-admin-location-pin';
        element.setAttribute('aria-label', 'Selected map location');
        const marker = new maplibre.Marker({ draggable: true, element })
          .setLngLat([current.longitude, current.latitude])
          .addTo(map);
        marker.on('dragend', () => {
          const next = marker.getLngLat();
          onCoordinateChangeRef.current({ latitude: next.lat, longitude: next.lng });
        });
        markerRef.current = marker;
      };
      renderMarkerRef.current = renderMarker;

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

      map.on('style.load', () => {
        renderMarker();
        scheduleFallbackCheck();
      });
      map.on('sourcedata', (event) => {
        if (
          !fallbackActiveRef.current &&
          event.sourceDataType === 'content' &&
          'tile' in event &&
          Boolean(event.tile)
        ) {
          if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
          fallbackTimerRef.current = null;
        }
      });
      map.on('click', (event) => {
        onCoordinateChangeRef.current({
          latitude: event.lngLat.lat,
          longitude: event.lngLat.lng,
        });
      });
      map.on('error', (event) => {
        const message = event.error instanceof Error ? event.error.message : String(event.error);
        if (message.includes('openfreemap') || message.includes('ERR_BLOCKED_BY_CLIENT')) {
          activateFallback();
        }
      });

      resizeObserver = new ResizeObserver(() => map.resize());
      resizeObserver.observe(containerRef.current);
    });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
      markerRef.current?.remove();
      markerRef.current = null;
      renderMarkerRef.current = () => {};
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    renderMarkerRef.current();
    if (map && coordinate) {
      map.easeTo({
        center: [coordinate.longitude, coordinate.latitude],
        duration: 300,
        zoom: Math.max(7, map.getZoom()),
      });
    }
  }, [coordinate]);

  useEffect(() => {
    modeRef.current = mode;
    const map = mapRef.current;
    if (!map) return;
    map.setStyle(
      fallbackActiveRef.current
        ? fallbackStyle(mode)
        : mode === 'dark'
          ? DARK_STYLE
          : LIGHT_STYLE
    );
  }, [mode]);

  return (
    <div className="rw-admin-location-map-shell">
      <div
        aria-label="Click the map or drag the pin to set the case location"
        className="rw-admin-location-map"
        ref={containerRef}
      />
    </div>
  );
}
