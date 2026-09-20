# -*- coding: utf-8 -*-
"""
ResQ Shield - Phase 5: FastAPI Backend
=======================================
Serves pre-generated ML predictions from:
    data/predictions/india_predictions.json

Run from project root:
    uvicorn backend.main:app --reload --port 8000

!! DISCLAIMER: Synthetic/demo data. Not an operational disaster warning system.
"""

import os
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Shadow research API (real data, experimental) ─────────────────────────────
try:
    from backend.routes.real_research import router as real_research_router
    _REAL_RESEARCH_AVAILABLE = True
except ImportError:
    _REAL_RESEARCH_AVAILABLE = False

try:
    from backend.routes.real_flood_predict import router as real_flood_router
    _REAL_FLOOD_AVAILABLE = True
except ImportError:
    _REAL_FLOOD_AVAILABLE = False


# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("resqshield")

# ── Path resolution ───────────────────────────────────────────────────────────
# Works whether run as  uvicorn backend.main:app  (from project root)
# or imported during tests.
def _find_project_root() -> Path:
    """Walk up from this file until we find data/predictions/."""
    candidate = Path(__file__).resolve().parent
    for _ in range(5):
        if (candidate / "data" / "predictions").exists():
            return candidate
        candidate = candidate.parent
    # Fallback: current working directory
    return Path.cwd()

PROJECT_ROOT = _find_project_root()
DATA_PATH    = PROJECT_ROOT / "data" / "predictions" / "india_predictions.json"

# ── Constants ─────────────────────────────────────────────────────────────────
VALID_RISK_VALUES = {"low", "medium", "high"}
INTERNAL_FIELDS   = {"source_flood_risk", "source_landslide_risk"}
REQUIRED_FIELDS   = {
    "district", "state", "latitude", "longitude",
    "flood_risk", "flood_probability",
    "landslide_risk", "landslide_probability",
}
DISCLAIMER = (
    "Synthetic/demo predictions only. "
    "Not an operational disaster warning system."
)

MOUNTAIN_DISTRICTS = {
    "Dehradun","Haridwar","Rishikesh","Nainital","Almora",
    "Pithoragarh","Chamoli","Rudraprayag","Uttarkashi","Tehri Garhwal",
    "Shimla","Manali","Kullu","Mandi","Dharamsala","Chamba","Kinnaur",
    "Srinagar","Jammu","Anantnag","Baramulla","Leh","Kargil",
    "Gangtok","Itanagar","Tawang",
    "Darjeeling","Kalimpong","Shillong","Aizawl","Kohima",
}

# ── In-memory store ───────────────────────────────────────────────────────────
_records: List[dict] = []

def _load_predictions():
    """Load and validate india_predictions.json into _records.

    Validation (Phase 6 hardening):
    - Required fields checked on EVERY record, not just the first.
    - Probability values [0,100] checked for every record.
    - Coordinate ranges checked for every record.
    - Fails clearly at startup if any record is invalid.
    """
    global _records
    if not DATA_PATH.exists():
        raise RuntimeError(
            f"Prediction file not found: {DATA_PATH}\n"
            "Run: python ml/generate_predictions.py"
        )
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list) or len(raw) == 0:
        raise RuntimeError("Prediction file is empty or not a JSON array.")

    # ── Validate ALL records ──────────────────────────────────────────────────
    errors = []
    for i, rec in enumerate(raw):
        loc = rec.get('district', f'row[{i}]')

        # Required fields
        missing = REQUIRED_FIELDS - set(rec.keys())
        if missing:
            errors.append(f"  [{loc}] missing fields: {missing}")
            continue   # skip further checks for this record

        # Coordinate range
        lat = rec.get("latitude", None)
        lon = rec.get("longitude", None)
        if lat is None or not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
            errors.append(f"  [{loc}] invalid latitude: {lat}")
        if lon is None or not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
            errors.append(f"  [{loc}] invalid longitude: {lon}")

        # Probability range
        for prob_field in ("flood_probability", "landslide_probability"):
            val = rec.get(prob_field)
            if val is None or not isinstance(val, (int, float)) or not (0 <= val <= 100):
                errors.append(f"  [{loc}] {prob_field}={val!r} out of range [0,100]")

    if errors:
        msg = "Prediction file contains invalid records (startup aborted):\n" + "\n".join(errors)
        raise RuntimeError(msg)

    # Strip internal audit fields from all public records
    _records = [{k: v for k, v in rec.items() if k not in INTERNAL_FIELDS} for rec in raw]
    log.info(f"Loaded {len(_records)} prediction records from {DATA_PATH} — all records validated.")

# ── Lifespan (replaces deprecated on_event) ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_predictions()
    log.info(f"ResQ Shield API ready. {DISCLAIMER}")
    yield

# ── Pydantic models ───────────────────────────────────────────────────────────
class LocationRecord(BaseModel):
    district: str
    state: str
    latitude: float
    longitude: float
    rainfall: float
    river_level: float
    soil_moisture: float
    slope: float
    elevation: float
    flood_history: int
    landslide_history: int
    flood_risk: str
    flood_probability: float
    flood_prob_low: float
    flood_prob_medium: float
    flood_prob_high: float
    landslide_risk: str
    landslide_probability: float
    landslide_prob_low: float
    landslide_prob_medium: float
    landslide_prob_high: float

