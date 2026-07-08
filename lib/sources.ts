/**
 * Single source of truth for data provenance (S2).
 *
 * The info modal, the methodology page and any future "about the data" surface
 * all render from this one registry, so a source is described identically
 * everywhere and only has to be updated in one place.
 */
export type SourceTier = 'LIVE' | 'SAMPLE' | 'STATIC';

export interface DataSource {
  name: string;
  /** One-line description of what this source provides. */
  provides: string;
  tier: SourceTier;
  url: string;
}

export const DATA_SOURCES: DataSource[] = [
  { name: 'Open-Meteo', provides: 'Rainfall — observed + 72 h multi-model forecast (CC-BY 4.0)', tier: 'LIVE', url: 'https://open-meteo.com' },
  { name: 'GDACS (EC JRC / UN OCHA)', provides: 'Multi-hazard disaster alerts — floods, cyclones, earthquakes', tier: 'LIVE', url: 'https://www.gdacs.org' },
  { name: 'USGS', provides: 'Earthquakes, past 7 days, peninsular India region', tier: 'LIVE', url: 'https://earthquake.usgs.gov' },
  { name: 'NASA GIBS', provides: 'VIIRS true-colour satellite imagery, updated daily', tier: 'LIVE', url: 'https://www.earthdata.nasa.gov/engage/gibs' },
  { name: 'CARTO / OpenStreetMap', provides: 'Dark basemap — © OpenStreetMap contributors', tier: 'LIVE', url: 'https://carto.com/basemaps' },
  { name: 'Esri World Imagery', provides: 'Satellite basemap — © Esri, Maxar, Earthstar Geographics', tier: 'LIVE', url: 'https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9' },
  { name: 'GloFAS via Open-Meteo Flood API', provides: 'River discharge at CWC station sites — modelled, updated daily (Copernicus)', tier: 'LIVE', url: 'https://open-meteo.com/en/docs/flood-api' },
  { name: 'NRSC / ISRO Landslide Atlas', provides: 'District landslide susceptibility rankings (derived)', tier: 'STATIC', url: 'https://www.nrsc.gov.in' },
  { name: 'Census of India', provides: 'District population density (exposure factor)', tier: 'STATIC', url: 'https://censusindia.gov.in' },
  { name: 'Community GeoJSON (datameet)', provides: 'Kerala district boundaries', tier: 'STATIC', url: 'https://github.com/datameet' },
  { name: 'Curated facility list', provides: 'Hospitals, relief camps, fire stations', tier: 'SAMPLE', url: 'https://sdma.kerala.gov.in' },
];
