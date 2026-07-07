import type { RiverGauge, Shelter } from './types';

/**
 * SAMPLE tier data.
 *
 * Station/facility locations are real; readings are illustrative.
 * Production: replace via the CWC flood-forecast adapter (river levels) and
 * OSM/KSDMA extracts (facilities). The UI badges everything below as SAMPLE.
 */

export const RIVER_GAUGES: RiverGauge[] = [
  { id: 'g-aluva',    name: 'Aluva',           river: 'Periyar',       districtId: 'EKM', coords: [76.35, 10.11], levelM: 3.1, warningM: 5.5,  dangerM: 7.0,  trend: 'steady',  tier: 'sample' },
  { id: 'g-neelesw',  name: 'Neeleswaram',     river: 'Periyar',       districtId: 'EKM', coords: [76.45, 10.16], levelM: 12.4, warningM: 15.0, dangerM: 17.5, trend: 'rising',  tier: 'sample' },
  { id: 'g-kalady',   name: 'Kalady',          river: 'Periyar',       districtId: 'EKM', coords: [76.44, 10.17], levelM: 6.8, warningM: 9.0,  dangerM: 11.0, trend: 'steady',  tier: 'sample' },
  { id: 'g-kumbidi',  name: 'Kumbidi',         river: 'Bharathapuzha', districtId: 'PKD', coords: [76.05, 10.83], levelM: 2.4, warningM: 5.0,  dangerM: 6.5,  trend: 'falling', tier: 'sample' },
  { id: 'g-kuniyil',  name: 'Kuniyil',         river: 'Chaliyar',      districtId: 'KKD', coords: [75.93, 11.30], levelM: 5.2, warningM: 8.0,  dangerM: 10.0, trend: 'rising',  tier: 'sample' },
  { id: 'g-thumpamon',name: 'Thumpamon',       river: 'Achankovil',    districtId: 'PTA', coords: [76.70, 9.23],  levelM: 4.1, warningM: 6.0,  dangerM: 7.5,  trend: 'steady',  tier: 'sample' },
  { id: 'g-malakkara',name: 'Malakkara',       river: 'Pamba',         districtId: 'PTA', coords: [76.68, 9.34],  levelM: 5.9, warningM: 7.0,  dangerM: 8.5,  trend: 'rising',  tier: 'sample' },
  { id: 'd-idukki',   name: 'Idukki Reservoir',river: 'Periyar',       districtId: 'IDK', coords: [76.97, 9.84],  levelM: 2373, warningM: 2395, dangerM: 2403, trend: 'rising', tier: 'sample' },
  { id: 'd-mullaper', name: 'Mullaperiyar Dam',river: 'Periyar',       districtId: 'IDK', coords: [77.14, 9.53],  levelM: 39.6, warningM: 41.5, dangerM: 43.0, trend: 'steady', tier: 'sample' },
  { id: 'd-banasura', name: 'Banasura Sagar',  river: 'Kabini',        districtId: 'WYD', coords: [75.95, 11.67], levelM: 771,  warningM: 774,  dangerM: 776,  trend: 'steady', tier: 'sample' },
];

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
