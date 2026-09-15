# ResQ Shield — AI Disaster Risk Intelligence

> **⚠️ IMPORTANT DISCLAIMER**
> All environmental values, model outputs, and risk predictions in this project are
> **SYNTHETIC / DEMO DATA** generated to validate system architecture and UX.
> This is **NOT** an operational disaster warning system and should **NOT** be used
> for any real disaster preparedness or policy decisions.

---

## Overview

ResQ Shield is a full-stack AI-powered flood and landslide risk visualization system
covering 292 locations across all 34 states and UTs of India. It demonstrates a complete
ML-to-UI pipeline: synthetic data generation → model training → REST API → interactive map.

---

## Current MVP

A **static synthetic dataset** system that:

- Generates geographically plausible synthetic environmental data for ~292 Indian locations
- Trains separate **Random Forest classifiers** for flood risk and landslide risk
- Generates an offline prediction dataset served via **FastAPI**
- Visualizes all predictions on an **interactive Leaflet India map**
- Supports **search, state filters, region filters, and risk-level filters**

---

## Architecture

```
Synthetic Static Data (prepare_data.py)
↓
master_dataset.csv  (292 locations, 13 features)
↓
┌─────────────────────────┬─────────────────────────┐
│   Flood RF Classifier   │ Landslide RF Classifier  │
│  (train_flood.py)       │  (train_landslide.py)    │
└────────────┬────────────┴────────────┬─────────────┘
             ↓                         ↓
          Prediction Generation (generate_predictions.py)
                        ↓
             india_predictions.json  (292 records)
                        ↓
               FastAPI Backend (backend/main.py)
                        ↓
              React + Vite Frontend (frontend/)
                        ↓
            Interactive India Risk Map (Leaflet)
```

---

## Features

| Feature | Status |
|---|---|
| Flood risk prediction (Low / Medium / High) | ✅ |
| Landslide risk prediction (Low / Medium / High) | ✅ |
| Model confidence % per prediction | ✅ |
| Interactive India map (292 markers) | ✅ |
| Flood / Landslide mode toggle | ✅ |
| Location search (district or state) | ✅ |
| State filter (all 34 states/UTs) | ✅ |
| Risk-level filter (Low / Medium / High) | ✅ |
| Region quick filters (Himalayan, NE, South, West, Central) | ✅ |
| Himalayan focus button | ✅ |
| Marker popups with risk summary | ✅ |
| Detailed LocationCard (env parameters + probability bars) | ✅ |
| Backend health + summary endpoints | ✅ |
| Nationwide coverage incl. NE + Himalayan belt | ✅ |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data preparation | Python, pandas, NumPy |
| Machine learning | scikit-learn (RandomForestClassifier) |
| Model persistence | joblib |
| Backend | FastAPI, Uvicorn |
| Frontend | React 18, Vite |
| Map | Leaflet, react-leaflet |
| Icons | lucide-react |
| Styling | Vanilla CSS (dark dashboard theme) |

---

## Project Structure

```
flood_prediction_this/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Backend Python dependencies
│   └── test_api.py          # API test suite (47 tests)
├── data/
│   ├── processed/
│   │   └── master_dataset.csv       # 292 rows, 13 columns
│   └── predictions/
│       ├── india_predictions.csv    # 292 rows, 23 columns
│       └── india_predictions.json   # Served by FastAPI
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main app + filter state
│   │   ├── components/
│   │   │   ├── FilterBar.jsx       # State/risk/region filters
│   │   │   ├── Header.jsx
│   │   │   ├── LocationCard.jsx    # Detailed location panel
│   │   │   ├── LoadingState.jsx
│   │   │   ├── RiskMap.jsx         # Leaflet map component
│   │   │   ├── RiskToggle.jsx
│   │   │   ├── SearchBar.jsx
│   │   │   └── SummaryCards.jsx
│   │   ├── services/
│   │   │   └── api.js              # Backend API service layer
│   │   └── index.css               # Global dark dashboard CSS
│   ├── index.html
│   └── package.json
├── ml/
│   ├── prepare_data.py      # Generate master_dataset.csv
│   ├── train_flood.py       # Train flood RF model
│   ├── train_landslide.py   # Train landslide RF model
│   ├── generate_predictions.py  # Generate india_predictions.json
│   └── verify_phase10.py    # Data + model QA checks
├── models/
│   ├── flood_model.pkl                # Flood RF bundle
│   ├── flood_model_metadata.json
│   ├── landslide_model.pkl            # Landslide RF bundle
│   └── landslide_model_metadata.json
└── README.md
```

