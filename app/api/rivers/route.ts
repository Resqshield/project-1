import { NextResponse } from 'next/server';
import { RIVER_STATIONS } from '@/lib/riverStations';
import type { RiverStatus } from '@/lib/types';

export const revalidate = 3600; // GloFAS updates daily

/**
 * LIVE river discharge — GloFAS (Copernicus) via the Open-Meteo Flood API.
 * One request covers every station (comma-separated coordinates).
 *
 * Status thresholds are anomaly-based and deliberately simple + published:
 *   ratio = today / median(31 trailing days)
 *   normal < 1.5×   ·   elevated 1.5–3×   ·   high ≥ 3×
 * Roadmap: replace with CWC official warning/danger levels per station.
 */
export async function GET() {
  const lats = RIVER_STATIONS.map((s) => s.coords[1]).join(',');
  const lons = RIVER_STATIONS.map((s) => s.coords[0]).join(',');
  const url =
    `https://flood-api.open-meteo.com/v1/flood?latitude=${lats}&longitude=${lons}` +
    `&daily=river_discharge&past_days=31&forecast_days=7&timezone=Asia%2FKolkata`;

  try {
    const res = await fetch(url, { next: { revalidate: 3600 } });
    if (!res.ok) throw new Error(`flood-api ${res.status}`);
    const json = await res.json();
    const entries: any[] = Array.isArray(json) ? json : [json];

    const data: RiverStatus[] = RIVER_STATIONS.map((s, i) => {
      const series: number[] = (entries[i]?.daily?.river_discharge ?? []).map(
        (v: number | null) => v ?? 0
      );
      // Series layout: 31 past days, then today, then 6 more forecast days.
      const todayIdx = Math.min(31, Math.max(0, series.length - 7));
      const past = series.slice(0, todayIdx);
      const today = series[todayIdx] ?? 0;
      const future = series.slice(todayIdx + 1);

      const median = quantile(past, 0.5) || 0.001;
      const ratio = today / median;
      const next3 = future.slice(0, 3);
      const next3avg = next3.length ? next3.reduce((a, b) => a + b, 0) / next3.length : today;
      const trend: RiverStatus['trend'] =
        next3avg > today * 1.15 ? 'rising' : next3avg < today * 0.85 ? 'falling' : 'steady';

      return {
        ...s,
        dischargeM3s: round1(today),
        median31d: round1(median),
        ratio: Math.round(ratio * 100) / 100,
        forecastMax7d: round1(Math.max(today, ...future, 0)),
        trend,
        status: ratio >= 3 ? 'high' : ratio >= 1.5 ? 'elevated' : 'normal',
        tier: 'live' as const,
      };
    });

    return NextResponse.json(
      { updatedAt: new Date().toISOString(), tier: 'live', source: 'GloFAS via Open-Meteo', data },
      { headers: { 'Cache-Control': 's-maxage=3600, stale-while-revalidate=21600' } }
    );
  } catch (err) {
    const detail = process.env.NODE_ENV === 'production' ? undefined : String(err);
    return NextResponse.json({ error: 'river discharge source unavailable', detail }, { status: 502 });
  }
}

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const a = [...sorted].sort((x, y) => x - y);
  const pos = (a.length - 1) * q;
  const base = Math.floor(pos);
  return a[base] + (a[Math.min(base + 1, a.length - 1)] - a[base]) * (pos - base);
}

function round1(v: number): number {
  return Math.round(v * 10) / 10;
}
