'use client';

import maplibregl, { Map as MLMap, Popup } from 'maplibre-gl';
import { useEffect, useRef, useState } from 'react';
import { DISTRICTS, KERALA_CENTER, REGION_BOUNDS } from '@/lib/districts';
import { fetchDistrictBoundaries } from '@/lib/geo';
import { SHELTERS } from '@/lib/sampleData';
import { SEVERITY_COLORS } from '@/lib/types';
import type { HazardAlert, Quake, RainPoint, RiskScore, RiverStatus } from '@/lib/types';
import { qty } from '@/lib/format';
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

/** Sea colour for the dark basemap — a deep muted ocean blue that reads clearly
 *  as water without breaking the dark-glass aesthetic. */
const SEA_BLUE = '#0f3355';

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
/**
 * District choropleth opacity, with a ~18% brighten under the cursor (C3).
 * Shared by ensureOverlays and PAINT_TARGETS so the pop-in tween and its final
 * snap both preserve the hover boost.
 */
const DISTRICT_FILL_OPACITY: any = [
  '*',
  ['case', ['boolean', ['feature-state', 'hover'], false], 1.18, 1],
  [
    'interpolate', ['linear'], ['coalesce', ['feature-state', 'score'], 0],
    0, 0.12, 40, 0.3, 70, 0.48, 100, 0.58,
  ],
];

const PAINT_TARGETS: Record<string, { opacity: Record<string, any>; radius?: Record<string, any> }> = {
  'districts-fill': {
    opacity: {
      'fill-opacity': DISTRICT_FILL_OPACITY,
    },
  },
  'districts-line': { opacity: { 'line-opacity': 1 } },
  'risk-centroid-circles': {
    opacity: {
      'circle-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.75, 0.55],
      'circle-stroke-opacity': 0.9,
    },
    radius: { 'circle-radius': ['interpolate', ['linear'], ['get', 'score'], 0, 8, 100, 30] },
  },
  'rainfall-icons': {
    opacity: {
      'icon-opacity': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0, 0.3, 0.75, 5, 1],
    },
  },
  'alert-halo': { opacity: { 'circle-opacity': 0.18 }, radius: { 'circle-radius': 22 } },
  'alert-icons': { opacity: { 'icon-opacity': 1 } },
  'quake-icons': { opacity: { 'icon-opacity': 0.95 } },
  'gauge-icons': { opacity: { 'icon-opacity': 1 } },
  'infra-icons': { opacity: { 'icon-opacity': 1 } },
  'gibs-satellite': { opacity: { 'raster-opacity': 0.85 } },
};

/** Which map layers belong to each toggleable UI layer. */
const UI_LAYER_MAP: Record<string, string[]> = {
  risk: ['districts-fill', 'districts-line', 'risk-centroid-circles'],
  rainfall: ['rainfall-icons'],
  alerts: ['alert-halo', 'alert-icons'],
  quakes: ['quake-icons'],
  gauges: ['gauge-icons'],
  infrastructure: ['infra-icons'],
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
  rivers: RiverStatus[] | null;
}

const RIVER_STATUS_COLOR: Record<string, string> = {
  normal: '#22c55e',
  elevated: '#f97316',
  high: '#ef4444',
};

