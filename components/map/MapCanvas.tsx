'use client';

import maplibregl, { Map as MLMap, Popup } from 'maplibre-gl';
import { useEffect, useRef, useState } from 'react';
import { DISTRICTS, KERALA_CENTER, REGION_BOUNDS } from '@/lib/districts';
import { fetchDistrictBoundaries } from '@/lib/geo';
import { RIVER_GAUGES, SHELTERS } from '@/lib/sampleData';
import { SEVERITY_COLORS } from '@/lib/types';
import type { HazardAlert, Quake, RainPoint, RiskScore } from '@/lib/types';
import { useAppStore } from '@/store/useAppStore';

/**
 * MapCanvas — owns the MapLibre instance and orchestrates every data layer.
 *
 * Boot strategy (bulletproof):
 *   1. The map constructs IMMEDIATELY with an inline style — no network fetch
 *      can block or break first paint.
 *   2. The polished dark vector basemap (CARTO Dark Matter) is fetched in the
 *      background and swapped in via setStyle() when ready.
 *   3. Every `style.load` event re-attaches all overlay sources/layers and
 *      bumps an epoch counter, which re-runs the data effects — so overlays
 *      survive any style swap (dark ↔ satellite ↔ fallback).
 *
 * Data flows INTO the map through effects (setData/feature-state); user intent
 * flows OUT through the zustand store. The WebGL canvas never re-renders.
 */

const DARK_STYLE_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

/** Inline boot style — dark-tinted OSM raster. Zero style-fetch dependency. */
const BOOT_DARK_STYLE: any = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#0a0e1a' } },
    {
      id: 'osm',
      type: 'raster',
      source: 'osm',
      paint: { 'raster-saturation': -0.85, 'raster-brightness-max': 0.6, 'raster-contrast': 0.1 },
    },
  ],
};

/** Photoreal satellite — Esri World Imagery (the "Google Earth view"). */
const SATELLITE_STYLE: any = {
  version: 8,
  sources: {
    esri: {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      maxzoom: 18,
      attribution: 'Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community',
    },
  },
  layers: [{ id: 'esri', type: 'raster', source: 'esri' }],
};

/**
 * Final paint values per map layer — single source of truth shared by
 * ensureOverlays (initial state) and the pop-in animator (tween targets).
 * Expressions are multiplied by a 0→1 factor during the animation, which is
 * valid MapLibre expression algebra: ['*', f, <interpolate…>].
 */
const PAINT_TARGETS: Record<string, { opacity: Record<string, any>; radius?: Record<string, any> }> = {
  'districts-fill': {
    opacity: {
      'fill-opacity': [
        'interpolate', ['linear'], ['coalesce', ['feature-state', 'score'], 0],
        0, 0.12, 40, 0.3, 70, 0.48, 100, 0.58,
      ],
    },
  },
  'districts-line': { opacity: { 'line-opacity': 1 } },
  'risk-centroid-circles': {
    opacity: { 'circle-opacity': 0.55, 'circle-stroke-opacity': 0.9 },
    radius: { 'circle-radius': ['interpolate', ['linear'], ['get', 'score'], 0, 8, 100, 30] },
  },
  'rainfall-circles': {
    opacity: {
      'circle-opacity': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0, 0.5, 0.25, 5, 0.5, 15, 0.75],
    },
    radius: { 'circle-radius': ['interpolate', ['linear'], ['get', 'intensity'], 0, 4, 2, 14, 8, 30, 20, 52] },
  },
  'alert-halo': { opacity: { 'circle-opacity': 0.18 }, radius: { 'circle-radius': 22 } },
  'alert-dots': { opacity: { 'circle-opacity': 1, 'circle-stroke-opacity': 1 }, radius: { 'circle-radius': 7 } },
  'quake-circles': {
    opacity: { 'circle-opacity': 0.75, 'circle-stroke-opacity': 1 },
    radius: { 'circle-radius': ['interpolate', ['linear'], ['get', 'mag'], 2, 4, 5, 12, 7, 24] },
  },
  'gauge-circles': {
    opacity: { 'circle-opacity': 1, 'circle-stroke-opacity': 0.7 },
    radius: { 'circle-radius': 6 },
  },
  'infra-circles': {
    opacity: { 'circle-opacity': 1, 'circle-stroke-opacity': 1 },
    radius: { 'circle-radius': 5.5 },
  },
  'gibs-satellite': { opacity: { 'raster-opacity': 0.85 } },
};

