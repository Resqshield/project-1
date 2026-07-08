import { NextResponse } from 'next/server';
import type { HazardAlert, Severity } from '@/lib/types';

export const revalidate = 300;

/**
 * GDACS RSS → normalized alerts, filtered to the wider South Asia region.
 * Dependency-free XML extraction (the feed structure is flat and stable).
 * Production roadmap: add an NDMA SACHET CAP adapter alongside this one.
 */
const REGION = { west: 60, east: 100, south: -5, north: 30 };

export async function GET() {
  try {
    const res = await fetch('https://www.gdacs.org/xml/rss.xml', {
      next: { revalidate: 300 },
      headers: { 'User-Agent': 'Vegvisir disaster dashboard (open-source)' },
    });
    if (!res.ok) throw new Error(`gdacs ${res.status}`);
    const xml = await res.text();

    const items = xml.split('<item>').slice(1);
    const data: HazardAlert[] = [];

    for (const item of items) {
      const get = (tag: string) => {
        const m = item.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
        return m ? decode(m[1].trim()) : '';
      };
      const point = get('georss:point').split(/\s+/).map(Number);
      const lat = point[0];
      const lon = point[1];
      if (!isFinite(lat) || !isFinite(lon)) continue;
      if (lon < REGION.west || lon > REGION.east || lat < REGION.south || lat > REGION.north) continue;

      const level = get('gdacs:alertlevel').toLowerCase();
      const type = get('gdacs:eventtype').toUpperCase();

      data.push({
        id: `gdacs-${get('gdacs:eventid') || data.length}`,
        source: 'GDACS',
        tier: 'live',
        hazard: hazardFor(type),
        severity: (['red', 'orange'].includes(level) ? level : level === 'green' ? 'green' : 'yellow') as Severity,
        title: get('title'),
        description: stripHtml(get('description')).slice(0, 400),
        area: get('gdacs:country') || 'Indian Ocean region',
        coords: [lon, lat],
        issuedAt: new Date(get('pubDate') || Date.now()).toISOString(),
        link: get('link'),
      });
    }

    return NextResponse.json(
      { updatedAt: new Date().toISOString(), tier: 'live', source: 'GDACS', data },
      { headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate=1800' } }
    );
  } catch (err) {
    const detail = process.env.NODE_ENV === 'production' ? undefined : String(err);
    return NextResponse.json({ error: 'gdacs unavailable', detail }, { status: 502 });
  }
}

function hazardFor(type: string): HazardAlert['hazard'] {
  switch (type) {
    case 'FL': return 'flood';
    case 'TC': return 'cyclone';
    case 'EQ': return 'earthquake';
    case 'DR': return 'other';
    case 'TS': return 'ocean';
    default: return 'other';
  }
}

function decode(s: string): string {
  return s
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function stripHtml(s: string): string {
  return s.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}