export default function MapCanvas({ risk, rain, alerts, quakes, rivers }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const darkStyleRef = useRef<any>(BOOT_DARK_STYLE);
  /** Increments on every style.load — overlay layers exist iff epoch > 0. */
  const [epoch, setEpoch] = useState(0);
  const [initError, setInitError] = useState<string | null>(null);
  const [boundaries, setBoundaries] = useState<GeoJSON.FeatureCollection | null>(null);

  const activeLayers = useAppStore((s) => s.activeLayers);
  const lastLayerEvent = useAppStore((s) => s.lastLayerEvent);
  const basemapMode = useAppStore((s) => s.basemapMode);
  const timelineHour = useAppStore((s) => s.timelineHour);
  const selectDistrict = useAppStore((s) => s.selectDistrict);
  const selectedDistrictId = useAppStore((s) => s.selectedDistrictId);
  const setCompareDistrict = useAppStore((s) => s.setCompareDistrict);
  const highlightStation = useAppStore((s) => s.highlightStation);

  /** Hidden aria-live region so popup content reaches screen readers (A1). */
  const liveRef = useRef<HTMLDivElement>(null);

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
    // bottom-right so it never collides with the timeline in the bottom-left
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
    map.on('error', (e: any) => console.warn('[vegvisir] map warning:', e?.error?.message ?? e));

    // All marker sprites are canvas-drawn on demand, per style — basemap
    // swaps can never lose them and there are zero image assets to load.
    map.on('styleimagemissing', (e: any) => {
      if (map.hasImage(e.id)) return;
      const img = e.id === 'rain-icon' ? makeRainIcon(64) : makeMapIcon(e.id, 64);
      if (img) map.addImage(e.id, img, { pixelRatio: 2 });
    });

    // Re-attach overlays after EVERY style load (boot, upgrade, mode switch).
    // ensureOverlays is idempotent, so calling it from multiple paths is safe.
    const attach = () => {
      try {
        ensureOverlays(map);
        tintSeaBlue(map);
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
        // I5 — deterministic per-district jitter so the rain icons read as
        // weather rather than a regular grid at district centroids.
        const h = hashStr(d.id);
        const jitter = 0.9 + ((h % 1000) / 1000) * 0.2; // ±10% size
        const offset: [number, number] = [
          ((h % 7) - 3) * 1.4, // ~±4px x
          (((h >> 3) % 7) - 3) * 1.4, // ~±4px y
        ];
        return {
          type: 'Feature',
          properties: { districtId: d.id, name: d.name, intensity, next24: r?.next24h ?? 0, jitter, offset },
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

  /* ------------------------------- river layer ------------------------------ */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !rivers) return;
    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: rivers.map((r) => ({
        type: 'Feature',
        properties: {
          stationId: r.id,
          districtId: r.districtId,
          name: r.name,
          river: r.river,
          discharge: r.dischargeM3s,
          median: r.median31d,
          ratio: r.ratio,
          forecastMax: r.forecastMax7d,
          trend: r.trend,
          status: RIVER_STATUS_COLOR[r.status],
          statusLabel: r.status,
        },
        geometry: { type: 'Point', coordinates: r.coords },
      })),
    };
    (map.getSource('gauges') as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [rivers, ready, epoch]);

  /* ---------------------------- layer visibility ---------------------------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const vis = (ids: string[], on: boolean) =>
      ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'));

    vis(['districts-fill', 'districts-line'], activeLayers.has('risk'));
    vis(['risk-centroid-circles'], activeLayers.has('risk') && !boundaries);
    vis(['rainfall-icons'], activeLayers.has('rainfall'));
    vis(['alert-halo', 'alert-icons'], activeLayers.has('alerts'));
    vis(['quake-icons'], activeLayers.has('quakes'));
    vis(['gauge-icons'], activeLayers.has('gauges'));
    vis(['infra-icons'], activeLayers.has('infrastructure'));
    vis(['gibs-satellite'], activeLayers.has('satellite'));
  }, [activeLayers, ready, boundaries, epoch]);

  /* ----------------------------- alert pulse ------------------------------- */
  // Active alerts breathe — a continuous soft radar pulse on the halo layer.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !activeLayers.has('alerts')) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let raf = 0;
    const loop = (t: number) => {
      if (map.getLayer('alert-halo')) {
        const k = (Math.sin(t / 480) + 1) / 2; // 0→1, ~3 s period
        map.setPaintProperty('alert-halo', 'circle-radius', 16 + k * 14);
        map.setPaintProperty('alert-halo', 'circle-opacity', 0.3 - 0.24 * k);
      }
      raf = requestAnimationFrame(loop);
    };
    // R3 — don't burn a rAF loop while the tab is backgrounded; gate it on
    // visibility like the data hooks do.
    const start = () => {
      if (!raf) raf = requestAnimationFrame(loop);
    };
    const stop = () => {
      if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    };
    const onVis = () => (document.hidden ? stop() : start());
    if (!document.hidden) start();
    document.addEventListener('visibilitychange', onVis);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVis);
      if (map.getLayer('alert-halo')) {
        map.setPaintProperty('alert-halo', 'circle-radius', 22);
        map.setPaintProperty('alert-halo', 'circle-opacity', 0.18);
      }
    };
  }, [ready, epoch, activeLayers]);

  /* --------------------------- layer pop-in animation ------------------------ */
  // Runs AFTER the visibility effect (declared above) has made the layer
  // visible, so the tween animates an already-visible layer from 0 → target.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !lastLayerEvent?.on) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const mapLayers = (UI_LAYER_MAP[lastLayerEvent.id] ?? []).filter(
      // centroid circles are hidden when polygons are present — don't animate hidden layers
      (id) => id !== 'risk-centroid-circles' || !boundaries
    );
    const cancels = mapLayers.map((id) => animateLayerIn(map, id));

    return () => cancels.forEach((c) => c()); // snap to exact finals on cleanup
  }, [lastLayerEvent, ready, boundaries]);

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

    let currentPopup: Popup | null = null;

    const announce = (text: string) => {
      if (liveRef.current) liveRef.current.textContent = text;
    };

    // T1 — popups in the design system: Space Grotesk title, tabular figures,
    // status-coloured left border. A1 — mirror the content to the aria-live
    // region so screen readers get what MapLibre injects as raw HTML.
    const popup = (bodyHtml: string, lngLat: any, accent: string, sr: string) => {
      currentPopup?.remove();
      const p = new Popup({ closeButton: false, className: 'veg-popup', maxWidth: '300px' })
        .setLngLat(lngLat)
        .setHTML(`<div class="veg-popup__body" style="--veg-accent:${safeColor(accent)}">${bodyHtml}</div>`)
        .addTo(map);
      currentPopup = p;
      p.on('close', () => {
        if (currentPopup === p) currentPopup = null;
      });
      announce(sr);
    };

    const clickDistrict = (e: any) => {
      const f = e.features?.[0];
      if (f?.properties?.districtId) selectDistrict(f.properties.districtId);
    };
    // X5 — double-click pins a second district for side-by-side comparison.
    const compareDistrict = (e: any) => {
      const f = e.features?.[0];
      if (f?.properties?.districtId) setCompareDistrict(f.properties.districtId);
    };

    const onAlert = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      const sev = String(p.severity).toUpperCase();
      popup(
        `<div class="veg-popup__title">${esc(p.title)}</div>` +
          `<div class="veg-popup__meta" style="margin-top:4px"><span class="veg-popup__status">● ${esc(sev)}</span> · ${esc(p.source)}</div>`,
        e.lngLat,
        p.color,
        `Hazard alert: ${p.title}. Severity ${p.severity}. Source ${p.source}.`
      );
    };
    const onQuake = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      const m = num(p.mag).toFixed(1);
      popup(
        `<div class="veg-popup__title">M<span class="veg-popup__num">${m}</span></div>` +
          `<div class="veg-popup__meta" style="margin-top:2px">${esc(p.place)}</div>`,
        e.lngLat,
        '#a78bfa',
        `Earthquake magnitude ${m} near ${p.place}.`
      );
    };
    const onGauge = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      const arrow = p.trend === 'rising' ? '↑ rising' : p.trend === 'falling' ? '↓ falling' : '→ steady';
      popup(
        `<div class="veg-popup__title">${esc(p.name)} <span class="veg-popup__meta" style="font-weight:400">· ${esc(p.river)}</span></div>` +
          `<div class="veg-popup__meta" style="margin-top:4px">Discharge <span class="veg-popup__num" style="color:#e2e8f0;font-weight:600">${qty(num(p.discharge), 'm³/s')}</span> (${arrow})</div>` +
          `<div style="margin-top:2px"><span class="veg-popup__status">● ${esc(p.statusLabel)}</span> <span class="veg-popup__meta">— <span class="veg-popup__num">${num(p.ratio)}×</span> the 31-day median (<span class="veg-popup__num">${qty(num(p.median), 'm³/s')}</span>)</span></div>` +
          `<div class="veg-popup__meta veg-popup__num" style="margin-top:2px">7-day forecast peak: ${qty(num(p.forecastMax), 'm³/s')}</div>` +
          `<div class="veg-popup__meta" style="margin-top:4px;font-style:italic">GloFAS via Open-Meteo</div>`,
        e.lngLat,
        p.status,
        `River station ${p.name} on the ${p.river}. Discharge ${num(p.discharge)} cubic metres per second, ${p.statusLabel}, ${num(p.ratio)} times the median.`
      );
      // L5 — dedupe popup ⇄ panel: open the district drill-down and flash the
      // station's row so the two surfaces are visibly linked.
      if (p.districtId) selectDistrict(p.districtId);
      if (p.stationId) highlightStation(p.stationId);
    };
    const onInfra = (e: any) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      popup(
        `<div class="veg-popup__title">${esc(p.name)}</div>` +
          `<div class="veg-popup__meta" style="margin-top:2px">${esc(p.type)} · <span style="font-style:italic">sample data</span></div>`,
        e.lngLat,
        '#34d399',
        `Facility: ${p.name}, ${p.type}. Sample data.`
      );
    };

    // Hover feedback:
    //  · C3 — districts (fill/circle are PAINT props) brighten via feature-state.
    //  · I3 — marker badges (icon-size is a LAYOUT prop, no feature-state) get a
    //    hover halo ring that follows the pointer, reading as a scale-up.
    const FS_SRC: Record<string, string> = {
      'districts-fill': 'districts',
      'risk-centroid-circles': 'risk-centroids',
    };
    let hoveredFS: { layer: string; id: string | number } | null = null;
    const clearFS = () => {
      if (hoveredFS != null) {
        map.setFeatureState({ source: FS_SRC[hoveredFS.layer], id: hoveredFS.id } as any, { hover: false });
        hoveredFS = null;
      }
    };
    const clearHalo = () =>
      (map.getSource('hover-halo') as maplibregl.GeoJSONSource)?.setData({ type: 'FeatureCollection', features: [] } as any);

    const onMove = (layer: string) => (e: any) => {
      const f = e.features?.[0];
      if (f == null) return;
      map.getCanvas().style.cursor = 'pointer';
      if (FS_SRC[layer]) {
        if (f.id == null) return;
        if (hoveredFS && (hoveredFS.layer !== layer || hoveredFS.id !== f.id)) clearFS();
        hoveredFS = { layer, id: f.id };
        map.setFeatureState({ source: FS_SRC[layer], id: f.id } as any, { hover: true });
      } else if (f.geometry?.type === 'Point') {
        (map.getSource('hover-halo') as maplibregl.GeoJSONSource)?.setData({
          type: 'FeatureCollection',
          features: [{ type: 'Feature', properties: {}, geometry: f.geometry }],
        } as any);
      }
    };
    const onLeave = () => {
      clearFS();
      clearHalo();
      map.getCanvas().style.cursor = '';
    };

    // L2 — Escape closes an open popup.
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape' && currentPopup) {
        currentPopup.remove();
        currentPopup = null;
      }
    };
    window.addEventListener('keydown', onKey);

    const moveHandlers: Record<string, (e: any) => void> = {};
    const hoverables = ['districts-fill', 'risk-centroid-circles', 'rainfall-icons', 'alert-icons', 'quake-icons', 'gauge-icons', 'infra-icons'];
    hoverables.forEach((l) => {
      moveHandlers[l] = onMove(l);
      map.on('mousemove', l, moveHandlers[l]);
      map.on('mouseleave', l, onLeave);
    });

    map.on('click', 'districts-fill', clickDistrict);
    map.on('click', 'risk-centroid-circles', clickDistrict);
    map.on('click', 'rainfall-icons', clickDistrict);
    map.on('dblclick', 'districts-fill', compareDistrict);
    map.on('dblclick', 'risk-centroid-circles', compareDistrict);
    map.on('click', 'alert-icons', onAlert);
    map.on('click', 'quake-icons', onQuake);
    map.on('click', 'gauge-icons', onGauge);
    map.on('click', 'infra-icons', onInfra);

    return () => {
      window.removeEventListener('keydown', onKey);
      currentPopup?.remove();
      clearFS();
      clearHalo();
      map.off('click', 'districts-fill', clickDistrict);
      map.off('click', 'risk-centroid-circles', clickDistrict);
      map.off('click', 'rainfall-icons', clickDistrict);
      map.off('dblclick', 'districts-fill', compareDistrict);
      map.off('dblclick', 'risk-centroid-circles', compareDistrict);
      map.off('click', 'alert-icons', onAlert);
      map.off('click', 'quake-icons', onQuake);
      map.off('click', 'gauge-icons', onGauge);
      map.off('click', 'infra-icons', onInfra);
      hoverables.forEach((l) => {
        map.off('mousemove', l, moveHandlers[l]);
        map.off('mouseleave', l, onLeave);
      });
    };
  }, [ready, selectDistrict, setCompareDistrict, highlightStation]);

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
      {/* A1 — screen-reader mirror of map popups (MapLibre injects raw HTML) */}
      <div ref={liveRef} aria-live="polite" className="sr-only" />
    </div>
  );
}