/** Which map layers belong to each toggleable UI layer. */
const UI_LAYER_MAP: Record<string, string[]> = {
  risk: ['districts-fill', 'districts-line', 'risk-centroid-circles'],
  rainfall: ['rainfall-circles'],
  alerts: ['alert-halo', 'alert-dots'],
  quakes: ['quake-circles'],
  gauges: ['gauge-circles'],
  infrastructure: ['infra-circles'],
  satellite: ['gibs-satellite'],
};

const scale = (f: number, v: any) => (typeof v === 'number' ? v * f : (['*', f, v] as any));
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
/** Slight overshoot — makes markers "pop" as they land. */
const easeOutBack = (t: number) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2);

/** Tween a map layer's opacity (ease-out) and radius (overshoot pop) from 0 → target. */
function animateLayerIn(map: MLMap, layerId: string, duration = 650): () => void {
  const target = PAINT_TARGETS[layerId];
  if (!target || !map.getLayer(layerId)) return () => {};
  let raf = 0;
  const t0 = performance.now();

  const frame = (now: number) => {
    if (!map.getLayer(layerId)) return;
    const t = Math.min(1, (now - t0) / duration);
    for (const [prop, v] of Object.entries(target.opacity)) {
      map.setPaintProperty(layerId, prop as any, scale(easeOutCubic(t), v));
    }
    if (target.radius) {
      for (const [prop, v] of Object.entries(target.radius)) {
        map.setPaintProperty(layerId, prop as any, scale(Math.max(0.001, easeOutBack(t)), v));
      }
    }
    if (t < 1) raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);

  return () => {
    cancelAnimationFrame(raf);
    // Snap to exact final values on cancel/complete.
    if (!map.getLayer(layerId)) return;
    for (const [prop, v] of Object.entries(target.opacity)) map.setPaintProperty(layerId, prop as any, v);
    if (target.radius) for (const [prop, v] of Object.entries(target.radius)) map.setPaintProperty(layerId, prop as any, v);
  };
}

interface Props {
  risk: RiskScore[] | null;
  rain: RainPoint[] | null;
  alerts: HazardAlert[] | null;
  quakes: Quake[] | null;
}

