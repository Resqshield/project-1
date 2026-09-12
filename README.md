# ResQShield AI — Flood & Landslide Early Warning System
## ML Pipeline — Day 1 Reproducible Experiment Foundation (B22)

> **Upstream reference:** [ECMWFCode4Earth/ml_flood](https://github.com/ECMWFCode4Earth/ml_flood)
> (MIT License — @lkugler, @seblehner, ESoWC 2019 — MATEHIW Project)
> This project adapts algorithmic ideas from ml_flood for India-specific sensor data.

---

## Project Structure

```
resqshield-ai/
├── external/
│   └── ml_flood/              ← upstream reference (MIT, unmodified)
├── configs/
│   ├── resqshield_default.yaml
│   └── features.yaml
├── data/
│   ├── raw/                   ← sensor CSVs, gauge readings
│   ├── interim/               ← after preprocessing
│   └── processed/             ← feature-engineered, ready for training
├── src/
│   └── resqshield_ml/
│       ├── data/              ← data loaders
│       ├── features/          ← feature engineering
│       ├── models/            ← model wrappers
│       ├── evaluation/        ← metrics and evaluation
│       └── utils/             ← configuration, logging
├── artifacts/
│   ├── models/                ← serialised model files (.joblib)
│   └── metrics/               ← evaluation results (.json, .csv)
├── tests/
├── requirements.txt
└── README.md
```

---

## What is reused from ml_flood (MIT License)

| Concept | Source | Adaptation |
|---|---|---|
| Temporal lag features | `utils_floodmodel.py::add_shifted_variables` | Reimplemented for pandas DataFrame |
| Rolling aggregate features | `utils_floodmodel.py::shift_and_aggregate` | Reimplemented for pandas + multi-column |
| NSE, RMSE, ME metrics | `verification.py` | Copied with attribution; pandas-compatible |
| FlowModel class pattern | `floodmodels.py::FlowModel` | Extended for GradBoost + XGBoost; xarray dependency removed |
| GradBoost + XGBoost as primary models | Notebooks 3.04, ml-04 | Hyperparameter space adapted for India sensor data |
| Train/test chronological split | Notebook 2.05 | Kept as-is |

## What is NOT reused from ml_flood

| Component | Reason |
|---|---|
| `get_mask_of_basin()` | Danube shapefile hard-coded — replaced by station-based aggregation |
| `FlowModel_DNN` (TDNN/Keras) | Not needed; neural net not justified at Day 1 |
| ERA5/NetCDF data loaders | Replaced by ResQShield CSV sensor stream loader |
| CDO command-line preprocessing | Replaced by pure-Python pandas/numpy |
| GloFAS download scripts | Replaced by CWC/IMD data sources |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Place raw sensor data in data/raw/
# Expected format: see configs/features.yaml

# 3. Run feature engineering
python -m resqshield_ml.features.engineer \
    --input data/raw/sensor_data.csv \
    --output data/processed/features.csv \
    --config configs/resqshield_default.yaml

# 4. Train the model
python -m resqshield_ml.models.flood_model \
    --data data/processed/features.csv \
    --config configs/resqshield_default.yaml \
    --artifact-dir artifacts/

# 5. Evaluate
python -m resqshield_ml.evaluation.metrics \
    --predictions artifacts/metrics/predictions.csv \
    --config configs/resqshield_default.yaml
```

---

## Attribution

Algorithmic ideas derived from:

```
ECMWFCode4Earth/ml_flood
Authors: Lukas Kugler (@lkugler), Sebastian Lehner (@seblehner)
License: MIT
Project: MATEHIW — ESoWC 2019 (ECMWF Summer of Weather Code)
URL: https://github.com/ECMWFCode4Earth/ml_flood
```

ResQShield-specific adaptations authored by the ResQShield team, Smart India Hackathon 2026.