/**
 * Recolour the basemap's water to blue. The CARTO Dark Matter vector style
 * paints the sea near-black; we tint every water fill (and waterway line) so
 * the coastline reads. Runs on every style.load, so it survives basemap swaps.
 * The satellite style is raster-only (no water layer), so it's left untouched.
 */
function tintSeaBlue(map: MLMap) {
  let style: any;
  try {
    style = map.getStyle();
  } catch {
    return;
  }
  if (!style?.layers) return;
  for (const layer of style.layers) {
    if (!/water|ocean|sea|marine/i.test(layer.id)) continue;
    try {
      if (layer.type === 'fill') {
        map.setPaintProperty(layer.id, 'fill-color', SEA_BLUE);
      } else if (layer.type === 'line') {
        map.setPaintProperty(layer.id, 'line-color', SEA_BLUE);
      }
    } catch {
      /* layer not paintable — skip */
    }
  }
}

/** Small deterministic string hash → non-negative int (for stable jitter). */
function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
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
      'fill-opacity': DISTRICT_FILL_OPACITY,
      // I4 — ease the colour change so a district shifting Normal→Watch visibly
      // transitions rather than snapping when risk recomputes. (Opacity is left
      // un-transitioned; the layer pop-in tween drives it frame-by-frame.)
      'fill-color-transition': { duration: 600, delay: 0 },
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
  addSource('risk-centroids', { type: 'geojson', data: seed as any, generateId: true });
  addLayer({
    id: 'risk-centroid-circles',
    type: 'circle',
    source: 'risk-centroids',
    paint: {
      'circle-color': ['get', 'color'],
      'circle-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.75, 0.55],
      'circle-radius': ['interpolate', ['linear'], ['get', 'score'], 0, 8, 100, 30],
      'circle-stroke-color': ['get', 'color'],
      'circle-stroke-width': 1.5,
      'circle-stroke-opacity': 0.9,
    },
  });

  // Rainfall — cloud/rain icon, only where it's actually raining at the
  // scrubbed hour; icon grows with intensity (mm/h).
  addSource('rainfall', { type: 'geojson', data: empty });
  addLayer({
    id: 'rainfall-icons',
    type: 'symbol',
    source: 'rainfall',
    filter: ['>=', ['get', 'intensity'], 0.2],
    layout: {
      'icon-image': 'rain-icon',
      // I5 — multiply base intensity size by the per-district jitter, and nudge
      // by a deterministic offset, so icons don't line up on a grid.
      'icon-size': [
        '*',
        ['coalesce', ['get', 'jitter'], 1],
        ['interpolate', ['linear'], ['get', 'intensity'], 0.2, 0.55, 2, 0.8, 8, 1.1, 20, 1.5],
      ],
      'icon-offset': ['coalesce', ['get', 'offset'], ['literal', [0, 0]]],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: {
      'icon-opacity': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0, 0.3, 0.75, 5, 1],
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
    id: 'alert-icons',
    type: 'symbol',
    source: 'alerts',
    layout: {
      'icon-image': ['concat', 'alert-', ['get', 'severity']],
      'icon-size': 0.7,
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: { 'icon-opacity': 1 },
  });

  // Quakes — epicenter badge scaled by magnitude
  addSource('quakes', { type: 'geojson', data: empty });
  addLayer({
    id: 'quake-icons',
    type: 'symbol',
    source: 'quakes',
    layout: {
      'icon-image': 'quake-icon',
      'icon-size': ['interpolate', ['linear'], ['get', 'mag'], 2, 0.5, 5, 0.8, 7, 1.1],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      visibility: 'none',
    },
    paint: { 'icon-opacity': 0.95 },
  });

  // Rivers — wave badge, ring colour = status, size grows with anomaly
  addSource('gauges', { type: 'geojson', data: empty });
  addLayer({
    id: 'gauge-icons',
    type: 'symbol',
    source: 'gauges',
    layout: {
      'icon-image': ['concat', 'gauge-', ['coalesce', ['get', 'statusLabel'], 'normal']],
      'icon-size': ['interpolate', ['linear'], ['coalesce', ['get', 'ratio'], 1], 0, 0.5, 1, 0.6, 3, 0.85, 6, 1.05],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: { 'icon-opacity': 1 },
  });

  // Infrastructure — hospital cross / shelter house / fire flame badges
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
    id: 'infra-icons',
    type: 'symbol',
    source: 'infra',
    layout: {
      'icon-image': ['concat', 'infra-', ['get', 'type']],
      'icon-size': 0.6,
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      visibility: 'none',
    },
    paint: { 'icon-opacity': 1 },
  });

  // I3 — hover halo: a soft ring that follows the pointer over any marker,
  // giving badge hover feedback without feature-state in layout properties.
  addSource('hover-halo', { type: 'geojson', data: empty });
  addLayer({
    id: 'hover-halo-ring',
    type: 'circle',
    source: 'hover-halo',
    paint: {
      'circle-radius': 18,
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': '#e2e8f0',
      'circle-stroke-width': 2,
      'circle-stroke-opacity': 0.75,
      'circle-radius-transition': { duration: 120 },
    },
  });
}