export default function MapCanvas({ risk, rain, alerts, quakes }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const darkStyleRef = useRef<any>(BOOT_DARK_STYLE);
  /** Increments on every style.load — overlay layers exist iff epoch > 0. */
  const [epoch, setEpoch] = useState(0);
  const [initError, setInitError] = useState<string | null>(null);
  const [boundaries, setBoundaries] = useState<GeoJSON.FeatureCollection | null>(null);

  const activeLayers = useAppStore((s) => s.activeLayers);
  const basemapMode = useAppStore((s) => s.basemapMode);
  const timelineHour = useAppStore((s) => s.timelineHour);
  const selectDistrict = useAppStore((s) => s.selectDistrict);
  const selectedDistrictId = useAppStore((s) => s.selectedDistrictId);

  const ready = epoch > 0;

  /* ---------------------------------- init --------------------------------- */
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let map: MLMap;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: BOOT_DARK_STYLE,
        center: KERALA_CENTER,
        zoom: 6.4,
        minZoom: 4,
        maxZoom: 17,
        attributionControl: { compact: true } as any,
      });
    } catch (err) {
      console.error('[vegvisir] map init failed:', err);
      setInitError(String(err));
      return;
    }
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.on('error', (e: any) => console.warn('[vegvisir] map warning:', e?.error?.message ?? e));

    // Re-attach overlays after EVERY style load (boot, upgrade, mode switch).
    // ensureOverlays is idempotent, so calling it from multiple paths is safe.
    const attach = () => {
      try {
        ensureOverlays(map);
        setEpoch((n) => n + 1);
      } catch (err) {
        console.error('[vegvisir] overlay attach failed:', err);
      }
    };
    map.on('style.load', attach);
    map.once('load', () => {
      attach(); // inline boot styles can finish before listeners register
      map.fitBounds(REGION_BOUNDS as any, { padding: 60, duration: 1200 });
    });

    // Background upgrade: swap the boot raster for the polished vector style.
    // CRITICAL: diff:false forces a full style reload so 'style.load' fires —
    // the default diff mode silently strips overlay layers without any event.
    fetch(DARK_STYLE_URL, { signal: AbortSignal.timeout(8000) })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`style ${r.status}`))))
      .then((styleJson) => {
        darkStyleRef.current = styleJson;
        if (mapRef.current && useAppStore.getState().basemapMode === 'dark') {
          mapRef.current.setStyle(styleJson, { diff: false });
        }
      })
      .catch((err) => console.warn('[vegvisir] dark style upgrade skipped:', err?.message));

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  /* ----------------------------- basemap mode ------------------------------ */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setStyle(basemapMode === 'satellite' ? SATELLITE_STYLE : darkStyleRef.current, {
      diff: false, // full reload → 'style.load' fires → overlays re-attach
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemapMode]);

  /* --------------------------- district boundaries -------------------------- */
  useEffect(() => {
    fetchDistrictBoundaries().then((fc) => fc && setBoundaries(fc as any));
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !boundaries) return;
    (map.getSource('districts') as maplibregl.GeoJSONSource)?.setData(boundaries as any);
  }, [boundaries, ready, epoch]);

  /* ------------------------------- risk layer ------------------------------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !risk) return;

    const byId = new Map(risk.map((r) => [r.districtId, r]));

    if (boundaries && map.getSource('districts')) {
      for (const f of (boundaries as any).features) {
        const r = byId.get(f.properties.districtId);
        map.setFeatureState(
          { source: 'districts', id: f.properties.districtId } as any,
          { score: r?.score ?? 0, color: r ? SEVERITY_COLORS[r.severity] : '#334155' }
        );
      }
    }

    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: DISTRICTS.map((d) => {
        const r = byId.get(d.id);
        return {
          type: 'Feature',
          properties: {
            districtId: d.id,
            name: d.name,
            score: r?.score ?? 0,
            color: r ? SEVERITY_COLORS[r.severity] : '#475569',
          },
          geometry: { type: 'Point', coordinates: d.centroid },
        };
      }),
    };
    (map.getSource('risk-centroids') as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [risk, boundaries, ready, epoch]);

  /* ------------------------------ rainfall layer ---------------------------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !rain) return;
    const byId = new Map(rain.map((r) => [r.districtId, r]));

    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: DISTRICTS.map((d) => {
        const r = byId.get(d.id);
        const intensity = r?.hourly[Math.min(timelineHour, 71)] ?? 0;
        return {
          type: 'Feature',
          properties: { districtId: d.id, name: d.name, intensity, next24: r?.next24h ?? 0 },
          geometry: { type: 'Point', coordinates: d.centroid },
        };
      }),
    };
    (map.getSource('rainfall') as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [rain, timelineHour, ready, epoch]);

  /* ------------------------------- alert layer ------------------------------ */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !alerts) return;
    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: alerts
        .filter((a) => a.coords)
        .map((a) => ({
          type: 'Feature',
          properties: {
            title: a.title,
            severity: a.severity,
            color: SEVERITY_COLORS[a.severity],
            hazard: a.hazard,
            source: a.source,
            link: a.link ?? '',
          },
          geometry: { type: 'Point', coordinates: a.coords! },
        })),
    };
    (map.getSource('alerts') as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [alerts, ready, epoch]);

  /* ------------------------------- quake layer ------------------------------ */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !quakes) return;
    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: quakes.map((q) => ({
        type: 'Feature',
        properties: { mag: q.mag, place: q.place, time: q.time, url: q.url },
        geometry: { type: 'Point', coordinates: q.coords },
      })),
    };
    (map.getSource('quakes') as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [quakes, ready, epoch]);

  /* ---------------------------- layer visibility ---------------------------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const vis = (ids: string[], on: boolean) =>
      ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'));

    vis(['districts-fill', 'districts-line'], activeLayers.has('risk'));
    vis(['risk-centroid-circles'], activeLayers.has('risk') && !boundaries);
    vis(['rainfall-circles'], activeLayers.has('rainfall'));
    vis(['alert-halo', 'alert-dots'], activeLayers.has('alerts'));
    vis(['quake-circles'], activeLayers.has('quakes'));
    vis(['gauge-circles'], activeLayers.has('gauges'));
    vis(['infra-circles'], activeLayers.has('infrastructure'));
    vis(['gibs-satellite'], activeLayers.has('satellite'));
  }, [activeLayers, ready, boundaries, epoch]);

  /* --------------------------- selection highlight -------------------------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getLayer('districts-line')) return;
    map.setPaintProperty('districts-line', 'line-width', [
      'case', ['==', ['get', 'districtId'], selectedDistrictId ?? ''], 2.5, 0.9,
    ]);
    map.setPaintProperty('districts-line', 'line-color', [
      'case', ['==', ['get', 'districtId'], selectedDistrictId ?? ''], '#38bdf8', '#64748b',
    ]);
  }, [selectedDistrictId, ready, boundaries, epoch]);

  /* ------------------------------ interactions ------------------------------ */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const clickDistrict = (e: any) => {
      const f = e.features?.[0];
      if (f?.properties?.districtId) selectDistrict(f.properties.districtId);
    };
    const popup = (html: string, lngLat: any) =>
      new Popup({ closeButton: false, className: 'veg-popup', maxWidth: '280px' })
        .setLngLat(lngLat)
        .setHTML(html)
        .addTo(map);

    const onAlert = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      popup(
        `<strong>${esc(p.title)}</strong><br/><span style="color:${p.color}">● ${String(p.severity).toUpperCase()}</span> · ${esc(p.source)}`,
        e.lngLat
      );
    };
    const onQuake = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      popup(`<strong>M${Number(p.mag).toFixed(1)}</strong> ${esc(p.place)}`, e.lngLat);
    };
    const onGauge = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      popup(
        `<strong>${esc(p.name)}</strong> · ${esc(p.river)}<br/>Level ${p.level} m — warning ${p.warning} m / danger ${p.danger} m<br/><em>sample data</em>`,
        e.lngLat
      );
    };
    const onInfra = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      popup(`<strong>${esc(p.name)}</strong><br/>${esc(p.type)} · <em>sample data</em>`, e.lngLat);
    };

    const hoverables = ['districts-fill', 'risk-centroid-circles', 'alert-dots', 'quake-circles', 'gauge-circles', 'infra-circles'];
    const enter = () => (map.getCanvas().style.cursor = 'pointer');
    const leave = () => (map.getCanvas().style.cursor = '');

    map.on('click', 'districts-fill', clickDistrict);
    map.on('click', 'risk-centroid-circles', clickDistrict);
    map.on('click', 'alert-dots', onAlert);
    map.on('click', 'quake-circles', onQuake);
    map.on('click', 'gauge-circles', onGauge);
    map.on('click', 'infra-circles', onInfra);
    hoverables.forEach((l) => {
      map.on('mouseenter', l, enter);
      map.on('mouseleave', l, leave);
    });

    return () => {
      map.off('click', 'districts-fill', clickDistrict);
      map.off('click', 'risk-centroid-circles', clickDistrict);
      map.off('click', 'alert-dots', onAlert);
      map.off('click', 'quake-circles', onQuake);
      map.off('click', 'gauge-circles', onGauge);
      map.off('click', 'infra-circles', onInfra);
      hoverables.forEach((l) => {
        map.off('mouseenter', l, enter);
        map.off('mouseleave', l, leave);
      });
    };
  }, [ready, selectDistrict]);

  /* ----------------------- fly to selected district ------------------------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !selectedDistrictId) return;
    const d = DISTRICTS.find((x) => x.id === selectedDistrictId);
    if (d) map.flyTo({ center: d.centroid, zoom: 8.4, duration: 1400, essential: false });
  }, [selectedDistrictId, ready]);

  return (
    <div className="absolute inset-0">
      <div
        ref={containerRef}
        className="absolute inset-0"
        aria-label="Interactive hazard map of Kerala and South India"
        role="application"
      />
      {!ready && !initError && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="rounded-full border border-white/10 bg-ink-900/80 px-4 py-2 font-mono text-xs text-ink-400 backdrop-blur">
            loading basemap…
          </span>
        </div>
      )}
      {initError && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="max-w-md rounded-xl border border-sev-red/30 bg-ink-900/90 px-4 py-2 text-center font-mono text-xs text-sev-red backdrop-blur">
            map engine failed to start — {initError}
          </span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------ overlay setup ------------------------------ */

