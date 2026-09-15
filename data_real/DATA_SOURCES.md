# ResQ Shield — Data Sources

> **DATA TYPE**: This directory (`data_real/`) contains **REAL OFFICIAL DATA** from government and authoritative sources.
> It is **completely separate** from `data/` which holds synthetic/demo data for the MVP.
> **NEVER mix synthetic and real data.**

---

## Administrative / Geospatial Foundation

### LGD — Local Government Directory

| Field | Value |
|---|---|
| Dataset | India Administrative Hierarchy (State → District → Sub-district → Block → GP → Village) |
| Provider | Ministry of Panchayati Raj, Government of India |
| Official URL | https://lgdirectory.gov.in/ |
| Variables | LGD codes and names for all 6 admin levels; village status (Active/Deleted/Merged) |
| Spatial resolution | Point (village centroid, where available) |
| Temporal coverage | Continuously updated; last known bulk snapshot: 2023 |
| Access method | Login required for full bulk export (OTP via Aadhaar/mobile); data.gov.in periodic snapshots (open) |
| License | Government of India Open Data License v1.0 (https://data.gov.in/sites/default/files/Gazette_Notification_OGD_Policy_0.pdf) |
| Raw path | `data_real/admin/raw/lgd_national_villages.csv` (MANUAL_REQUIRED) |
| Processing script | `real_pipeline/admin/ingest_lgd.py` |
| Limitations | Bulk export requires login. Codes change when admin boundaries are reorganized (new states/districts). Sub-district/block mapping is not always consistent across states. |

### data.gov.in — LGD Village Snapshot (Open)

| Field | Value |
|---|---|
| Dataset | All Villages LGD (periodic snapshot) |
| Provider | data.gov.in (National Data & Analytics Platform) |
| Official URL | https://data.gov.in/resource/all-villages-lgd |
| API URL | https://api.data.gov.in/resource/13c04e89-02aa-4e87-8f0e-5d11d84a1e9b |
| Variables | State, District, Sub-district, Block, GP, Village codes and names |
| Access method | Open API (paginated, 5000 records/page; ~130 pages for full dataset) |
| License | NDSAP / GoI Open Data License |
| Raw path | API — no raw file needed for sample; `data_real/admin/raw/lgd_national_villages.csv` for bulk |
| Processing script | `real_pipeline/admin/ingest_lgd.py --source datagov` |
| Limitations | Snapshot may lag LGD live data by weeks/months. API key may be required for high-volume requests. |

---

### GADM — Global Administrative Areas (Research Use)

| Field | Value |
|---|---|
| Dataset | GADM India Administrative Boundaries v4.1 |
| Provider | University of California Davis / GADM |
| Official URL | https://gadm.org/download_country.html |
| Download URL | https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_IND.gpkg |
| Variables | State, District, Sub-district polygon boundaries; GADM codes and names |
| Spatial resolution | ~1:250,000 to 1:1,000,000 (varies by level) |
| Temporal coverage | Based on ~2018–2022 boundaries |
| Access method | Free direct download (~220 MB GeoPackage); no login |
| License | Free for non-commercial academic / research use. NOT for redistribution or commercial use. |
| Raw path | `data_real/admin/raw/gadm41_IND.gpkg` (MANUAL_REQUIRED — download manually) |
| Processing script | `real_pipeline/admin/ingest_boundaries.py` |
| Limitations | GADM codes differ from LGD codes — crosswalk required. Not an authoritative GoI source. Boundary accuracy varies. Sub-district coverage incomplete for some regions. |

### Datameet India Maps

| Field | Value |
|---|---|
| Dataset | Census 2011 District and State Boundaries |
| Provider | Datameet community (sourced from Census of India / GoI data) |
| Official URL | https://github.com/datameet/maps |
| Variables | State and district polygon boundaries; Census 2011 codes |
| Access method | Free GitHub download (Shapefiles) |
| License | Community attribution required; see repo for details |
| Raw path | `data_real/admin/raw/datameet_districts/` (MANUAL_REQUIRED) |
| Processing script | `real_pipeline/admin/ingest_boundaries.py` |
| Limitations | Based on Census 2011 — does not reflect post-2011 boundary changes (Telangana, Ladakh, etc.). Census codes differ from LGD codes. |

### Survey of India (SoI)

| Field | Value |
|---|---|
| Dataset | Administrative boundary maps |
| Provider | Survey of India, Government of India |
| Official URL | https://surveyofindia.gov.in/, https://nsdi.gov.in/ |
| Variables | State, district, sub-district boundaries (authoritative) |
| Access method | **MANUAL_REQUIRED** — purchase or request via SoI; NSDI portal registration; some Open Series Maps free |
| License | GoI copyright; terms vary by product |
| Raw path | `data_real/admin/raw/soi_districts.gpkg` (MANUAL_REQUIRED) |
| Limitations | Most boundary layers require purchase or formal request. Open Series Maps (OSM) are terrain-focused, not administrative. |

---

## Terrain / Elevation

### Copernicus GLO-30 DEM (Recommended)

| Field | Value |
|---|---|
| Dataset | Copernicus Digital Elevation Model — Global 30m (GLO-30 Public) |
| Provider | European Space Agency / Copernicus |
| Official URL | https://spacedata.copernicus.eu/ |
| Public AWS | s3://copernicus-dem-30m/ (public bucket, no auth) |
| Variables | Surface elevation (metres), 1 arc-second (~30m) resolution |
| Spatial resolution | 1 arc-second (~30m at equator) |
| Temporal coverage | Based on TanDEM-X mission 2011–2015, released 2021 |
| Access method | Public AWS S3 (no credentials); HTTPS direct download |
| License | Free for any use (GLO-30 Public release) |
| Raw path | `data_real/terrain/raw/N<lat>E<lon>_glo30.tif` |
| Processing script | `real_pipeline/terrain/ingest_dem_pilot.py --source copernicus_glo30` |
| Limitations | ~17–25 MB per 1°×1° tile; India-wide ~250 tiles (~6 GB). Download pilot tiles only. Voids over water and some high-slope areas. |

### SRTM 1 Arc-Second Global (30m)

| Field | Value |
|---|---|
| Dataset | Shuttle Radar Topography Mission 1 Arc-Second Global |
| Provider | USGS / NASA |
| Official URL | https://earthexplorer.usgs.gov/ |
| Download URL | https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/ |
| Variables | Surface elevation (metres), HGT format |
| Spatial resolution | 1 arc-second (~30m) |
| Temporal coverage | February 2000 (single acquisition) |
| Access method | **MANUAL_REQUIRED** — free but requires USGS EarthExplorer account (register at urs.earthdata.nasa.gov) |
| License | Public domain (NASA) |
| Raw path | `data_real/terrain/raw/<tile_name>.hgt` |
| Limitations | Acquisition 2000 — does not reflect land cover changes. Some voids in steep terrain. HGT format requires special parsing. |

---

## Rainfall

### IMD Gridded Rainfall (1° / 0.25°)

| Field | Value |
|---|---|
| Dataset | IMD Daily Gridded Rainfall (1901–present) |
| Provider | India Meteorological Department |
| Official URL | https://www.imd.gov.in/pages/rainfall_main.php |
| Variables | Daily rainfall (mm), district-level and gridded products |
| Spatial resolution | 1° × 1° (historical); 0.25° (post-1971) |
| Temporal coverage | 1901–present |
| Access method | **MANUAL_REQUIRED** — IMD data portal; some products require formal request. Open access products at imdpune.gov.in |
| License | GoI; commercial redistribution restricted |
| Raw path | `data_real/rainfall/imd/` (MANUAL_REQUIRED) |
| Limitations | Sub-district level not available. Station coverage sparse in remote areas. |

### GPM IMERG (30-minute, 0.1° global)

| Field | Value |
|---|---|
| Dataset | Global Precipitation Measurement IMERG Final Run |
| Provider | NASA / JAXA |
| Official URL | https://gpm.nasa.gov/data/imerg |
| Access URL | https://search.earthdata.nasa.gov/ |
| Variables | Precipitation rate (mm/hr), 30-minute intervals, 0.1° grid |
| Spatial resolution | 0.1° × 0.1° (~11 km) |
| Temporal coverage | 2000–present |
| Access method | **MANUAL_REQUIRED** — NASA Earthdata account (free); large data volumes |
| License | Open (NASA) |
| Raw path | `data_real/rainfall/imerg/` |
| Limitations | Satellite-derived; can miss orographic enhancement in steep terrain. Full historical archive is TB-scale. Download event-windows only. |

---

## River / Hydrology

### CWC Real-time River Data

| Field | Value |
|---|---|
| Dataset | River level, discharge at CWC gauge stations |
| Provider | Central Water Commission, GoI |
| Official URL | https://cwc.gov.in/ , http://www.india-water.gov.in/ |
| Variables | River stage (m above datum), discharge (cumec), flood alert level |
| Spatial resolution | Station-point (~950 gauging stations nationwide) |
| Temporal coverage | Real-time + historical archives |
| Access method | **MANUAL_REQUIRED** — some data via WIRIS portal; bulk historical requires formal request |
| Raw path | `data_real/rivers/cwc/` |
| Limitations | Not all rivers gauged. Station locations not always geolocated precisely in public data. Historical archives behind formal access. |

### HydroSHEDS / HydroBASINS

| Field | Value |
|---|---|
| Dataset | HydroBASINS Asia sub-basins (Pfafstetter system) |
| Provider | WWF / USGS HydroSHEDS |
| Official URL | https://www.hydrosheds.org/ |
| Variables | Watershed delineation, stream network, basin hierarchy |
| Spatial resolution | 15 arc-second (~500m) conditioned DEM |
| Access method | Free registration download |
| Raw path | `data_real/hydrology/catchments/` (MANUAL_REQUIRED) |
| License | Free for non-commercial research; commercial license for other uses |
| Limitations | Based on SRTM; not derived from Indian survey data. Pfafstetter codes differ from CWC basin codes. |

---

## Soil / Land Cover

### ERA5-Land Soil Moisture

| Field | Value |
|---|---|
| Dataset | ERA5-Land hourly soil volumetric water content |
| Provider | ECMWF / Copernicus Climate Change Service |
| Official URL | https://cds.climate.copernicus.eu/ |
| Variables | Soil moisture (4 layers), skin temperature, evaporation |
| Spatial resolution | 0.1° × 0.1° (~11 km) |
| Temporal coverage | 1950–present |
| Access method | **MANUAL_REQUIRED** — free CDS account; CDS API (cdsapi) for bulk download |
| Raw path | `data_real/soil_moisture/era5_land/` |
| Limitations | Reanalysis (not direct observation). 0.1° resolution too coarse for village-level. Large files. |

### NASA SMAP Level-3 Soil Moisture

| Field | Value |
|---|---|
| Dataset | SMAP L3 Daily Global 36km / 9km |
| Provider | NASA JPL |
| Official URL | https://smap.jpl.nasa.gov/ |
| Access URL | https://search.earthdata.nasa.gov/ |
| Variables | Surface soil moisture (0–5 cm), volumetric water content |
| Spatial resolution | 36 km (passive) / 9 km (enhanced) |
| Temporal coverage | 2015–present |
| Access method | **MANUAL_REQUIRED** — NASA Earthdata account |
| Raw path | `data_real/soil_moisture/smap/` |
| Limitations | 36 km resolution; gaps from orbital revisit period (~2–3 days). |

### ESA WorldCover 2021

| Field | Value |
|---|---|
| Dataset | ESA WorldCover 10m Global Land Cover 2021 |
| Provider | ESA / Sinergise |
| Official URL | https://esa-worldcover.org/ |
| AWS | s3://esa-worldcover/ (public) |
| Variables | 11 land cover classes at 10m resolution (GeoTIFF) |
| Spatial resolution | 10m |
| Access method | Free, no login; public AWS S3 bucket |
| Raw path | `data_real/landcover/worldcover/` |
| License | CC BY 4.0 |
| Limitations | Single year (2021). Large files (~15 TB global; tile-wise for India). |

---

## Events / Historical Disasters

### NDMA / NIDM Disaster Database

| Field | Value |
|---|---|
| Dataset | National disaster event records |
| Provider | NDMA (National Disaster Management Authority) / NIDM |
| Official URL | https://ndma.gov.in/ , https://nidm.gov.in/ |
| Variables | Event type, date, state, district, affected area, casualties |
| Access method | Some open data; detailed records **MANUAL_REQUIRED** |
| Raw path | `data_real/events/flood/` , `data_real/events/landslide/` |
| Limitations | Village-level event mapping not consistently available. Reporting inconsistencies across states. |

### ISRO Bhuvan Flood / Landslide Inventory

| Field | Value |
|---|---|
| Provider | ISRO Bhuvan / NRSC |
| URL | https://bhuvan.nrsc.gov.in/ |
| Variables | Satellite-mapped inundation extents; some landslide inventories |
| Access method | Some open; detailed products **MANUAL_REQUIRED** via Bhuvan portal |
| Raw path | `data_real/events/flood/` |

### GSI National Landslide Susceptibility Mapping

| Field | Value |
|---|---|
| Provider | Geological Survey of India |
| URL | https://www.gsi.gov.in/ |
| Variables | Landslide susceptibility zones; inventory points |
| Access method | Some products open; detailed shapefiles **MANUAL_REQUIRED** |
| Raw path | `data_real/events/landslide/` |

---

## Notes on Missing Data Policy

> **MISSING DATA ≠ ZERO RISK.**
>
> All null values in `data_real/` represent genuinely missing or unavailable data.
> They must NEVER be silently filled with zero, as zero risk and missing data are fundamentally different.
> All models must propagate null/coverage flags.
