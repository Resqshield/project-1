/** Shared domain types for Vegvisir. */

export type Severity = 'green' | 'yellow' | 'orange' | 'red';

export type DataTier = 'live' | 'sample';

export interface District {
  id: string;
  name: string;
  /** [lon, lat] centroid */
  centroid: [number, number];
  /** people per km² (Census-derived, rounded) */
  popDensity: number;
  /** 0–1, derived from NRSC Landslide Atlas hotspot ranking for the Western Ghats */
  landslideSusceptibility: number;
  /** 0–1, derived from historical flood footprints (2018/2019) & low-lying terrain share */
  floodProneness: number;
  /** coastal district — exposed to INCOIS ocean hazards */
  coastal: boolean;
}

export interface RainPoint {
  districtId: string;
  /** mm accumulated, past 24 h (model reanalysis) */
  past24h: number;
  /** mm forecast next 24/48/72 h */
  next24h: number;
  next48h: number;
  next72h: number;
  /** hourly forecast series (mm) for the timeline, 72 entries */
  hourly: number[];
  /** ISO timestamp series start */
  hourlyStart: string;
}

export interface RiskScore {
  districtId: string;
  /** 0–100 composite */
  score: number;
  severity: Severity;
  drivers: {
    rain: number;
    landslide: number;
    flood: number;
    exposure: number;
  };
}

export interface HazardAlert {
  id: string;
  source: string;
  tier: DataTier;
  hazard: 'flood' | 'cyclone' | 'landslide' | 'earthquake' | 'rain' | 'ocean' | 'other';
  severity: Severity;
  title: string;
  description: string;
  area: string;
  coords?: [number, number];
  issuedAt: string;
  link?: string;
}

export interface Quake {
  id: string;
  mag: number;
  place: string;
  time: number;
  coords: [number, number];
  depthKm: number;
  url: string;
}

export interface RiverGauge {
  id: string;
  name: string;
  river: string;
  districtId: string;
  coords: [number, number];
  levelM: number;
  warningM: number;
  dangerM: number;
  trend: 'rising' | 'falling' | 'steady';
  tier: DataTier;
}

export interface Shelter {
  id: string;
  name: string;
  type: 'hospital' | 'shelter' | 'fire' | 'police';
  districtId: string;
  coords: [number, number];
  tier: DataTier;
}

export interface LayerMeta {
  id: LayerId;
  label: string;
  group: 'Hazards' | 'Water' | 'People & Infrastructure' | 'Imagery';
  tier: DataTier;
  description: string;
  defaultOn: boolean;
}

export type LayerId =
  | 'risk'
  | 'rainfall'
  | 'alerts'
  | 'quakes'
  | 'gauges'
  | 'infrastructure'
  | 'satellite';

export function severityRank(s: Severity): number {
  return { green: 0, yellow: 1, orange: 2, red: 3 }[s];
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  green: '#22c55e',
  yellow: '#eab308',
  orange: '#f97316',
  red: '#ef4444',
};
