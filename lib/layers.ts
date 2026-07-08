import type { LayerMeta } from './types';

export const LAYERS: LayerMeta[] = [
  {
    id: 'risk',
    label: 'Composite risk index',
    group: 'Hazards',
    tier: 'live',
    description: 'District fill colour = current composite risk (live rainfall × terrain × exposure). Click a district for the breakdown.',
    defaultOn: true,
    legend: [
      { color: '#22c55e', label: 'Normal', shape: 'fill' },
      { color: '#eab308', label: 'Watch', shape: 'fill' },
      { color: '#f97316', label: 'Alert', shape: 'fill' },
      { color: '#ef4444', label: 'Severe', shape: 'fill' },
    ],
  },
  {
    id: 'rainfall',
    label: 'Rainfall (obs + 72 h forecast)',
    group: 'Hazards',
    tier: 'live',
    description: 'Glowing blue halos — size & brightness = rain intensity (mm/h) at the timeline hour. Press play on the timeline to watch systems move.',
    defaultOn: true,
    legend: [{ color: '#38bdf8', label: 'halo size = mm/h at timeline hour', shape: 'size' }],
  },
  {
    id: 'alerts',
    label: 'Hazard alerts',
    group: 'Hazards',
    tier: 'live',
    description: 'GDACS disaster events — dot colour = alert severity. Click a dot for details. Production target: NDMA SACHET CAP feed.',
    defaultOn: true,
    legend: [
      { color: '#22c55e', label: 'Green event', shape: 'dot' },
      { color: '#f97316', label: 'Orange', shape: 'dot' },
      { color: '#ef4444', label: 'Red', shape: 'dot' },
    ],
  },
  {
    id: 'quakes',
    label: 'Earthquakes (7 days)',
    group: 'Hazards',
    tier: 'live',
    description: 'USGS seismic events across peninsular India & nearby seas — circle size = magnitude. Click for details.',
    defaultOn: false,
    legend: [{ color: '#a78bfa', label: 'circle size = magnitude', shape: 'size' }],
  },
  {
    id: 'gauges',
    label: 'River discharge (GloFAS)',
    group: 'Water',
    tier: 'live',
    description: 'Live modelled river flow at CWC station sites — colour & size = today\'s discharge vs the 31-day median. Click a station for readings and the 7-day peak.',
    defaultOn: true,
    legend: [
      { color: '#22c55e', label: 'normal flow', shape: 'dot' },
      { color: '#f97316', label: '≥1.5× median', shape: 'dot' },
      { color: '#ef4444', label: '≥3× median', shape: 'dot' },
    ],
  },
  {
    id: 'infrastructure',
    label: 'Hospitals & shelters',
    group: 'People & Infrastructure',
    tier: 'sample',
    description: 'Key facilities for response planning — colour = facility type.',
    defaultOn: false,
    legend: [
      { color: '#f472b6', label: 'hospital', shape: 'dot' },
      { color: '#34d399', label: 'relief camp', shape: 'dot' },
      { color: '#fb923c', label: 'fire & rescue', shape: 'dot' },
    ],
  },
  {
    id: 'satellite',
    label: 'Satellite (NASA GIBS)',
    group: 'Imagery',
    tier: 'live',
    description: "Yesterday's VIIRS true-colour imagery draped over the map — cloud bands reveal active monsoon systems.",
    defaultOn: false,
    legend: [{ color: '#94a3b8', label: 'true-colour imagery overlay', shape: 'fill' }],
  },
];

export const LAYER_BY_ID = new Map(LAYERS.map((l) => [l.id, l]));
