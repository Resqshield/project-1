import { NextResponse } from 'next/server';
import type { Quake } from '@/lib/types';

export const revalidate = 300;

/** Peninsular India + surrounding seas */
const BBOX = { west: 66, east: 92, south: 2, north: 22 };

export async function GET() {
  try {
    const res = await fetch(
      'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson',
      { next: { revalidate: 300 } }
    );
    if (!res.ok) throw new Error(`usgs ${res.status}`);
    const gj = await res.json();

    const data: Quake[] = (gj.features ?? [])
      .filter((f: any) => {
        const [lon, lat] = f.geometry?.coordinates ?? [0, 0];
        return lon >= BBOX.west && lon <= BBOX.east && lat >= BBOX.south && lat <= BBOX.north;
      })
      .map((f: any) => ({
        id: f.id,
        mag: f.properties.mag ?? 0,
        place: f.properties.place ?? 'Unknown',
        time: f.properties.time,
        coords: [f.geometry.coordinates[0], f.geometry.coordinates[1]] as [number, number],
        depthKm: f.geometry.coordinates[2] ?? 0,
        url: f.properties.url,
      }));

    return NextResponse.json(
      { updatedAt: new Date().toISOString(), tier: 'live', source: 'USGS', data },
      { headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate=1800' } }
    );
  } catch (err) {
    const detail = process.env.NODE_ENV === 'production' ? undefined : String(err);
    return NextResponse.json({ error: 'usgs unavailable', detail }, { status: 502 });
  }
}