> **Note:** `models/*.pkl` are excluded from git by default (`.gitignore`).
> Run the ML pipeline steps below to regenerate them locally.

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### 1 — Install Python dependencies

```bash
pip install pandas numpy scikit-learn joblib fastapi uvicorn[standard] httpx
```

### 2 — Install Frontend dependencies

```bash
cd frontend
npm install
```

### 3 — Run the ML pipeline (from project root)

```bash
python ml/prepare_data.py        # Generate master_dataset.csv
python ml/train_flood.py         # Train flood model → models/flood_model.pkl
python ml/train_landslide.py     # Train landslide model → models/landslide_model.pkl
python ml/generate_predictions.py  # Generate india_predictions.json
```

### 4 — Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5 — Start the frontend

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Status, location count, disclaimer |
| GET | `/api/locations` | All predictions (optional `?state=` `?flood_risk=` `?landslide_risk=`) |
| GET | `/api/location/{district}` | Single location detail (optional `?state=`) |
| GET | `/api/search?q={query}` | Search by district or state name |
| GET | `/api/states` | All 34 state/UT names |
| GET | `/api/summary` | Risk distribution counts |
| GET | `/api/mountain-locations` | High-elevation / mountain locations only |

Swagger UI: **http://localhost:8000/docs**

---

## ML Features

### Flood Model (RandomForestClassifier)
Input features: `rainfall`, `river_level`, `soil_moisture`, `elevation`, `flood_history`
Target: `flood_risk` → Low / Medium / High

### Landslide Model (RandomForestClassifier)
Input features: `rainfall`, `soil_moisture`, `slope`, `elevation`, `landslide_history`
Target: `landslide_risk` → Low / Medium / High

| Model | Training Rows | Synthetic Validation Accuracy |
|---|---|---|
| Flood RF | 233 / 292 | 84.7% |
| Landslide RF | 233 / 292 | 88.1% |

> These accuracy values reflect how well the model reproduces the **synthetic label rules**
> on a held-out portion of the same synthetic dataset.
> They do **NOT** represent real-world flood or landslide forecasting performance.

---

## Current Dataset

| Metric | Value |
|---|---|
| Total locations | 292 |
| Unique states/UTs | 34 |
| Himalayan belt locations | ~78 |
| North-East locations | ~54 |
| South India locations | ~55 |
| Coordinate range (lat) | 8.09° – 34.71° N |
| Coordinate range (lon) | 69.63° – 96.17° E |
| All environmental values | **SYNTHETIC/DEMO** |

### State coverage sample (top by count)
Uttarakhand (25), Himachal Pradesh (18), Assam (16), Uttar Pradesh (16),
Jammu & Kashmir (15), Maharashtra (15), Bihar (14), West Bengal (13),
Karnataka (12), Kerala (12), Gujarat (12), Tamil Nadu (12) …

---

## Running Tests

```bash
# Backend API tests (47 tests)
python backend/test_api.py

# Data + model QA verification
python ml/verify_phase10.py

# Frontend production build check
cd frontend && npm run build
```

---

## ⚠️ Important Disclaimer

The current dataset, all environmental feature values (rainfall, river level index,
soil moisture, slope, elevation, flood history, landslide history) and all model
predictions (flood risk, landslide risk, confidence percentages) are **entirely
synthetic/demo values** generated to demonstrate the system architecture.

