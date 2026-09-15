# ResQ Shield — Training Strategy (Real Data Phase)

> **STATUS**: Design document only.
> **NO real ML models are trained in Phase 1.**
> This document defines the planned training approach for Phase 2+.

---

## Overview

The ResQ Shield real-data training strategy separates:
- **STATIC** features: terrain, drainage, geology, historical land cover, historical inundation footprints
- **DYNAMIC** features: rainfall, river level, soil moisture, antecedent conditions

This separation is fundamental because:
1. Static features define *where* an area is susceptible (structural risk).
2. Dynamic features define *when* hazard conditions are exceeded (trigger conditions).
3. A model that mixes them without clear labelling will not generalize across unseen events.

---

## Target Spatial Unit

**Primary unit: Village (LGD village_code) intersected with catchment/slope unit**

- Villages are the impact/output unit for community-level warnings.
- Hazard processes (floods, landslides) operate on physical units: river reaches, catchments, slope units.
- Training samples should be constructed as: **physical_unit × time_window** (not "one village = one sample").

**Multi-scale approach:**
| Scale | Unit | Purpose |
|---|---|---|
| 1–10 km² | Slope unit / sub-catchment | Landslide susceptibility, trigger modelling |
| 10–100 km² | Catchment / watershed | Flood routing, hydrological response |
| Village | LGD village | Impact attribution, warning dissemination |

---

## Flood Model

### Static Features (WHERE susceptibility exists)
| Feature | Source | Resolution | Notes |
|---|---|---|---|
| Elevation | Copernicus GLO-30 / SRTM | 30m | Absolute and relative elevation |
| Slope | DEM-derived | 30m | Low slope → overland flow accumulation |
| Flow accumulation | DEM-derived (D8/D-inf) | 30m | Upstream contributing area |
| Distance to drainage | DEM-derived | 30m | Distance to nearest stream |
| Relative elevation | DEM-derived (HAND: Height Above Nearest Drainage) | 30m | Key flood inundation predictor |
| River distance | GIS (CWC/OpenStreetMap rivers) | Vector | Proximity to named rivers |
| Historical inundation | ISRO Bhuvan / SAR products | 30–100m | Percent of events historically flooded |
| Land cover | ESA WorldCover 2021 | 10m | Urban/forest/agriculture affects runoff |
| Soil type / permeability | ICAR / FAO soil grids | ~1 km | Affects infiltration capacity |
| Drainage density | DEM-derived | — | Drainage network density |

### Dynamic Features (WHEN conditions trigger)
| Feature | Source | Temporal resolution | Notes |
|---|---|---|---|
| 30-min rainfall | IMD or GPM IMERG | 30 min | Convective trigger for flash floods |
| 1-hour rainfall | IMD / IMERG | 1h | Flash flood critical |
| 3-hour rainfall | IMD / IMERG | 3h | — |
| 6-hour rainfall | IMD / IMERG | 6h | — |
| 24-hour rainfall | IMD / IMERG | 24h | Sustained rainfall input |
| Antecedent 3-day rainfall | IMD / IMERG | 24h | Pre-event soil saturation proxy |
| Antecedent 7-day rainfall | IMD / IMERG | 24h | — |
| River level | CWC real-time / WIRIS | 15 min / 1h | Absolute and change rate |
| River level rate of rise | CWC derived | 1h | Critical early warning indicator |
| Soil moisture (satellite) | SMAP / ERA5-Land | 24h–3h | Soil saturation state |
| Soil wetness index (TWI) | DEM-derived static + rainfall dynamic | — | Hybrid indicator |

---

## Landslide Model

