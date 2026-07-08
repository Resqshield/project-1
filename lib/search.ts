import { DISTRICTS, DISTRICT_BY_ID } from './districts';
import { PLACES } from './places';
import { RIVER_STATIONS } from './riverStations';

export interface SearchHit {
  /** display label, e.g. "Munnar" */
  label: string;
  /** secondary context, e.g. "Idukki district" */
  sub: string;
  districtId: string;
  kind: 'district' | 'place' | 'river';
}

/** Combined gazetteer: districts + towns + river stations, built once. */
const INDEX: SearchHit[] = [
  ...DISTRICTS.map((d) => ({
    label: d.name,
    sub: 'District',
    districtId: d.id,
    kind: 'district' as const,
  })),
  ...PLACES.map((p) => ({
    label: p.name,
    sub: `${DISTRICT_BY_ID.get(p.districtId)?.name ?? ''} district`,
    districtId: p.districtId,
    kind: 'place' as const,
  })),
  ...RIVER_STATIONS.map((s) => ({
    label: s.name,
    sub: `${s.river} · ${DISTRICT_BY_ID.get(s.districtId)?.name ?? ''}`,
    districtId: s.districtId,
    kind: 'river' as const,
  })),
];

/** Pincode → district, for numeric lookups. */
const PIN_INDEX = new Map(
  PLACES.filter((p) => p.pin).map((p) => [p.pin!, p.districtId])
);

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

/**
 * Rank hits for a query: exact prefix beats substring; districts beat places
 * beat river stations on ties. Returns up to `limit` results.
 */
export function searchPlaces(query: string, limit = 8): SearchHit[] {
  const q = norm(query);
  if (!q) return [];

  // Pincode fast path
  if (/^\d{3,6}$/.test(q)) {
    const id = PIN_INDEX.get(q);
    if (id) return INDEX.filter((h) => h.districtId === id && h.kind === 'district');
  }

  const kindRank = { district: 0, place: 1, river: 2 } as const;
  return INDEX.map((h) => {
    const n = norm(h.label);
    let score = -1;
    if (n === q) score = 0;
    else if (n.startsWith(q)) score = 1;
    else if (n.includes(q)) score = 2;
    return { h, score };
  })
    .filter((x) => x.score >= 0)
    .sort((a, b) => a.score - b.score || kindRank[a.h.kind] - kindRank[b.h.kind] || a.h.label.length - b.h.label.length)
    .slice(0, limit)
    .map((x) => x.h);
}
