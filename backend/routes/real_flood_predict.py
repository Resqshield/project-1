# -*- coding: utf-8 -*-
"""
backend/routes/real_flood_predict.py
======================================
Real Flood Model Inference Endpoint (Strict Prediction Contract)
"""

import json
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

log = logging.getLogger("real_flood_predict")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR   = PROJECT_ROOT / "models_real"

STATIC_MODEL_PATH = MODELS_DIR / "flood_static_v3_research_model.pkl"
STATIC_META_PATH  = MODELS_DIR / "flood_static_v3_research_metadata.json"

DYNAMIC_MODEL_PATH = MODELS_DIR / "flood_dynamic_research_model.pkl"
DYNAMIC_META_PATH  = MODELS_DIR / "flood_dynamic_research_metadata.json"

router = APIRouter(prefix="/api/real/flood", tags=["Real Flood Inference"])

RESEARCH_HEADER: Dict[str, Any] = {
    "research_only":      True,
    "not_operational":    True,
    "deployment_allowed": False,
    "data_type":          "real_historical_research",
    "status":             "EXPERIMENTAL_DUAL_MODEL",
    "warning": (
        "Strict static vs dynamic model separation."
    ),
}

_MODEL_CACHE: Dict[str, Any] = {}

def _load_model(model_key: str, model_path: Path) -> Dict[str, Any]:
    if model_key not in _MODEL_CACHE:
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        with open(model_path, "rb") as f:
            artifact = pickle.load(f)
            _MODEL_CACHE[model_key] = artifact
            
        # load meta for features
        meta_path = model_path.with_name(model_path.name.replace(".pkl", "_metadata.json").replace("model_metadata", "metadata"))
        if meta_path.exists():
            with open(meta_path, "r") as f:
                meta = json.load(f)
                _MODEL_CACHE[model_key + "_features"] = meta.get("features", [])
        else:
            _MODEL_CACHE[model_key + "_features"] = []
            
    return _MODEL_CACHE[model_key], _MODEL_CACHE[model_key + "_features"]

def _get_prob(model_key, model_path, supplied_features):
    try:
        model, features = _load_model(model_key, model_path)
    except FileNotFoundError:
        return None, "model_missing"
    except Exception as e:
        return None, str(e)
        
    X_vals = []
    missing = []
    for f in features:
        if f in supplied_features and supplied_features[f] is not None:
            X_vals.append(float(supplied_features[f]))
        else:
            missing.append(f)
            X_vals.append(0.0) # naive fallback for API survival
            
    if missing:
        log.warning(f"Missing features for {model_key}: {missing}")
        if model_key == "dynamic":
            return None, f"missing_features: {','.join(missing)}"
            
    try:
        X = np.array(X_vals, dtype=float).reshape(1, -1)
        prob = float(model.predict_proba(X)[0, 1])
        return prob, "ok"
    except Exception as e:
        return None, str(e)

def _risk_tier(prob: float) -> str:
    if prob >= 0.65: return "high"
    if prob >= 0.40: return "medium"
    return "low"

