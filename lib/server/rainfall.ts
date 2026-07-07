import { DISTRICTS } from '@/lib/districts';
import type { RainPoint } from '@/lib/types';

/**
 * Fetch rainfall for all district centroids in ONE Open-Meteo request
 * (the API accepts comma-separated coordinate lists and returns an array).
 * Free, key-less, CC-BY — ideal for the LIVE tier.
 */
export async function fetchRainfall(): Promise<RainPoint[]> {
  const lats = DISTRICTS.map((d) => d.centroid[1]).join(',');
  const lons = DISTRICTS.map((d) => d.centroid[0]).join(',');
  const url =
    `https://api.open-meteo.com/v1/forecast?latitude=${lats}&longitude=${lons}` +
    `&hourly=precipitation&past_days=1&forecast_days=4&timezone=Asia%2FKolkata`;

  const res = await fetch(url, { next: { revalidate: 900 } });
  if (!res.ok) throw new Error(`open-meteo ${res.status}`);
  const json = await res.json();
  const entries: any[] = Array.isArray(json) ? json : [json];

  return DISTRICTS.map((d, i) => {
    const e = entries[i];
    const times: string[] = e?.hourly?.time ?? [];
    const precip: number[] = (e?.hourly?.precipitation ?? []).map((v: number | null) => v ?? 0);

    // Index of "now" within the series (series starts 24 h in the past).
    const nowIso = new Date().toISOString().slice(0, 13);
    let nowIdx = times.findIndex((t) => t.slice(0, 13) >= nowIso);
    if (nowIdx < 0) nowIdx = 24;

    const sum = (from: number, to: number) =>
      precip.slice(Math.max(0, from), Math.min(precip.length, to)).reduce((a, b) => a + b, 0);

    const hourly = precip.slice(nowIdx, nowIdx + 72);
    while (hourly.length < 72) hourly.push(0);

    return {
      districtId: d.id,
      past24h: round1(sum(nowIdx - 24, nowIdx)),
      next24h: round1(sum(nowIdx, nowIdx + 24)),
      next48h: round1(sum(nowIdx, nowIdx + 48)),
      next72h: round1(sum(nowIdx, nowIdx + 72)),
      hourly: hourly.map(round1),
      hourlyStart: times[nowIdx] ?? new Date().toISOString(),
    };
  });
}

function round1(v: number): number {
  return Math.round(v * 10) / 10;
}
