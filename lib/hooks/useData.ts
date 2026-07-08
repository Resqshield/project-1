'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { HazardAlert, Quake, RainPoint, RiskScore, RiverStatus } from '@/lib/types';

interface Envelope<T> {
  updatedAt: string;
  data: T;
  degraded?: boolean;
}

export interface Feed<T> {
  data: T | null;
  updatedAt: string | null;
  error: boolean;
  loading: boolean;
  refresh: () => void;
}

/**
 * Lightweight polling fetcher — deliberately dependency-free.
 * Pauses polling while the tab is hidden (battery/network courtesy).
 */
function usePolledFeed<T>(url: string, intervalMs: number): Feed<T> {
  const [state, setState] = useState<Omit<Feed<T>, 'refresh'>>({
    data: null,
    updatedAt: null,
    error: false,
    loading: true,
  });
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(String(res.status));
      const json = (await res.json()) as Envelope<T>;
      setState({ data: json.data, updatedAt: json.updatedAt, error: false, loading: false });
    } catch {
      setState((s) => ({ ...s, error: true, loading: false }));
    }
  }, [url]);

  useEffect(() => {
    load();
    const start = () => {
      if (!timer.current) timer.current = setInterval(load, intervalMs);
    };
    const stop = () => {
      if (timer.current) {
        clearInterval(timer.current);
        timer.current = null;
      }
    };
    const onVis = () => (document.hidden ? stop() : (load(), start()));
    start();
    document.addEventListener('visibilitychange', onVis);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [load, intervalMs]);

  return { ...state, refresh: load };
}

export const useRainfall = () => usePolledFeed<RainPoint[]>('/api/rainfall', 15 * 60_000);
export const useRisk = () => usePolledFeed<RiskScore[]>('/api/risk', 15 * 60_000);
export const useAlerts = () => usePolledFeed<HazardAlert[]>('/api/alerts', 5 * 60_000);
export const useQuakes = () => usePolledFeed<Quake[]>('/api/quakes', 5 * 60_000);
export const useRivers = () => usePolledFeed<RiverStatus[]>('/api/rivers', 60 * 60_000);
