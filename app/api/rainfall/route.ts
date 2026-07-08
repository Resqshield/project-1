import { NextResponse } from 'next/server';
import { fetchRainfall } from '@/lib/server/rainfall';

export const revalidate = 900; // 15 min — Open-Meteo model cadence is 1–6 h

export async function GET() {
  try {
    const data = await fetchRainfall();
    return NextResponse.json(
      { updatedAt: new Date().toISOString(), tier: 'live', source: 'Open-Meteo', data },
      { headers: { 'Cache-Control': 's-maxage=900, stale-while-revalidate=3600' } }
    );
  } catch (err) {
    // Never leak upstream internals in production responses.
    const detail = process.env.NODE_ENV === 'production' ? undefined : String(err);
    return NextResponse.json({ error: 'rainfall source unavailable', detail }, { status: 502 });
  }
}