### Static Features (WHERE slope failure susceptibility exists)
| Feature | Source | Resolution | Notes |
|---|---|---|---|
| Slope (degrees) | DEM-derived | 30m | Primary mechanical control |
| Aspect | DEM-derived | 30m | Exposure, vegetation, moisture |
| Curvature (plan / profile) | DEM-derived | 30m | Concavity increases water convergence |
| Elevation | DEM | 30m | — |
| Topographic Wetness Index | DEM-derived | 30m | Steady-state saturation proxy |
| Historical landslide inventory | GSI / NIDM / ISRO | Point/polygon | Where failures occurred previously |
| Geology / lithology | GSI bedrock map | ~1:50k–1:250k | Rock type, discontinuities |
| Soil type / depth | ICAR / FAO | ~1 km | Soil thickness over bedrock |
| Land cover | ESA WorldCover | 10m | Forest root reinforcement |
| Land cover change | Multi-year WorldCover | 10m | Deforestation increases risk |
| Road / cut slope | OSM / NHAI | Vector | Engineering cuts destabilize slopes |

### Dynamic Features (WHEN rainfall triggers failure)
| Feature | Source | Temporal resolution | Notes |
|---|---|---|---|
| Recent 1-hour rainfall | IMD / IMERG | 1h | Rapid intensity trigger |
| Recent 6-hour rainfall | IMD / IMERG | 6h | — |
| Recent 24-hour rainfall | IMD / IMERG | 24h | — |
| Antecedent 3-day rainfall | IMD / IMERG | 24h | Pre-wetting of soil |
| Antecedent 7–15 day rainfall | IMD / IMERG | 24h | Deep pore pressure buildup |
| Antecedent 30-day rainfall | IMD / IMERG | 24h | Slow drainage systems |
| Static susceptibility score | Model output | — | Combined with dynamic trigger |
| Soil moisture anomaly | SMAP / ERA5-Land | 24h | Deviation from climatology |

---

## Sample Construction (Time × Space)

**Critical design rule: training samples are not "one village = one sample".**

Proposed sample unit: `(spatial_unit_id, event_window_start, event_window_end)`

### For Flood:
- Spatial unit: CWC gauge sub-basin or DEM-derived catchment
- Event window: ±72 hours around peak river level or identified flood event
- Label: Binary (flooded / not-flooded) from ISRO satellite inundation maps or NDMA records
- Negative samples: same spatial units during non-flood periods

### For Landslide:
- Spatial unit: 1 km² slope unit (derived from DEM and curvature analysis)
- Event window: Within 72 hours after rainfall trigger
- Label: Binary (landslide / no-landslide) from GSI inventory or NDMA records
- Negative samples: same slope units during non-triggering periods

---

## Validation Strategy

### Critical Principle: No Random Train/Test Splits

Random 80/20 splits are **not acceptable** for geospatial hazard models because:
- Nearby spatial units are highly correlated (spatial autocorrelation).
- A model trained on villages near Chamoli can trivially "predict" risk at another village 2 km away.
- This inflates evaluation metrics without reflecting real operational value.

### Required Validation Approaches (in priority order):

| Method | Description | Why Required |
|---|---|---|
| **Leave-one-region-out (LORO)** | Train on all regions except one; test on the held-out region | Tests generalization to unseen geographies |
| **Temporal hold-out** | Train on events before year T; test on events after T | Tests generalization to future events |
| **Block cross-validation** | Spatial blocks assigned to folds (no adjacent training/test cells) | Reduces spatial autocorrelation |
| Leave-event-out | Leave out a specific major disaster event | Tests that model wasn't "taught" the event |

**At minimum, LORO on major region groupings:**
- Western Himalayas (Uttarakhand + Himachal)
- Eastern Himalayas (Sikkim + Arunachal + Assam hills)
- Northeast India
- Western Ghats
- Central India (Odisha, Chhattisgarh plains)
- Peninsular rivers (Godavari, Krishna basins)

---

## Evaluation Metrics

**Accuracy is NOT the headline metric.** Rare event classes + class imbalance make accuracy misleading.

### Required Metrics (in priority order):