- `river_level` is a **normalized index 0–10**, not metres
- All coordinates are real approximate city/district centroids
- All other values are synthetically generated from geographic profiles

**DO NOT use any output from this system for real disaster preparedness,
evacuation decisions, or policy-making.**

---

## Future Work (Synthetic MVP)

The following MVP enhancements are planned:

| Enhancement | Description |
|---|---|
| Real historical flood labels | IMD/NDMA disaster records |
| Live rainfall data | IMD / OpenWeatherMap API |
| River gauge data | CWC real-time river level feeds |
| Satellite soil moisture | ISRO / NASA SMAP products |
| GloFAS integration | Global Flood Awareness System |
| District-level GeoJSON | Choropleth risk visualization |
| Real-time alerting | Push notifications on risk escalation |
| Evacuation routing | Nearest shelter / route planning |
| Model validation | Against actual historical disaster records |
| Production deployment | Cloud hosting with CI/CD |

---

## Real Data v1 Development: in progress

> **Branch**: `real-data-v1`
> **Status**: Phase 1 complete — Administrative / Geospatial Foundation
> **The synthetic MVP remains fully functional on branch `static_data_map`.**

### What Real Data Phase 1 delivers

A complete geospatial infrastructure foundation in `data_real/` and `real_pipeline/`:

| Component | Status |
|---|---|
| LGD admin hierarchy ingest (State→District→Sub-dist→Block→GP→Village) | Pipeline ready; LGD data MANUAL_REQUIRED |
| Boundary ingest (GADM, Datameet, Survey of India) | Pipeline ready; GADM download MANUAL_REQUIRED |
| Admin crosswalk (LGD ↔ Census 2011 ↔ GADM) | ✅ State crosswalk (38 entries) built |
| Admin validation suite (codes, dupes, hierarchy, coords) | ✅ 43 tests passing |
| Village search prototype (Raini → code + parents) | ✅ Implemented and tested |
| Terrain pilot: Copernicus GLO-30 DEM (public, no auth) | ✅ N29E078 (42.5 MB) downloaded |
| Real terrain derivatives (elevation, slope, aspect) | ✅ From real DEM: 197m–2693m, 7.5° mean slope |
| Training strategy (static/dynamic, LORO validation, PR-AUC metrics) | ✅ Documented |
| Observation confidence schema | ✅ Designed (null ≠ zero risk) |
| Data sources documentation | ✅ 15+ sources documented |
| Download manifest | ✅ All datasets tracked with status |
| REAL_DATA_GAP.md (accurate gap framing) | ✅ India ecosystem accurately described |
| No real ML models trained | ✅ Confirmed — Phase 2+ only |
| No synthetic data in data_real/ | ✅ Confirmed — fully separated |

### Recommended Next Steps (Phase 2)

1. **Manually download LGD data** from https://lgdirectory.gov.in/ or https://data.gov.in/resource/all-villages-lgd
2. **Download GADM GeoPackage** (~220 MB) from https://gadm.org/download_country.html
3. **Complete Uttarakhand terrain** — download remaining 8 tiles (N29–N31, E78–E80)
4. **Download HydroBASINS** for catchment delineation
5. **Ingest IMD or IMERG** rainfall for historical event windows
6. **Start historical event labelling** using ISRO Bhuvan + NDMA records

### Map Scaling Recommendation (Leaflet vs MapLibre)

For 292 synthetic markers: **Leaflet is adequate**.
For 600,000+ village features (nationwide):
- **MapLibre GL JS + PMTiles/Vector tiles** is strongly recommended.
- Leaflet cannot render 600k markers without significant clustering or decimation.
- Proposed zoom hierarchy: zoom 4–6 = state/district aggregates; zoom 7–9 = district/subdistrict; zoom 10–11 = village clusters/boundaries; zoom 12+ = individual village features.
- Current `RiskMap.jsx` is preserved unchanged. MapLibre migration is a future phase task.