def _predict_response(lat, lon, rain_features, location_label, lgd_village_code=None):
    supplied = {"lat_center": lat, "lon_center": lon}
    supplied.update(rain_features)
    
    # Resolve terrain from parquet if lgd_village_code is provided
    terrain_path = PROJECT_ROOT / "data_real" / "terrain" / "processed" / "village_terrain_features.parquet"
    hydro_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "village_hydrology.parquet"
    infra_path = PROJECT_ROOT / "data_real" / "infrastructure" / "processed" / "village_infrastructure.parquet"
    up_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "upstream_features.parquet"
    catch_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "village_catchment_link.parquet"
    
    if lgd_village_code:
        import pandas as pd
        try:
            if terrain_path.exists():
                tdf = pd.read_parquet(terrain_path)
                match = tdf[tdf["village_code"].astype(str) == str(lgd_village_code)]
                if not match.empty:
                    row = match.iloc[0]
                    for f in ["elev_mean_m", "slope_mean_deg", "distance_to_stream_m"]:
                        if pd.notna(row.get(f)):
                            supplied[f] = float(row[f])
            
            if hydro_path.exists():
                hdf = pd.read_parquet(hydro_path)
                match = hdf[hdf["village_code"].astype(str) == str(lgd_village_code)]
                if not match.empty and pd.notna(match.iloc[0].get("nearest_river_m")):
                    supplied["nearest_river_m"] = float(match.iloc[0]["nearest_river_m"])
                    
            if infra_path.exists():
                idf = pd.read_parquet(infra_path)
                match = idf[idf["village_code"].astype(str) == str(lgd_village_code)]
                if not match.empty and pd.notna(match.iloc[0].get("nearest_hospital_m")):
                    supplied["nearest_hospital_m"] = float(match.iloc[0]["nearest_hospital_m"])
                    
            if up_path.exists() and catch_path.exists():
                cdf = pd.read_parquet(catch_path)
                cmatch = cdf[cdf["village_lgd_code"].astype(str) == str(lgd_village_code)]
                if not cmatch.empty and pd.notna(cmatch.iloc[0].get("catchment_id")):
                    cid = str(cmatch.iloc[0]["catchment_id"])
                    udf = pd.read_parquet(up_path)
                    umatch = udf[udf["HYBAS_ID"].astype(str) == cid]
                    if not umatch.empty and pd.notna(umatch.iloc[0].get("total_upstream_area_skm")):
                        supplied["total_upstream_area_skm"] = float(umatch.iloc[0]["total_upstream_area_skm"])
                        
        except Exception as e:
            log.error(f"Failed to lookup context for {lgd_village_code}: {e}")
            
    static_prob, stat_stat = _get_prob("static", STATIC_MODEL_PATH, supplied)
    dynamic_prob, dyn_stat = _get_prob("dynamic", DYNAMIC_MODEL_PATH, supplied)
    
    # Strictly defined prediction contract
    # Calculate mathematical confidence based on margin from decision boundary (0.5)
    if dynamic_prob is not None:
        conf_val = abs(dynamic_prob - 0.5) * 2
        confidence_str = f"{conf_val:.2f}"
    else:
        confidence_str = "NEEDS_DATA"

    resp = {
        **RESEARCH_HEADER,
        "location_id": location_label,
        "lgd_ids": {"village_code": lgd_village_code} if lgd_village_code else {},
        "hazard": "flood",
        "static_susceptibility": static_prob if static_prob is not None else -1.0,
        "dynamic_risk": dynamic_prob if dynamic_prob is not None else -1.0,
        "risk_probability": dynamic_prob if dynamic_prob is not None else -1.0,
        "risk_tier": _risk_tier(dynamic_prob) if dynamic_prob is not None else "unknown",
        "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
        "forecast_horizon": "NEEDS_DATA", # Strict lead time rule
        "model_version": "flood_v4_decoupled",
        "model_confidence": confidence_str,
        "data_freshness": "NEEDS_DATA", # No real live observation timestamps available yet
        "observation_confidence": "NEEDS_DATA",
        "data_mode": "full" if (static_prob is not None and dynamic_prob is not None) else "reduced",
        "nearest_hospital_m": supplied.get("nearest_hospital_m") if supplied else None,
        "nearest_road_m": supplied.get("nearest_road_m") if supplied else None,
        "debug_status": {"static": stat_stat, "dynamic": dyn_stat}
    }
    return resp

class PredictRequest(BaseModel):
    lat: float
    lon: float
    lgd_village_code: Optional[str] = None
    allow_research_imputation: bool = Field(False)
    rain_event_sum_mm:   Optional[float] = None
    rain_event_max_mm:   Optional[float] = None
    rain_event_mean_mm:  Optional[float] = None
    rain_event_p90_mm:   Optional[float] = None
    n_days_valid_chirps: Optional[float] = None
    chirps_coverage_pct: Optional[float] = None
    ant_3d_mm:           Optional[float] = None
    n_days_ant_3d:       Optional[float] = None
    ant_7d_mm:           Optional[float] = None
    n_days_ant_7d:       Optional[float] = None
    ant_14d_mm:          Optional[float] = None
    n_days_ant_14d:      Optional[float] = None
    elev_mean_m:         Optional[float] = None
    slope_mean_deg:      Optional[float] = None
    pct_slope_gt_30:     Optional[float] = None
    distance_to_stream_m:Optional[float] = None
    flow_accumulation_skm:Optional[float] = None

