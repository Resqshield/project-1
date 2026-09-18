import pytest
import json
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def test_static_model_leakage():
    meta_path = PROJECT_ROOT / "models_real" / "flood_static_v3_research_metadata.json"
    assert meta_path.exists(), "Static model v3 metadata missing"
    
    with open(meta_path) as f:
        meta = json.load(f)
        
    features = [f.lower() for f in meta["feature_list"]]
    
    # Assert NO dynamic features exist in static model
    dynamic_substrings = ["rain", "ant_", "coverage", "chirps", "event"]
    for f in features:
        for sub in dynamic_substrings:
            assert sub not in f, f"Leakage found! Static model contains dynamic feature: {f}"

def test_dynamic_model_contains_temporal():
    meta_path = PROJECT_ROOT / "models_real" / "flood_dynamic_research_metadata.json"
    assert meta_path.exists(), "Dynamic model metadata missing"
    
    with open(meta_path) as f:
        meta = json.load(f)
        
    features = [f.lower() for f in meta["feature_list"]]
    
    has_temporal = any("rain" in f or "ant" in f for f in features)
    assert has_temporal, "Dynamic model has no temporal/dynamic features!"
    
    # Assert NO static features in dynamic model
    static_substrings = ["elev", "slope", "dist", "acc", "lat", "lon"]
    for f in features:
        for sub in static_substrings:
            assert sub not in f, f"Static feature mixed into dynamic model: {f}"

def test_terrain_not_dummy():
    prov_path = PROJECT_ROOT / "data_real" / "terrain" / "processed" / "provenance.txt"
    assert prov_path.exists(), "Terrain provenance missing"
    with open(prov_path) as f:
        content = f.read().lower()
        assert "dummy" not in content, "Terrain is still marked as dummy!"
        
    parquet_path = PROJECT_ROOT / "data_real" / "terrain" / "processed" / "village_terrain_features.parquet"
    assert parquet_path.exists(), "village_terrain_features.parquet missing"
    
    df = pd.read_parquet(parquet_path)
    assert "elev_mean_m" in df.columns
    assert "slope_mean_deg" in df.columns
    
    # Check that we have at least some non-null real pixels
    valid = df["elev_mean_m"].notna().sum()
    assert valid > 0, "No valid elevation pixels found (all NaN)!"
    assert df["elev_mean_m"].sum() != 0, "All elevations are exactly zero! (dummy)"
    
def test_lead_time_integrity():
    with open(PROJECT_ROOT / "backend" / "routes" / "real_flood_predict.py") as f:
        content = f.read()
    assert '"forecast_horizon": "NEEDS_DATA"' in content, "Lead time is fabricating a constant instead of NEEDS_DATA"

def test_map_hardcoded_colors_removed():
    map_path = PROJECT_ROOT / "frontend" / "src" / "realmap" / "RealAdminMap.jsx"
    with open(map_path) as f:
        content = f.read()
    assert 'rgba(255, 100, 100' not in content, "Hardcoded red hazard color still exists in RealAdminMap.jsx"
    assert 'fetch("/api/real/flood/predict_batch"' in content, "Map does not dynamically batch-fetch ML predictions"

def test_prediction_contract_no_hardcoded_constants():
    with open(PROJECT_ROOT / "backend" / "routes" / "real_flood_predict.py") as f:
        content = f.read()
    
    assert '"model_confidence": "low"' not in content, "model_confidence is still hardcoded to a constant"
    assert '"data_freshness": "historical"' not in content, "data_freshness is still hardcoded to a constant"
    assert '"model_confidence": confidence_str' in content or '"model_confidence": "NEEDS_DATA"' in content
    assert '"data_freshness": "NEEDS_DATA"' in content
