import type { Shelter } from './types';

/**
 * SAMPLE tier data — facility locations are real; the curated list is
 * illustrative. Production: OSM extract + KSDMA camp registry.
 * (River data graduated to LIVE — see lib/riverStations.ts + /api/rivers.)
 */

export const SHELTERS: Shelter[] = [
  { id: 's-mch-tvm', name: 'Govt Medical College, Thiruvananthapuram', type: 'hospital', districtId: 'TVM', coords: [76.93, 8.52],  tier: 'sample' },
  { id: 's-mch-ekm', name: 'Ernakulam General Hospital',               type: 'hospital', districtId: 'EKM', coords: [76.28, 9.98],  tier: 'sample' },
  { id: 's-mch-kkd', name: 'Govt Medical College, Kozhikode',          type: 'hospital', districtId: 'KKD', coords: [75.83, 11.27], tier: 'sample' },
  { id: 's-mch-ktm', name: 'Govt Medical College, Kottayam',           type: 'hospital', districtId: 'KTM', coords: [76.55, 9.61],  tier: 'sample' },
  { id: 's-mch-tsr', name: 'Govt Medical College, Thrissur',           type: 'hospital', districtId: 'TSR', coords: [76.22, 10.53], tier: 'sample' },
  { id: 's-rc-alp',  name: 'Alappuzha Relief Camp Cluster (Kuttanad)', type: 'shelter',  districtId: 'ALP', coords: [76.42, 9.38],  tier: 'sample' },
  { id: 's-rc-idk',  name: 'Idukki Relief Camp (Cheruthoni)',          type: 'shelter',  districtId: 'IDK', coords: [76.98, 9.86],  tier: 'sample' },
  { id: 's-rc-wyd',  name: 'Wayanad Relief Camp (Meppadi)',            type: 'shelter',  districtId: 'WYD', coords: [76.13, 11.55], tier: 'sample' },
  { id: 's-fs-ekm',  name: 'Fire & Rescue Station, Kochi',             type: 'fire',     districtId: 'EKM', coords: [76.27, 9.97],  tier: 'sample' },
  { id: 's-fs-kkd',  name: 'Fire & Rescue Station, Kozhikode',         type: 'fire',     districtId: 'KKD', coords: [75.78, 11.25], tier: 'sample' },
];