/** Idempotent: attaches every overlay source + layer if missing. */
function ensureOverlays(map: MLMap) {
  const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
  const addSource = (id: string, spec: any) => {
    if (!map.getSource(id)) map.addSource(id, spec);
  };
  const addLayer = (spec: any) => {
    if (!map.getLayer(spec.id)) map.addLayer(spec);
  };

  // NASA GIBS satellite overlay (yesterday's VIIRS true colour)
  const date = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  addSource('gibs', {
    type: 'raster',
    tiles: [
      `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
    ],
    tileSize: 256,
    maxzoom: 9,
    attribution: 'NASA GIBS / VIIRS',
  });
  addLayer({
    id: 'gibs-satellite',
    type: 'raster',
    source: 'gibs',
    layout: { visibility: 'none' },
    paint: { 'raster-opacity': 0.85 },
  });

  // District polygons (choropleth via feature-state)
  addSource('districts', { type: 'geojson', data: empty, promoteId: 'districtId' });
  addLayer({
    id: 'districts-fill',
    type: 'fill',
    source: 'districts',
    paint: {
      'fill-color': ['coalesce', ['feature-state', 'color'], '#334155'],
      'fill-opacity': [
        'interpolate', ['linear'], ['coalesce', ['feature-state', 'score'], 0],
        0, 0.12, 40, 0.3, 70, 0.48, 100, 0.58,
      ],
    },
  });
  addLayer({
    id: 'districts-line',
    type: 'line',
    source: 'districts',
    paint: { 'line-color': '#64748b', 'line-width': 0.9 },
  });

  // Centroid circles — seeded so the map is never blank while data loads
  const seed: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: DISTRICTS.map((d) => ({
      type: 'Feature',
      properties: { districtId: d.id, name: d.name, score: 0, color: '#475569' },
      geometry: { type: 'Point', coordinates: d.centroid },
    })),
  };
  addSource('risk-centroids', { type: 'geojson', data: seed as any });
  addLayer({
    id: 'risk-centroid-circles',
    type: 'circle',
    source: 'risk-centroids',
    paint: {
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.55,
      'circle-radius': ['interpolate', ['linear'], ['get', 'score'], 0, 8, 100, 30],
      'circle-stroke-color': ['get', 'color'],
      'circle-stroke-width': 1.5,
      'circle-stroke-opacity': 0.9,
    },
  });

  // Rainfall
  addSource('rainfall', { type: 'geojson', data: empty });
  addLayer({
    id: 'rainfall-circles',
    type: 'circle',
    source: 'rainfall',
    paint: {
      'circle-color': '#38bdf8',
      'circle-blur': 0.6,
      'circle-opacity': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0, 0.5, 0.25, 5, 0.5, 15, 0.75],
      'circle-radius': ['interpolate', ['linear'], ['get', 'intensity'], 0, 4, 2, 14, 8, 30, 20, 52],
    },
  });

  // Alerts
  addSource('alerts', { type: 'geojson', data: empty });
  addLayer({
    id: 'alert-halo',
    type: 'circle',
    source: 'alerts',
    paint: { 'circle-color': ['get', 'color'], 'circle-opacity': 0.18, 'circle-radius': 22, 'circle-blur': 0.4 },
  });
  addLayer({
    id: 'alert-dots',
    type: 'circle',
    source: 'alerts',
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': 7,
      'circle-stroke-color': '#05070d',
      'circle-stroke-width': 2,
    },
  });

  // Quakes
  addSource('quakes', { type: 'geojson', data: empty });
  addLayer({
    id: 'quake-circles',
    type: 'circle',
    source: 'quakes',
    layout: { visibility: 'none' },
    paint: {
      'circle-color': '#a78bfa',
      'circle-opacity': 0.75,
      'circle-radius': ['interpolate', ['linear'], ['get', 'mag'], 2, 4, 5, 12, 7, 24],
      'circle-stroke-color': '#05070d',
      'circle-stroke-width': 1.5,
    },
  });

  // River gauges & dams (sample tier)
  addSource('gauges', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: RIVER_GAUGES.map((g) => {
        const status = g.levelM >= g.dangerM ? '#ef4444' : g.levelM >= g.warningM ? '#f97316' : '#22c55e';
        return {
          type: 'Feature' as const,
          properties: { name: g.name, river: g.river, level: g.levelM, warning: g.warningM, danger: g.dangerM, status },
          geometry: { type: 'Point' as const, coordinates: g.coords },
        };
      }),
    },
  });
  addLayer({
    id: 'gauge-circles',
    type: 'circle',
    source: 'gauges',
    paint: {
      'circle-color': ['get', 'status'],
      'circle-radius': 6,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 1.2,
      'circle-stroke-opacity': 0.7,
    },
  });

  // Infrastructure (sample tier)
  addSource('infra', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: SHELTERS.map((s) => ({
        type: 'Feature' as const,
        properties: { name: s.name, type: s.type },
        geometry: { type: 'Point' as const, coordinates: s.coords },
      })),
    },
  });
  addLayer({
    id: 'infra-circles',
    type: 'circle',
    source: 'infra',
    layout: { visibility: 'none' },
    paint: {
      'circle-color': ['match', ['get', 'type'], 'hospital', '#f472b6', 'shelter', '#34d399', 'fire', '#fb923c', '#94a3b8'],
      'circle-radius': 5.5,
      'circle-stroke-color': '#05070d',
      'circle-stroke-width': 1.5,
    },
  });
}

function esc(s: unknown): string {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
}
