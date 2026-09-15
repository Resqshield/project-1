# ResQ Shield — Demo Guide

> **3–5 minute walkthrough for judges / reviewers**

---

## Prerequisites

Make sure both services are running:

```bash
# Terminal 1 (project root)
uvicorn backend.main:app --port 8000

# Terminal 2
cd frontend && npm run dev
```

Open **http://localhost:5173**

---

## Demo Sequence

### 1. Dashboard Overview (~30 seconds)

Point out:
- **Header** — "ResQ Shield — AI Disaster Risk Intelligence"
- **Backend Connected** status indicator (top-right)
- **Summary cards** — Total Locations, Flood High, LS High counts (all dynamic from API)
- **Disclaimer** — at bottom: "Synthetic/demo predictions only"

> *"This dashboard loads all 292 synthetic prediction locations from our FastAPI backend on startup."*

---

### 2. Flood Risk Nationwide View (~30 seconds)

The map should be in **Flood Risk** mode by default.

- Point out the India-wide coverage — North, South, East, West, NE, Himalayan belt
- Note the **red (High), amber (Medium), green (Low)** markers
- Note the risk **legend** (bottom-right) showing live counts

> *"292 CircleMarkers — each corresponds to one row in our offline prediction dataset."*

---

### 3. Search — Flood Plains Example (~30 seconds)

Type **"Dhemaji"** in the search bar → select it.

Demonstrate:
- Map **flies to** northeast Assam
- **LocationCard** panel shows: Flood: High (100%), Landslide: Medium
- Note high rainfall, high river level index, flood history: Yes

> *"Dhemaji district in Assam sits in the Brahmaputra flood plain. The flood model assigns 100% confidence — High. The landslide risk is Medium because the slope is low."*

---

### 4. Landslide Risk Toggle (~30 seconds)

Click **"Landslide Risk"** button in the top-left controls.

Demonstrate:
- **All marker colors update** — same 292 locations, different risk mode
- Legend title changes to "Landslide Risk"
- Legend counts change

Search **"Chamoli"** → select it.

> *"Chamoli in Uttarakhand — Flood: Medium, Landslide: High. High slope (28–42°), high rainfall, landslide history drives this result."*

---

### 5. Western Ghats Example (~20 seconds)

Search **"Wayanad"** → select it.

- Landslide: High (99%), Flood: High (96%)
- Note very high rainfall (320–520 mm/month), slope, soil moisture

> *"Wayanad in Kerala — the Western Ghats profile. Both flood and landslide risk are High due to extreme monsoon rainfall combined with steep terrain."*

---

### 6. Himalayan Filter (~30 seconds)

Click **"🏔 Himalayan"** button in the filter bar.

Demonstrate:
- Map zooms to Himalayan belt
- ~78 locations shown — Uttarakhand, Himachal, J&K, Ladakh, Sikkim, Arunachal

Search **"Leh"** → select it.

> *"Leh, Ladakh — 3,501 metres ASL, only 14 mm/month rainfall. Flood: Medium (unusual — but the model uses the synthetic river index). Landslide: Low. High elevation doesn't automatically mean high risk."*

---

### 7. State Filter (~30 seconds)

Clear Himalayan filter. Select **State: "Bihar"** from the State dropdown.

Demonstrate:
- 14 Bihar locations shown
- Map fits to north Bihar flood plains
- Visible count updates: "Visible: 14 / 292"

> *"14 locations across Bihar. Darbhanga, Madhubani, Sitamarhi — all in the Kosi/Bagmati flood belts. Flood: High across the board."*

Click **"Reset Map"** to return to India view.

---

### 8. Architecture Explanation (~30 seconds)

```
prepare_data.py → master_dataset.csv
      ↓
  train_flood.py  +  train_landslide.py
      ↓                  ↓
 flood_model.pkl    landslide_model.pkl
      ↓
generate_predictions.py → india_predictions.json
      ↓
  FastAPI (backend/main.py)
      ↓
  React + Leaflet (frontend/)
```

> *"Two separate Random Forest classifiers. The flood model uses 5 features — rainfall, river level index, soil moisture, elevation, flood history. The landslide model uses rainfall, soil moisture, slope, elevation, landslide history. Predictions are generated once offline and served statically through FastAPI."*

---

### 9. Synthetic Data Disclaimer (~20 seconds)

> *"All environmental values — rainfall, river levels, soil moisture — are synthetic and generated from geographic profiles to demonstrate the pipeline. The models achieve 84.7% and 88.1% accuracy on this synthetic dataset, which measures how well the model reproduces the generation rules — not real-world forecasting accuracy."*

---

### 10. Future Path (~20 seconds)

> *"The next step would be replacing the synthetic data with real IMD rainfall records, CWC river gauge data, ISRO soil moisture products, and historical NDMA disaster records. The model architecture, API, and dashboard are designed to consume real data with minimal changes."*

---

## Key Numbers to Know

| Metric | Value |
|---|---|
| Locations | 292 |
| States/UTs | 34 |
| Flood model accuracy (synthetic) | 84.7% |
| Landslide model accuracy (synthetic) | 88.1% |
| Himalayan belt locations | ~78 |
| North-East locations | ~54 |
| South India locations | ~55 |
| Backend endpoints | 7 |
| Frontend build size | ~404 KB JS (gzipped: 123 KB) |

---

## If Something Goes Wrong

| Problem | Fix |
|---|---|
| "Backend Unavailable" | Run `uvicorn backend.main:app --port 8000` |
| Map not loading | Check browser console for Leaflet errors; hard-refresh |
| Search not finding locations | Try partial name (e.g. "Deh" for Dehradun) |
| Filters empty | Click "Clear Filters" or "Reset Map" |
| Port conflict on 8000 | `uvicorn backend.main:app --port 8001` then update `frontend/src/services/api.js` |