| Metric | Why Critical |
|---|---|
| **PR-AUC** (Precision-Recall Area Under Curve) | Robust to class imbalance; primary metric |
| **Recall / POD** (Probability of Detection) | Minimizing missed dangerous events |
| **FAR** (False Alarm Ratio) | Warning fatigue; too many false alarms erode trust |
| **Precision** | Fraction of alerts that were real events |
| **F1 / CSI** (Critical Success Index) | Balanced trade-off |
| **Brier Score** | Probabilistic calibration |
| **Calibration curve** | Are probability outputs actually calibrated? |
| **Lead time analysis** | At what lead time can events be predicted? |
| **Missed-dangerous-event rate** | Fraction of high-impact events missed entirely |

### NOT acceptable as primary metric:
- Accuracy (biased by class imbalance)
- AUC-ROC alone (doesn't reflect precision at low threshold)

---

## Data Volume Considerations

| Level | Approx. flood events | Approx. landslide events | Notes |
|---|---|---|---|
| Nationwide (1980–2024) | ~500–2000 district-season events | ~10k–50k inventory points | NDMA/ISRO/GSI sources |
| Village-season | Very sparse | Very sparse | Most villages: 0 events |
| Class imbalance ratio | ~1:50 to 1:500 | ~1:100 to 1:1000 | Requires careful sampling |

**Class imbalance strategy:**
- Focal loss / class weighting in tree models
- Hard negative mining (select challenging negative samples)
- No naive oversampling of label-1 (SMOTE on spatial data inflates correlations)

---

## PostGIS / Spatial Database (Future)

Phase 1 uses local GeoParquet/GeoPackage files.
Phase 2+ target: PostgreSQL + PostGIS for:
- Spatial joins (village ↔ catchment ↔ DEM tile)
- Streaming feature extraction
- Audit trail via PostGIS versioning

Migration path:
```python
# geopandas → PostGIS
gdf.to_postgis("admin_boundaries", engine, if_exists="replace", schema="resqshield")
```

---

## Observation Confidence Schema

Every record in the feature store must carry data quality metadata:

```python
# Observation confidence fields (schema only — no fake values)
{
    "rainfall_source":           str | None,  # "imd_0.25deg", "imerg_final", "imerg_early", None
    "rainfall_resolution_deg":   float | None,
    "rainfall_age_hours":        float | None,  # hours since last observation
    "river_source":              str | None,   # "cwc_realtime", "cwc_daily", None
    "river_station_dist_km":     float | None, # distance to nearest gauge
    "river_observation_age_h":   float | None,
    "soil_source":               str | None,   # "smap_l3", "era5_land", None
    "soil_resolution_km":        float | None,
    "soil_age_hours":            float | None,
    "terrain_source":            str | None,   # "copernicus_glo30", "srtm", None
    "landcover_source":          str | None,   # "worldcover_2021", None
    "dynamic_data_coverage":     float | None, # 0.0–1.0 fraction of features present
    # RULE: null = missing. NOT zero. Missing data ≠ zero risk.
}
```

**Graceful degradation**: When dynamic data is unavailable, model falls back to static susceptibility only, with `dynamic_data_coverage=0.0` flagged in output.

---

## What This System Is NOT

ResQ Shield does NOT replace or duplicate existing national systems:
- **IFLOWS-India**: national flood early warning (IMD/CWC/NDMA)
- **IMD district-level warnings**: existing weather guidance
- **Bhumi-Roshni / NDMA alerts**: existing dissemination infrastructure
- **Landslide Early Warning System**: existing NIDM/GSI pilot systems

ResQ Shield's target differentiation:
1. **Village/catchment localization** — sub-district resolution linking to official LGD villages
2. **Upstream/downstream context** — river routing, not just point gauges
3. **Static + dynamic separation** — explicit separation of susceptibility and trigger
4. **Multimodal fusion** — combining terrain, rainfall, river, soil, satellite
5. **Observation confidence** — explicit data quality propagation
6. **Graceful degradation** — useful output even with partial data
7. **Cross-region validation** — LORO instead of random splits
8. **Local impact mapping** — linking catchment-scale hazard to village-scale impact