/** Cloud-with-raindrops sprite, drawn on a canvas (no asset, no async). */
function makeRainIcon(size: number): ImageData {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d')!;
  const s = size / 64;

  // soft glow so the icon reads on any basemap
  ctx.shadowColor = 'rgba(56, 189, 248, 0.55)';
  ctx.shadowBlur = 7 * s;

  // cloud — three lobes + base
  ctx.fillStyle = 'rgba(191, 219, 254, 0.98)';
  ctx.beginPath();
  ctx.arc(21 * s, 27 * s, 11 * s, 0, Math.PI * 2);
  ctx.arc(33 * s, 20 * s, 13 * s, 0, Math.PI * 2);
  ctx.arc(45 * s, 28 * s, 10 * s, 0, Math.PI * 2);
  ctx.rect(21 * s, 26 * s, 24 * s, 12 * s);
  ctx.fill();

  // raindrops
  ctx.shadowBlur = 4 * s;
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 4.5 * s;
  ctx.lineCap = 'round';
  for (const [x1, y1, x2, y2] of [
    [22, 44, 18, 55],
    [34, 46, 30, 58],
    [46, 44, 42, 55],
  ]) {
    ctx.beginPath();
    ctx.moveTo(x1 * s, y1 * s);
    ctx.lineTo(x2 * s, y2 * s);
    ctx.stroke();
  }
  return ctx.getImageData(0, 0, size, size);
}

