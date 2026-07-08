/**
 * Monitored river points — real CWC gauging-station locations on Kerala's
 * flood-critical rivers. Live discharge comes from the GloFAS model via the
 * Open-Meteo Flood API (keyless, CC-BY); the station grid cell is sampled at
 * these coordinates.
 */
export interface RiverStation {
  id: string;
  name: string;
  river: string;
  districtId: string;
  /** [lon, lat] */
  coords: [number, number];
}

export const RIVER_STATIONS: RiverStation[] = [
  { id: 'r-aluva',     name: 'Aluva',       river: 'Periyar',       districtId: 'EKM', coords: [76.35, 10.11] },
  { id: 'r-neelesw',   name: 'Neeleswaram', river: 'Periyar',       districtId: 'EKM', coords: [76.45, 10.16] },
  { id: 'r-kumbidi',   name: 'Kumbidi',     river: 'Bharathapuzha', districtId: 'PKD', coords: [76.05, 10.83] },
  { id: 'r-kuniyil',   name: 'Kuniyil',     river: 'Chaliyar',      districtId: 'KKD', coords: [75.93, 11.30] },
  { id: 'r-thumpamon', name: 'Thumpamon',   river: 'Achankovil',    districtId: 'PTA', coords: [76.70, 9.23] },
  { id: 'r-malakkara', name: 'Malakkara',   river: 'Pamba',         districtId: 'PTA', coords: [76.68, 9.34] },
  { id: 'r-kidangoor', name: 'Kidangoor',   river: 'Meenachil',     districtId: 'KTM', coords: [76.62, 9.68] },
  { id: 'r-vandiper',  name: 'Vandiperiyar',river: 'Periyar (upper)', districtId: 'IDK', coords: [77.09, 9.57] },
  { id: 'r-mananthav', name: 'Mananthavady',river: 'Kabini',        districtId: 'WYD', coords: [76.00, 11.80] },
  { id: 'r-kallada',   name: 'Enathu',      river: 'Kallada',       districtId: 'KLM', coords: [76.68, 9.02] },
];
