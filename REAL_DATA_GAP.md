# REAL_DATA_GAP.md — ResQ Shield

> **CRITICAL CLARIFICATION**: India does **NOT** lack disaster warning infrastructure.
> This document accurately describes the existing ecosystem and precisely frames
> where ResQ Shield adds localization and integration value.

---

## India's Existing Warning Ecosystem

India has a robust and growing national disaster warning infrastructure:

### National Alerts & Forecasting
| System | Operator | Description |
|---|---|---|
| IFLOWS-India | IMD / CWC / MHA / NDMA | Integrated Flood Early Warning System; multi-river basin coverage |
| IMD District-level Warnings | IMD | Daily/3-hourly weather warnings to district level; color-coded alerts |
| IMD Multi-hazard Early Warning | IMD | Heat wave, cold wave, cyclone, heavy rain alerts |
| NTEWS (National Tsunami EWS) | INCOIS | Indian Ocean tsunami warning |
| Cyclone warnings | IMD | Bay of Bengal / Arabian Sea track forecasts |

### River Monitoring
| System | Operator | Description |
|---|---|---|
| CWC Flood Forecasting | Central Water Commission | ~950 gauge stations, flood level alerts on ~250+ forecasting stations |
| WIRIS | CWC | Web-based integrated river information system; real-time stage/discharge |
| RFFS | CWC | River forecast and flood simulation |
| GloFAS India | EU Copernicus / CWC | Global Flood Awareness System; extended-range ensemble flood forecasting |

### Landslide
| System | Operator | Description |
|---|---|---|
| Landslide Early Warning System | NIDM / GSI / IMD | Pilot operational systems in Uttarakhand, HP, NE India |
| National Landslide Susceptibility Mapping | GSI | Multi-state susceptibility zones |
| Bhunidhi / Bhuvan | ISRO / NRSC | Satellite-based disaster mapping; near-real-time SAR flood mapping |

### Dissemination
| System | Operator | Description |
|---|---|---|
| Common Alerting Protocol (CAP) | NDMA / DM Authorities | Standardized alert format for multi-channel dissemination |
| NDMA app / alerts | NDMA | Direct-to-citizen mobile alerts |
| State DMAs | 36 State/UT DM Authorities | Local last-mile dissemination |

---

## Where ResQ Shield Adds Value

ResQ Shield is NOT an alternative to national systems. It is a **research prototype** targeting the following specific gaps:

### 1. Village / Catchment Localization
**Gap**: National systems typically warn at district or sub-district level (e.g. "Chamoli district: Red Alert").
A district may span 3,000–15,000 km² and contain 500–3,000 villages with very different terrain, drainage, and exposure.

**Target**: Link hazard assessment to individual LGD villages via catchment intersection, providing village-specific context rather than district-level uniform alerts.

### 2. Upstream / Downstream Catchment Context
**Gap**: District-level warnings don't communicate which villages are upstream vs. downstream of a failing slope or rising river — critically different risk profiles.

**Target**: Catchment-aware routing that identifies upstream contributing areas and downstream inundation paths for specific village clusters.

### 3. Static + Dynamic Separation
**Gap**: Many operational models blend structural susceptibility and real-time trigger in ways that are opaque to end users and difficult to audit.

**Target**: Explicit separation of:
- Static susceptibility (WHERE: terrain, geology, historical footprint)
- Dynamic trigger (WHEN: rainfall, river level, antecedent conditions)
This allows clear communication: "This village has HIGH structural susceptibility; current rainfall has not yet reached trigger threshold."

### 4. Multimodal Fusion with Explicit Data Gaps
**Gap**: Operational systems may have data gaps in remote/poorly-gauged areas but may not propagate uncertainty explicitly.

**Target**: Explicit `observation_confidence` schema — every prediction carries rainfall_age, river_station_distance, soil_data_coverage flags. Missing data is not imputed to zero.

### 5. Graceful Degradation
**Gap**: When dynamic data (rainfall, river level) is unavailable (network outage, remote area), many systems either fail or silently degrade without notification.

