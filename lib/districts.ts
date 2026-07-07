import type { District } from './types';

/**
 * Kerala's 14 districts.
 *
 * - centroid: approximate district centroid [lon, lat]
 * - popDensity: people/km², Census 2011 rounded (update when 2021+ figures publish)
 * - landslideSusceptibility: 0–1 qualitative ranking derived from the NRSC
 *   Landslide Atlas of India hotspot districts (Idukki, Wayanad, Palakkad,
 *   Malappuram, Kozhikode among India's most exposed) and Western Ghats terrain share.
 * - floodProneness: 0–1 qualitative ranking from 2018/2019 flood footprints
 *   (Kuttanad/Alappuzha, Ernakulam–Periyar basin, Thrissur–Chalakudy worst hit)
 *   and share of low-lying land.
 *
 * These static factors feed the composite risk index together with LIVE rainfall.
 */
export const DISTRICTS: District[] = [
  { id: 'TVM', name: 'Thiruvananthapuram', centroid: [77.0, 8.6],   popDensity: 1508, landslideSusceptibility: 0.35, floodProneness: 0.35, coastal: true },
  { id: 'KLM', name: 'Kollam',             centroid: [76.9, 8.9],   popDensity: 1056, landslideSusceptibility: 0.35, floodProneness: 0.45, coastal: true },
  { id: 'PTA', name: 'Pathanamthitta',     centroid: [76.9, 9.3],   popDensity: 452,  landslideSusceptibility: 0.55, floodProneness: 0.70, coastal: false },
  { id: 'ALP', name: 'Alappuzha',          centroid: [76.4, 9.4],   popDensity: 1501, landslideSusceptibility: 0.05, floodProneness: 0.95, coastal: true },
  { id: 'KTM', name: 'Kottayam',           centroid: [76.6, 9.6],   popDensity: 895,  landslideSusceptibility: 0.35, floodProneness: 0.70, coastal: false },
  { id: 'IDK', name: 'Idukki',             centroid: [77.0, 9.9],   popDensity: 254,  landslideSusceptibility: 0.95, floodProneness: 0.45, coastal: false },
  { id: 'EKM', name: 'Ernakulam',          centroid: [76.5, 10.0],  popDensity: 1069, landslideSusceptibility: 0.25, floodProneness: 0.85, coastal: true },
  { id: 'TSR', name: 'Thrissur',           centroid: [76.3, 10.5],  popDensity: 1026, landslideSusceptibility: 0.30, floodProneness: 0.75, coastal: true },
  { id: 'PKD', name: 'Palakkad',           centroid: [76.6, 10.8],  popDensity: 627,  landslideSusceptibility: 0.60, floodProneness: 0.45, coastal: false },
  { id: 'MLP', name: 'Malappuram',         centroid: [76.1, 11.1],  popDensity: 1157, landslideSusceptibility: 0.60, floodProneness: 0.55, coastal: true },
  { id: 'KKD', name: 'Kozhikode',          centroid: [75.9, 11.4],  popDensity: 1318, landslideSusceptibility: 0.60, floodProneness: 0.50, coastal: true },
  { id: 'WYD', name: 'Wayanad',            centroid: [76.1, 11.7],  popDensity: 384,  landslideSusceptibility: 0.90, floodProneness: 0.40, coastal: false },
  { id: 'KNR', name: 'Kannur',             centroid: [75.6, 11.9],  popDensity: 852,  landslideSusceptibility: 0.50, floodProneness: 0.40, coastal: true },
  { id: 'KSD', name: 'Kasaragod',          centroid: [75.1, 12.4],  popDensity: 654,  landslideSusceptibility: 0.45, floodProneness: 0.35, coastal: true },
];

export const DISTRICT_BY_ID = new Map(DISTRICTS.map((d) => [d.id, d]));

/** South India view bounds [[west, south], [east, north]] */
export const REGION_BOUNDS: [[number, number], [number, number]] = [
  [74.0, 7.8],
  [78.5, 13.0],
];

export const KERALA_CENTER: [number, number] = [76.4, 10.3];

/**
 * District boundary polygons are fetched at runtime (see lib/geo.ts) from a
 * public GeoJSON source and cached; if unavailable, the UI falls back to
 * centroid-based graduated circles so the platform degrades gracefully.
 */
export const DISTRICT_GEOJSON_URLS = [
  // Local copy if `npm run fetch:data` has been executed (fastest, offline-safe)
  '/data/districts.json',
  // Community-maintained Kerala district boundaries (datameet/geohacker lineage)
  'https://raw.githubusercontent.com/geohacker/kerala/master/geojsons/district.geojson',
];

/** Normalize various source property spellings to our district ids. */
export const NAME_TO_ID: Record<string, string> = {
  thiruvananthapuram: 'TVM',
  trivandrum: 'TVM',
  kollam: 'KLM',
  pathanamthitta: 'PTA',
  alappuzha: 'ALP',
  alleppey: 'ALP',
  kottayam: 'KTM',
  idukki: 'IDK',
  ernakulam: 'EKM',
  thrissur: 'TSR',
  trichur: 'TSR',
  palakkad: 'PKD',
  palghat: 'PKD',
  malappuram: 'MLP',
  kozhikode: 'KKD',
  calicut: 'KKD',
  wayanad: 'WYD',
  kannur: 'KNR',
  cannanore: 'KNR',
  kasaragod: 'KSD',
  kasargod: 'KSD',
};
