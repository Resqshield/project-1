'use client';

import { useEffect, useRef } from 'react';
import { LAYERS } from '@/lib/layers';
import { DISTRICT_BY_ID } from '@/lib/districts';
import type { BasemapMode } from '@/store/useAppStore';
import { useAppStore } from '@/store/useAppStore';
import type { LayerId } from '@/lib/types';

const VALID_LAYERS = new Set(LAYERS.map((l) => l.id));

/**
 * X3 — shareable state in the URL: `?d=WYD&c=IDK&l=risk,rain&b=dark&t=24`.
 * Critical for authorities sharing a situation view, and makes refresh
 * non-destructive. Reads once on mount, then mirrors store → URL via
 * replaceState (no history spam, no navigation).
 */
export default function UrlStateSync() {
  const hydrated = useRef(false);

  // Hydrate from URL once.
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    const p = new URLSearchParams(window.location.search);
    const s = useAppStore.getState();

    const d = p.get('d');
    if (d && DISTRICT_BY_ID.has(d)) s.selectDistrict(d);
    const c = p.get('c');
    if (c && DISTRICT_BY_ID.has(c)) s.setCompareDistrict(c);

    const l = p.get('l');
    if (l !== null) {
      const ids = l.split(',').filter((x): x is LayerId => VALID_LAYERS.has(x as LayerId));
      s.setActiveLayers(ids);
    }

    const b = p.get('b');
    if (b === 'dark' || b === 'satellite') s.setBasemapMode(b as BasemapMode);

    const t = Number(p.get('t'));
    if (Number.isFinite(t) && t >= 0 && t <= 71) s.setTimelineHour(Math.round(t));
  }, []);

  // Mirror store → URL.
  const selectedDistrictId = useAppStore((s) => s.selectedDistrictId);
  const compareDistrictId = useAppStore((s) => s.compareDistrictId);
  const activeLayers = useAppStore((s) => s.activeLayers);
  const basemapMode = useAppStore((s) => s.basemapMode);
  const timelineHour = useAppStore((s) => s.timelineHour);

  useEffect(() => {
    if (!hydrated.current) return;
    const p = new URLSearchParams();
    if (selectedDistrictId) p.set('d', selectedDistrictId);
    if (compareDistrictId) p.set('c', compareDistrictId);
    // Only serialise layers when they differ from default, to keep URLs short.
    p.set('l', LAYERS.filter((l) => activeLayers.has(l.id)).map((l) => l.id).join(','));
    if (basemapMode !== 'dark') p.set('b', basemapMode);
    if (timelineHour > 0) p.set('t', String(timelineHour));
    const qs = p.toString();
    window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
  }, [selectedDistrictId, compareDistrictId, activeLayers, basemapMode, timelineHour]);

  return null;
}