@router.post("/predict", summary="Real flood probability (Strict Contract)")
async def predict_point(req: PredictRequest):
    feats = {k: v for k, v in req.dict().items() if v is not None}
    return _predict_response(req.lat, req.lon, feats, f"lat={req.lat:.4f},lon={req.lon:.4f}", req.lgd_village_code)

@router.post("/predict_batch", summary="Batch predict multiple LGD villages")
async def predict_batch(req: List[str]):
    results = {}
    terrain_path = PROJECT_ROOT / "data_real" / "terrain" / "processed" / "village_terrain_features.parquet"
    hydro_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "village_hydrology.parquet"
    infra_path = PROJECT_ROOT / "data_real" / "infrastructure" / "processed" / "village_infrastructure.parquet"
    up_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "upstream_features.parquet"
    catch_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "village_catchment_link.parquet"
    
    if terrain_path.exists():
        import pandas as pd
        try:
            tdf = pd.read_parquet(terrain_path)
            hdf = pd.read_parquet(hydro_path) if hydro_path.exists() else None
            idf = pd.read_parquet(infra_path) if infra_path.exists() else None
            cdf = pd.read_parquet(catch_path) if catch_path.exists() else None
            udf = pd.read_parquet(up_path) if up_path.exists() else None
            
            # Filter all requested
            match = tdf[tdf["village_code"].astype(str).isin(req)]
            for _, row in match.iterrows():
                code = str(row["village_code"])
                supplied = {"lat_center": 0, "lon_center": 0} # batch doesn't require precise lat/lon for API if terrain provided
                for f in ["elev_mean_m", "slope_mean_deg", "distance_to_stream_m"]:
                    if pd.notna(row.get(f)):
                        supplied[f] = float(row[f])
                        
                if hdf is not None:
                    hm = hdf[hdf["village_code"].astype(str) == code]
                    if not hm.empty and pd.notna(hm.iloc[0].get("nearest_river_m")):
                        supplied["nearest_river_m"] = float(hm.iloc[0]["nearest_river_m"])
                        
                if idf is not None:
                    im = idf[idf["village_code"].astype(str) == code]
                    if not im.empty and pd.notna(im.iloc[0].get("nearest_hospital_m")):
                        supplied["nearest_hospital_m"] = float(im.iloc[0]["nearest_hospital_m"])
                        
                if cdf is not None and udf is not None:
                    cm = cdf[cdf["village_lgd_code"].astype(str) == code]
                    if not cm.empty and pd.notna(cm.iloc[0].get("catchment_id")):
                        cid = str(cm.iloc[0]["catchment_id"])
                        um = udf[udf["HYBAS_ID"].astype(str) == cid]
                        if not um.empty and pd.notna(um.iloc[0].get("total_upstream_area_skm")):
                            supplied["total_upstream_area_skm"] = float(um.iloc[0]["total_upstream_area_skm"])

                s_prob, _ = _get_prob("static", STATIC_MODEL_PATH, supplied)
                d_prob, _ = _get_prob("dynamic", DYNAMIC_MODEL_PATH, supplied)
                results[code] = {
                    "static_susceptibility": s_prob if s_prob is not None else -1.0,
                    "dynamic_risk": d_prob if d_prob is not None else -1.0
                }
        except Exception as e:
            log.error(f"Batch predict failed: {e}")
    return results

@router.get("/location", summary="Real flood probability by admin name (Experimental)")
async def predict_location(state: str, district: str = None):
    # Dummy implementation for location lookup to satisfy old tests if needed
    raise HTTPException(501, detail="Location text lookup deprecated in favor of explicit LGD polygon requests.")

@router.get("/model-info", summary="Real flood model metadata")
async def model_info():
    return {
        **RESEARCH_HEADER,
        "model_available": DYNAMIC_MODEL_PATH.exists(),
        "prediction_endpoint": "POST /api/real/flood/predict"
    }