**Target**: Explicit fallback: static susceptibility only when dynamic unavailable, with clear `dynamic_data_coverage=0.0` flag. Users know they're seeing structural risk, not triggered risk.

### 6. Cross-Region Validation
**Gap**: Many published ML-based flood/landslide models use random 80/20 splits that inflate metrics due to spatial autocorrelation, giving false confidence in cross-region generalization.

**Target**: Mandatory Leave-One-Region-Out (LORO) validation with geographically distinct hold-out regions. Models that fail LORO cross-validation are not deployed.

### 7. Local Impact Mapping
**Gap**: Hazard extent (inundation polygon, failure zone) → village impact linkage is often manual and delayed in post-event assessments.

**Target**: Systematic village ↔ catchment ↔ hazard-zone intersection to pre-compute exposure fractions, enabling rapid impact estimates during events.

---

## What ResQ Shield Does NOT Claim to Do

- ❌ Replace IMD, CWC, or NDMA operational warning systems
- ❌ Provide real-time alerts faster than national systems
- ❌ Operate with better meteorological data than IMD (same underlying data)
- ❌ Have been validated against real disasters (not yet — Phase 1 is admin foundation only)
- ❌ Be an operational system (currently a research prototype)
- ❌ Cover all hazard types (focus: riverine flood + rainfall-triggered landslide)

---

## Honest Assessment of Limitations

### Data Gaps (as of Phase 1)
| Gap | Impact | Mitigation |
|---|---|---|
| No village-level historical flood labels | Cannot train village-level flood model | Use catchment-level ISRO inundation data; spatial join to villages |
| CWC gauge coverage sparse (NE, remote Himalayas) | Poor river monitoring in highest-risk areas | Explicit station_distance flag; satellite-derived river levels (MODIS, SAR) |
| IMD station density lowest in mountains | Rainfall estimates least accurate where risk is highest | IMERG satellite; quantify uncertainty |
| GSI landslide inventory incomplete | Training data biased toward accessible areas | LORO validation; do not claim national coverage |
| Sub-district/block-level geometry unavailable without login | Cannot do fine-grained spatial joins until LGD data ingested | Phase 1 admin foundation addresses this |
| No real-time API integration yet | Prototype is post-event / research, not operational | Future phase |

### Technical Limitations
| Limitation | Notes |
|---|---|
| Spatial resolution mismatch | DEM 30m vs rainfall 0.1° (~11km) vs soil moisture 36km |
| Temporal coverage | Historical events sparse, biased toward well-documented areas |
| Class imbalance | Flood/landslide events rare; requires careful sample strategy |
| Boundary changes | Post-2014 district/state splits (Telangana, Ladakh) affect historical joins |
| Transliteration | Village names in Hindi/regional scripts → ASCII transliteration inconsistencies |

---

## Phase 1 Status Summary

**Phase 1 (current) = Administrative / Geospatial Foundation only.**

- ✅ Directory structure created (`data_real/`, `real_pipeline/`)
- ✅ LGD ingest scripts ready (pending manual download or data.gov.in access)
- ✅ Boundary ingest scripts ready (GADM download documented)
- ✅ Admin crosswalk (LGD ↔ Census 2011 ↔ GADM) designed
- ✅ Admin validation suite implemented
- ✅ Village search prototype implemented
- ✅ Terrain pilot script ready (Copernicus GLO-30, public AWS)
- ✅ Training strategy designed (no models trained)
- ✅ Observation confidence schema defined (no fake values)
- ✅ Data sources documented
- ✅ Download manifest created
- ✅ Synthetic MVP fully preserved and operational
- ❌ LGD nationwide data: MANUAL_REQUIRED (see data_real/admin/processed/lgd_status.json)
- ❌ GADM boundaries: MANUAL_REQUIRED (download gadm41_IND.gpkg ~220 MB)
- ❌ Terrain pilot: ready to run (Copernicus GLO-30 public, no auth needed)
- ❌ Real ML training: NOT started (Phase 2+)

---

*This document was generated as part of ResQ Shield Real Data Phase 1.*
*Date: 2026-09-16*
