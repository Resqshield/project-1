import { NextResponse } from 'next/server';
import { DISTRICTS } from '@/lib/districts';
import { computeRisk } from '@/lib/risk';
import { fetchRainfall } from '@/lib/server/rainfall';
import type { RainPoint } from '@/lib/types';

export const revalidate = 900;

export async function GET() {
  let rain: RainPoint[] = [];
  let degraded = false;
  try {
    rain = await fetchRainfall();
  } catch {
    degraded = true; // risk still computes from static factors (rain = 0)
  }
  const rainBy = new Map(rain.map((r) => [r.districtId, r]));
  const scores = DISTRICTS.map((d) => computeRisk(d, rainBy.get(d.id)));

  return NextResponse.json(
    {
      updatedAt: new Date().toISOString(),
      degraded,
      methodology: '/methodology — weighted overlay v1 (rain 0.40, landslide 0.25, flood 0.25, exposure 0.10)',
      data: scores,
    },
    { headers: { 'Cache-Control': 's-maxage=900, stale-while-revalidate=3600' } }
  );
}