/**
 * Badge-icon factory — dark glass disc, coloured ring + glyph, soft glow.
 * One visual language for every marker; drawn on canvas so there are no
 * assets, no async loading, and crisp rendering at any DPI.
 */
const ICON_COLORS: Record<string, string> = {
  'gauge-normal': '#22c55e',
  'gauge-elevated': '#f97316',
  'gauge-high': '#ef4444',
  'alert-green': '#22c55e',
  'alert-yellow': '#eab308',
  'alert-orange': '#f97316',
  'alert-red': '#ef4444',
  'quake-icon': '#a78bfa',
  'infra-hospital': '#f472b6',
  'infra-shelter': '#34d399',
  'infra-fire': '#fb923c',
  'infra-police': '#94a3b8',
};

function makeMapIcon(id: string, size: number): ImageData | null {
  const color = ICON_COLORS[id];
  if (!color) return null;

  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d')!;
  const s = size / 64;
  const cx = 32 * s;
  const cy = 32 * s;

  // glowing dark disc + colour ring
  ctx.shadowColor = color;
  ctx.shadowBlur = 8 * s;
  ctx.fillStyle = 'rgba(8, 12, 22, 0.92)';
  ctx.beginPath();
  ctx.arc(cx, cy, 24 * s, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.strokeStyle = color;
  ctx.lineWidth = 3.5 * s;
  ctx.stroke();

  // glyph
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 3.5 * s;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  if (id.startsWith('gauge-')) {
    // two water waves
    for (const y of [28, 38]) {
      ctx.beginPath();
      ctx.moveTo(19 * s, y * s);
      ctx.quadraticCurveTo(25.5 * s, (y - 7) * s, 32 * s, y * s);
      ctx.quadraticCurveTo(38.5 * s, (y + 7) * s, 45 * s, y * s);
      ctx.stroke();
    }
  } else if (id.startsWith('alert-')) {
    // warning triangle + exclamation
    ctx.beginPath();
    ctx.moveTo(32 * s, 17 * s);
    ctx.lineTo(45 * s, 42 * s);
    ctx.lineTo(19 * s, 42 * s);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(32 * s, 26 * s);
    ctx.lineTo(32 * s, 33 * s);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(32 * s, 38 * s, 1.8 * s, 0, Math.PI * 2);
    ctx.fill();
  } else if (id === 'quake-icon') {
    // seismograph zigzag
    ctx.beginPath();
    ctx.moveTo(16 * s, 32 * s);
    ctx.lineTo(24 * s, 32 * s);
    ctx.lineTo(28 * s, 21 * s);
    ctx.lineTo(34 * s, 43 * s);
    ctx.lineTo(38 * s, 27 * s);
    ctx.lineTo(41 * s, 32 * s);
    ctx.lineTo(48 * s, 32 * s);
    ctx.stroke();
  } else if (id === 'infra-hospital') {
    // medical cross
    ctx.beginPath();
    ctx.moveTo(32 * s, 21 * s);
    ctx.lineTo(32 * s, 43 * s);
    ctx.moveTo(21 * s, 32 * s);
    ctx.lineTo(43 * s, 32 * s);
    ctx.stroke();
  } else if (id === 'infra-shelter') {
    // house
    ctx.beginPath();
    ctx.moveTo(19 * s, 32 * s);
    ctx.lineTo(32 * s, 20 * s);
    ctx.lineTo(45 * s, 32 * s);
    ctx.moveTo(23 * s, 30 * s);
    ctx.lineTo(23 * s, 43 * s);
    ctx.lineTo(41 * s, 43 * s);
    ctx.lineTo(41 * s, 30 * s);
    ctx.stroke();
  } else if (id === 'infra-fire') {
    // flame
    ctx.beginPath();
    ctx.moveTo(32 * s, 18 * s);
    ctx.bezierCurveTo(40 * s, 26 * s, 44 * s, 32 * s, 44 * s, 37 * s);
    ctx.bezierCurveTo(44 * s, 43.5 * s, 38.5 * s, 46 * s, 32 * s, 46 * s);
    ctx.bezierCurveTo(25.5 * s, 46 * s, 20 * s, 43.5 * s, 20 * s, 37 * s);
    ctx.bezierCurveTo(20 * s, 32 * s, 24 * s, 26 * s, 32 * s, 18 * s);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(32 * s, 38 * s, 4 * s, 0, Math.PI * 2);
    ctx.fill();
  } else if (id === 'infra-police') {
    // shield
    ctx.beginPath();
    ctx.moveTo(32 * s, 19 * s);
    ctx.lineTo(43 * s, 24 * s);
    ctx.lineTo(43 * s, 33 * s);
    ctx.quadraticCurveTo(43 * s, 42 * s, 32 * s, 45 * s);
    ctx.quadraticCurveTo(21 * s, 42 * s, 21 * s, 33 * s);
    ctx.lineTo(21 * s, 24 * s);
    ctx.closePath();
    ctx.stroke();
  }

  return ctx.getImageData(0, 0, size, size);
}

function esc(s: unknown): string {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

/** Coerce to a finite number (0 fallback) — never interpolate raw values. */
function num(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/** Only #rgb/#rrggbb colours may enter a style attribute. */
function safeColor(v: unknown): string {
  const s = String(v ?? '');
  return /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(s) ? s : '#64748b';
}