class SearchResult(BaseModel):
    district: str
    state: str
    latitude: float
    longitude: float
    flood_risk: str
    flood_probability: float
    landslide_risk: str
    landslide_probability: float

class HealthResponse(BaseModel):
    status: str
    project: str
    version: str
    locations: int
    states: int
    data_type: str
    disclaimer: str

class SummaryResponse(BaseModel):
    total_locations: int
    total_states: int
    flood: dict
    landslide: dict
    data_type: str
    generation_source: str
    disclaimer: str

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ResQ Shield API",
    description=(
        "AI-based Disaster Risk Prediction for India. "
        "WARNING: Powered by SYNTHETIC/DEMO data only."
    ),
    version="1.0.0-synthetic",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Register shadow research API (experimental, separate namespace)
# Does NOT touch /api/locations or any synthetic MVP routes
if _REAL_RESEARCH_AVAILABLE:
    app.include_router(real_research_router)
    log.info("Shadow research API registered at /api/real/ [EXPERIMENTAL, not_operational]")

# Register real flood inference (POST /api/real/flood/predict etc.)
if _REAL_FLOOD_AVAILABLE:
    app.include_router(real_flood_router)
    log.info("Real flood inference registered at /api/real/flood/ [EXPERIMENTAL_BASELINE_ONLY]")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _validate_risk(value: Optional[str], param_name: str) -> Optional[str]:
    if value is None:
        return None
    n = value.strip().lower()
    if n not in VALID_RISK_VALUES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {param_name} value '{value}'. "
                "Must be one of: Low, Medium, High (case-insensitive)."
            ),
        )
    return n.capitalize()

def _filter(state=None, flood_risk=None, landslide_risk=None):
    res = _records
    if state:
        s = state.strip().lower()
        res = [r for r in res if r["state"].lower() == s]
    if flood_risk:
        res = [r for r in res if r["flood_risk"].lower() == flood_risk.lower()]
    if landslide_risk:
        res = [r for r in res if r["landslide_risk"].lower() == landslide_risk.lower()]
    return res

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_model=HealthResponse, tags=["Health"])
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    states = {r["state"] for r in _records}
    return HealthResponse(
        status="ok", project="ResQ Shield", version="1.0.0-synthetic",
        locations=len(_records), states=len(states),
        data_type="synthetic_demo", disclaimer=DISCLAIMER,
    )

@app.get("/api/locations", response_model=List[LocationRecord], tags=["Locations"])
async def get_locations(
    state:          Optional[str] = Query(None),
    flood_risk:     Optional[str] = Query(None),
    landslide_risk: Optional[str] = Query(None),
):
    fr = _validate_risk(flood_risk,     "flood_risk")
    lr = _validate_risk(landslide_risk, "landslide_risk")
    return _filter(state=state, flood_risk=fr, landslide_risk=lr)

@app.get("/api/search", response_model=List[SearchResult], tags=["Search"])
async def search(q: str = Query(..., min_length=1,
                               description="Search query (district or state, partial match)")):
    """
    Search by district or state name (case-insensitive, partial match).
    Whitespace-only queries are rejected with HTTP 400.
    """
    q_stripped = q.strip()
    if not q_stripped:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty or whitespace-only."
        )
    q_lower = q_stripped.lower()
    return [
        r for r in _records
        if q_lower in r["district"].lower() or q_lower in r["state"].lower()
    ]

@app.get("/api/location/{district}", response_model=LocationRecord, tags=["Locations"])
async def get_location(district: str, state: Optional[str] = Query(None)):
    d_lower = district.strip().lower()
    matches = [r for r in _records if r["district"].lower() == d_lower]
    if not matches:
        raise HTTPException(status_code=404,
            detail=f"Location '{district}' not found. Use /api/search to find available locations.")
    if state:
        matches = [r for r in matches if r["state"].lower() == state.strip().lower()]
        if not matches:
            raise HTTPException(status_code=404,
                detail=f"Location '{district}' in state '{state}' not found.")
    return matches[0]

@app.get("/api/states", response_model=List[str], tags=["Metadata"])
async def get_states():
    return sorted({r["state"] for r in _records})

@app.get("/api/summary", response_model=SummaryResponse, tags=["Metadata"])
async def get_summary():
    fd = {"Low":0,"Medium":0,"High":0}
    ld = {"Low":0,"Medium":0,"High":0}
    for r in _records:
        if r.get("flood_risk")     in fd: fd[r["flood_risk"]]     += 1
        if r.get("landslide_risk") in ld: ld[r["landslide_risk"]] += 1
    return SummaryResponse(
        total_locations=len(_records), total_states=len({r["state"] for r in _records}),
        flood=fd, landslide=ld, data_type="synthetic_demo",
        generation_source="ml/generate_predictions.py", disclaimer=DISCLAIMER,
    )

@app.get("/api/mountain-locations", response_model=List[LocationRecord], tags=["Locations"])
async def get_mountain_locations():
    res = [r for r in _records if r["district"] in MOUNTAIN_DISTRICTS]
    res.sort(key=lambda r: (r["state"], r["district"]))
    return res
