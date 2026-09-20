# -*- coding: utf-8 -*-
"""
backend/routes/real_research.py
================================
Shadow Research API — FastAPI Router
Prefix: /api/real/

RULES (enforced):
  - ALL responses include research_only=True, not_operational=True
  - NO nationwide hazard predictions
  - NO replacement of /api/locations (synthetic MVP untouched)
  - NO fabricated predictions
"""

import json
import logging
import os
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import FileResponse

log = logging.getLogger("real_research_api")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR   = PROJECT_ROOT / "data_real" / "evaluation"
MODELS_DIR = PROJECT_ROOT / "models_real"
DATA_REAL_DIR = PROJECT_ROOT / "data_real"

router = APIRouter(prefix="/api/real", tags=["Real Research (Experimental)"])

RESEARCH_HEADER: Dict[str, Any] = {
    "research_only": True,
    "not_operational": True,
    "data_type": "real_historical_research",
    "status": "EXPERIMENTAL_BASELINE_ONLY",
    "warning": (
        "Experimental research outputs trained on 3 independent flood events. "
        "NOT for operational forecasting or decision support. "
        "Synthetic MVP at /api/locations remains the active demo layer."
    ),
}


def _load_json(path: Path) -> Dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"File not found: {path.name}", "generated": False}
    except Exception as e:
        return {"error": str(e)}


def _read_md(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Not found: {path.name}"


@router.get("/status", summary="Real data pipeline status and model readiness")
async def real_status():
    """
    Returns research pipeline status. All flags accurately reflect current data state.
    """
    def check_file(path_str):
        return "READY" if (PROJECT_ROOT / path_str).exists() else "MISSING"

    return {
        **RESEARCH_HEADER,
        "admin_identity": "LGD_READY",
        "admin_geometry": check_file("data_real/admin/processed/geojson/districts_india.geojson"),
        "village_geometry": check_file("data_real/admin/raw/LGD_Villages.parquet"),
        "village_catchment_linkage": check_file("data_real/hydrology/processed/village_catchment_link.parquet"),
        "catchments": check_file("data_real/hydrology/processed/hydrobasins_india_lev08.parquet"),
        "streams": check_file("data_real/hydrology/processed/hydro_rivers_india.parquet"),
        "terrain": check_file("data_real/terrain/processed/village_terrain_features.parquet"),
        "upstream_graph": check_file("data_real/hydrology/processed/upstream_graph.json"),
        "static_susceptibility": check_file("models_real/flood_static_v2_research_model.pkl"),
        "dynamic_flood": check_file("models_real/flood_dynamic_research_model.pkl"),
        "roads": check_file("data_real/osm/raw/uttarakhand_roads.json"),
        "shelters": check_file("data_real/osm/raw/uttarakhand_shelters.json"),
        "sensors": "MISSING",
        "landslide": "NEEDS_MORE_EVENTS",
        "nationwide_predictions": False,
        "research_only": True
    }


@router.get("/model-card/flood", summary="Flood model card and LOEO evaluation summary")
async def flood_model_card():
    metadata = _load_json(MODELS_DIR / "flood_research_metadata.json")
    fold_summary: Dict[str, Any] = {}

    fold_path = EVAL_DIR / "fold_metrics.csv"
    if fold_path.exists():
        try:
            import pandas as pd
            fm = pd.read_csv(fold_path)
            loeo = fm[fm["strategy"] == "LOEO"]
            for model_name, grp in loeo.groupby("model"):
                fold_summary[model_name] = {
                    "macro_pr_auc": round(float(grp["pr_auc"].mean()), 4),
                    "macro_recall": round(float(grp["recall_pod"].mean()), 4),
                    "macro_far":    round(float(grp["far"].mean()), 4),
                    "n_folds":      int(len(grp)),
                    "strategy":     "LOEO",
                }
        except Exception as e:
            fold_summary = {"error": str(e)}

    md_card = _read_md(EVAL_DIR / "model_card_flood.md")
    return {
        **RESEARCH_HEADER,
        "hazard": "flood",
        "metadata": metadata,
        "loeo_macro_summary": fold_summary,
        "model_card_markdown": md_card[:5000],
    }


@router.get("/model-card/landslide", summary="Landslide readiness card (no model trained)")
async def landslide_model_card():
    md_card = _read_md(EVAL_DIR / "model_card_landslide.md")
    return {
        **RESEARCH_HEADER,
        "hazard": "landslide",
        "readiness": "NEEDS_MORE_EVENTS",
        "model_trained": False,
        "n_rows": 14,
        "n_dynamic_positives": 4,
        "minimum_needed": 50,
        "reason": (
            "Only 4 dynamic rain-triggered dated events. 14 total rows insufficient "
            "for defensible ML model. No model trained."
        ),
        "model_card_markdown": md_card[:3000],
    }


@router.get("/pilot-regions", summary="Available pilot regions and event inventory")
async def pilot_regions():
    metadata = _load_json(MODELS_DIR / "flood_research_metadata.json")
    return {
        **RESEARCH_HEADER,
        "n_pilot_regions": len(metadata.get("regions", [])),
        "regions": {
            "uttarakhand": {
                "events": ["IND_FLOOD_2013_UK_001"],
                "negative_windows": ["NEG_UK_2013_PREMONSOON"],
                "notes": "Kedarnath flood 2013. Himalayan terrain.",
            },
            "kerala_wayanad": {
                "events": ["IND_FLOOD_2018_KL_001"],
                "negative_windows": ["NEG_KL_2019_PREMONSOON"],
                "notes": "Kerala Great Flood 2018. Western Ghats.",
            },
            "assam": {
                "events": ["IND_FLOOD_2022_AS_001"],
                "negative_windows": ["NEG_AS_2022_DRY_WINTER"],
                "notes": "Assam seasonal flood 2022. Brahmaputra basin.",
            },
        },
        "nationwide_predictions": False,
        "nationwide_prediction_note": (
            "This model is NOT applied nationwide. Scoped to training regions only."
        ),
    }


@router.get("/audit", summary="Full independence audit and gate results")
async def independence_audit():
    report = _load_json(EVAL_DIR / "readiness_report.json")
    return {**RESEARCH_HEADER, "audit": report}


# ── Gate K: Admin hierarchy search ────────────────────────────────────────────

GADM_DIR = PROJECT_ROOT / "data_real" / "admin" / "processed"
_ADMIN_INDEX = None


def _load_admin_search_index():
    """Build search index from GADM districts/states GeoJSON with centroids for flyTo."""
    import json
    import math
    records = []

    def _geojson_centroid(geometry):
        """Compute approximate centroid from a GeoJSON geometry."""
        try:
            coords_flat = []
            gtype = geometry.get("type", "")
            coords = geometry.get("coordinates", [])
            
            def _flatten(c, depth=0):
                if isinstance(c, list) and len(c) == 2 and isinstance(c[0], (int, float)):
                    coords_flat.append(c)
                elif isinstance(c, list):
                    for sub in c:
                        _flatten(sub, depth + 1)
                        
            _flatten(coords)
            if coords_flat:
                lons = [p[0] for p in coords_flat]
                lats = [p[1] for p in coords_flat]
                return sum(lats) / len(lats), sum(lons) / len(lons)
        except Exception:
            pass
        return None, None

    # ── Build centroid lookup from districts GeoJSON ──────────────────────────
    district_centroids = {}   # district_name_lower -> (lat, lon)
    state_centroids    = {}   # state_name_lower    -> (lat, lon)

    district_geojson = GEOJSON_DIR / "districts_india.geojson"
    states_geojson   = GEOJSON_DIR / "states_india.geojson"

    try:
        if district_geojson.exists():
            with open(district_geojson, encoding="utf-8") as f:
                gj = json.load(f)
            for feat in gj.get("features", []):
                props = feat.get("properties", {})
                name = str(props.get("district_name", "") or "").strip()
                state = str(props.get("state_name", "") or "").strip()
                geom = feat.get("geometry") or {}
                lat, lon = _geojson_centroid(geom)
                if name and lat is not None:
                    district_centroids[name.lower()] = (round(lat, 4), round(lon, 4))
    except Exception as e:
        log.warning(f"District centroid build failed: {e}")

    try:
        if states_geojson.exists():
            with open(states_geojson, encoding="utf-8") as f:
                gj = json.load(f)
            for feat in gj.get("features", []):
                props = feat.get("properties", {})
                name = str(props.get("state_name", "") or "").strip()
                geom = feat.get("geometry") or {}
                lat, lon = _geojson_centroid(geom)
                if name and lat is not None:
                    state_centroids[name.lower()] = (round(lat, 4), round(lon, 4))
    except Exception as e:
        log.warning(f"State centroid build failed: {e}")

    # ── Build records from the GeoJSON features directly ─────────────────────
    try:
        if district_geojson.exists():
            with open(district_geojson, encoding="utf-8") as f:
                gj = json.load(f)
            for feat in gj.get("features", []):
                props = feat.get("properties", {})
                name     = str(props.get("district_name", "") or "").strip()
                state    = str(props.get("state_name",   "") or "").strip()
                code     = str(props.get("district_code","") or "").strip()
                if not name:
                    continue
                geom = feat.get("geometry") or {}
                lat, lon = _geojson_centroid(geom)
                records.append({
                    "name": name,
                    "type": "district",
                    "code": code,
                    "parent_path": state,
                    "state": state,
                    "district": name,
                    "lat": round(lat, 4) if lat is not None else None,
                    "lon": round(lon, 4) if lon is not None else None,
                })
    except Exception as e:
        log.warning(f"District index build from GeoJSON failed: {e}")

    try:
        if states_geojson.exists():
            with open(states_geojson, encoding="utf-8") as f:
                gj = json.load(f)
            for feat in gj.get("features", []):
                props = feat.get("properties", {})
                name  = str(props.get("state_name",  "") or "").strip()
                code  = str(props.get("state_code",  "") or "").strip()
                if not name:
                    continue
                geom = feat.get("geometry") or {}
                lat, lon = _geojson_centroid(geom)
                records.append({
                    "name": name,
                    "type": "state",
                    "code": code,
                    "parent_path": "India",
                    "state": name,
                    "district": None,
                    "lat": round(lat, 4) if lat is not None else None,
                    "lon": round(lon, 4) if lon is not None else None,
                })
    except Exception as e:
        log.warning(f"State index build from GeoJSON failed: {e}")

    # Deduplicate by (name, type, code)
    seen, unique = set(), []
    for r in records:
        key = (r["name"].lower(), r["type"], r.get("code", ""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    log.info(f"Admin search index: {len(unique)} entries ({len(district_centroids)} district centroids, {len(state_centroids)} state centroids)")
    return unique



@router.get("/infrastructure/evacuation/summary", summary="Evacuation Features Summary")
async def evacuation_summary():
    path = Path(__file__).parent.parent.parent / "data_real" / "infrastructure" / "processed" / "evacuation_points.geojson"
    if not path.exists():
        return {"hospitals": 0, "shelters": 0, "total": 0}
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            features = data.get("features", [])
            hospitals = sum(1 for f in features if f.get("properties", {}).get("amenity") in ("hospital", "clinic"))
            shelters = sum(1 for f in features if f.get("properties", {}).get("amenity") == "shelter")
            return {"hospitals": hospitals, "shelters": shelters, "total": len(features)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/infrastructure/evacuation/nearest", summary="Nearest OSM Facility")
async def evacuation_nearest(lat: float, lon: float, radius_km: float = 20.0):
    import json
    import math
    from pathlib import Path

    path = Path(__file__).parent.parent.parent / "data_real" / "infrastructure" / "processed" / "evacuation_points.geojson"
    if not path.exists():
        return {"error": "Dataset missing"}

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            features = data.get("features", [])
            
            nearby = []
            for feat in features:
                coords = feat.get("geometry", {}).get("coordinates", [])
                if len(coords) == 2:
                    f_lon, f_lat = coords
                    dist = haversine(lat, lon, f_lat, f_lon)
                    if dist <= radius_km:
                        feat["properties"]["_distance_km"] = dist
                        nearby.append(feat)

            if not nearby:
                return {"error": "No facilities found"}

            shelters = [f for f in nearby if f.get("properties", {}).get("amenity") == "shelter"]
            hospitals = [f for f in nearby if f.get("properties", {}).get("amenity") in ("hospital", "clinic")]

            # Prefer shelter
            if shelters:
                shelters.sort(key=lambda x: x["properties"]["_distance_km"])
                return shelters[0]
            if hospitals:
                hospitals.sort(key=lambda x: x["properties"]["_distance_km"])
                return hospitals[0]
            
            nearby.sort(key=lambda x: x["properties"]["_distance_km"])
            return nearby[0]
    except Exception as e:
        return {"error": str(e)}

@router.get("/infrastructure/evacuation", summary="GeoJSON of Hospitals and Shelters (Evacuation Context)")
async def evacuation_geojson():
    """Serves the verified OSM hospital, clinic, and shelter points."""
    path = Path(__file__).parent.parent.parent / "data_real" / "infrastructure" / "processed" / "evacuation_points.geojson"
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return FileResponse(path, media_type="application/geo+json")

def _get_admin_index():
    global _ADMIN_INDEX
    if _ADMIN_INDEX is None:
        _ADMIN_INDEX = _load_admin_search_index()
        log.info(f"Admin search index: {len(_ADMIN_INDEX)} entries")
    return _ADMIN_INDEX


_VILLAGE_SEARCH_INDEX = None

def _get_village_search_index():
    global _VILLAGE_SEARCH_INDEX
    if _VILLAGE_SEARCH_INDEX is None:
        p = PROJECT_ROOT / "data_real" / "admin" / "raw" / "LGD_Villages.parquet"
        if not p.exists():
            _VILLAGE_SEARCH_INDEX = []
            return _VILLAGE_SEARCH_INDEX
            
        import pandas as pd
        import geopandas as gpd
        log.info("Building village search index... (this may take a few seconds)")
        try:
            df = gpd.read_parquet(p, columns=["vilname11", "vil_lgd", "dtname", "stname", "geometry"])
            centroids = df.geometry.centroid
            
            records = []
            # Optimization: Extract arrays to python list for faster iteration
            names = df["vilname11"].fillna("").astype(str).tolist()
            codes = df["vil_lgd"].fillna("").astype(str).tolist()
            dts = df["dtname"].fillna("").astype(str).tolist()
            sts = df["stname"].fillna("").astype(str).tolist()
            cx = centroids.x.tolist()
            cy = centroids.y.tolist()
            
            for i in range(len(names)):
                name = names[i]
                if not name or name == "nan":
                    continue
                records.append({
                    "name": name,
                    "name_lower": name.lower(),
                    "type": "village",
                    "code": codes[i],
                    "parent_path": f"{dts[i]}, {sts[i]}",
                    "state": sts[i],
                    "district": dts[i],
                    "lat": round(cy[i], 4) if pd.notnull(cy[i]) else None,
                    "lon": round(cx[i], 4) if pd.notnull(cx[i]) else None,
                })
            _VILLAGE_SEARCH_INDEX = records
            log.info(f"Village search index built: {len(_VILLAGE_SEARCH_INDEX)} entries")
        except Exception as e:
            log.warning(f"Failed to build village search index: {e}")
            _VILLAGE_SEARCH_INDEX = []
            
    return _VILLAGE_SEARCH_INDEX

def _search_villages(q_lower, limit):
    idx = _get_village_search_index()
    
    # 1. Exact matches
    exact_matches = []
    # 2. Starts with matches
    starts_matches = []
    # 3. Contains matches
    contains_matches = []
    
    for r in idx:
        if r["name_lower"] == q_lower:
            exact_matches.append(r)
        elif r["name_lower"].startswith(q_lower):
            starts_matches.append(r)
        elif q_lower in r["name_lower"]:
            contains_matches.append(r)
            
    # Sort the partial matches by length for better relevance
    starts_matches.sort(key=lambda r: len(r["name"]))
    contains_matches.sort(key=lambda r: len(r["name"]))
    
    results = exact_matches + starts_matches + contains_matches
    return results[:limit]



@router.get("/search", summary="Admin hierarchy search with disambiguation (Gate K)")
async def admin_search(q: str = "", limit: int = 10):
    """Search state/district/sub-district. Returns full parent path for disambiguation."""
    if not q or len(q) < 2:
        return {**RESEARCH_HEADER, "results": [], "query": q,
                "note": "Minimum 2 characters required"}
    q_lower = q.strip().lower()
    
    # Get all district/state matches
    idx = _get_admin_index()
    admin_matches = [r for r in idx if q_lower in r["name"].lower()]
    
    # Get all village matches
    village_matches = _search_villages(q_lower, 50)  # get enough to sort properly
    
    # Combine
    all_results = admin_matches + village_matches
    
    # Sorting logic:
    # 1. Exact match (0) vs Prefix match (1) vs Substring (2)
    # 2. Type: district (0) vs village (1) vs state (2)
    # 3. Length of name (shorter is better)
    def sort_key(r):
        name_lower = r["name"].lower()
        if name_lower == q_lower:
            match_type = 0
        elif name_lower.startswith(q_lower):
            match_type = 1
        else:
            match_type = 2
            
        type_priority = {"district": 0, "village": 1, "state": 2}.get(r["type"], 3)
        return (match_type, type_priority, len(name_lower))
        
    all_results.sort(key=sort_key)
    
    # Deduplicate by unique code or name+parent_path
    seen = set()
    deduped = []
    for r in all_results:
        key = (r.get("type"), r.get("code") or r.get("name"), r.get("parent_path"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
            if len(deduped) == limit:
                break
                
    return {
        **RESEARCH_HEADER,
        "query": q, "n_results": len(deduped),
        "results": deduped,
    }

# Start background warm-up of the village index so it doesn't block the first search
import threading
threading.Thread(target=_get_village_search_index, daemon=True).start()


# ── Gate J: GeoJSON static serving & Health ───────────────────────────────────

from fastapi.responses import FileResponse
import geopandas as gpd
GEOJSON_DIR = GADM_DIR / "geojson"

@router.get("/health", summary="Real pipeline health check")
async def real_health():
    """Health check for the real experimental pipeline."""
    return {
        "status": "ok",
        "project": "ResQ Shield Real Research",
        "version": "1.0.0-real-experimental",
        "data_type": "real_historical_research",
        **RESEARCH_HEADER
    }

_VILLAGE_GDF = None
_STREAMS_GDF = None
_CATCHMENTS_GDF = None

def _get_village_gdf():
    global _VILLAGE_GDF
    if _VILLAGE_GDF is None:
        p = PROJECT_ROOT / "data_real" / "admin" / "raw" / "LGD_Villages.parquet"
        if p.exists():
            _VILLAGE_GDF = gpd.read_parquet(p)
    return _VILLAGE_GDF

def _get_streams_gdf():
    global _STREAMS_GDF
    if _STREAMS_GDF is None:
        p = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "hydro_rivers_india.parquet"
        if p.exists():
            _STREAMS_GDF = gpd.read_parquet(p)
    return _STREAMS_GDF

def _get_catchments_gdf():
    global _CATCHMENTS_GDF
    if _CATCHMENTS_GDF is None:
        p = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "hydrobasins_india_lev08.parquet"
        if p.exists():
            _CATCHMENTS_GDF = gpd.read_parquet(p)
            _CATCHMENTS_GDF = _CATCHMENTS_GDF.to_crs(epsg=4326)
    return _CATCHMENTS_GDF

@router.get("/geojson/villages/bbox", summary="Lazy-load Village geometries by BBox (Gate J)")
async def serve_villages_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    gdf = _get_village_gdf()
    if gdf is None:
        return {"type": "FeatureCollection", "features": []}
    clipped = gdf.cx[min_lon:max_lon, min_lat:max_lat]
    if len(clipped) > 1000:
        clipped = clipped.head(1000) # prevent browser crash
    return json.loads(clipped.to_json())

@router.get("/geojson/streams/bbox", summary="Lazy-load Stream geometries by BBox")
async def serve_streams_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    gdf = _get_streams_gdf()
    if gdf is None:
        return {"type": "FeatureCollection", "features": []}
    clipped = gdf.cx[min_lon:max_lon, min_lat:max_lat]
    if len(clipped) > 1000:
        clipped = clipped.head(1000)
    return json.loads(clipped.to_json())

@router.get("/geojson/catchments/bbox", summary="Lazy-load Catchment geometries by BBox")
async def serve_catchments_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    gdf = _get_catchments_gdf()
    if gdf is None:
        return {"type": "FeatureCollection", "features": []}
    clipped = gdf.cx[min_lon:max_lon, min_lat:max_lat]
    return json.loads(clipped.to_json())

@router.get("/geojson/{filename}", summary="Serve GADM GeoJSON for MapLibre (Gate J)")
async def serve_geojson(filename: str):
    """Serve pre-generated simplified GADM GeoJSON for MapLibre prototype."""
    allowed = {
        "states_india.geojson", "districts_india.geojson",
        "districts_pilot.geojson", "subdistricts_pilot.geojson",
        "layers_meta.json",
    }
    if filename not in allowed:
        from fastapi import HTTPException
        raise HTTPException(404, detail=f"Unknown file: {filename}")
    path = GEOJSON_DIR / filename
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, detail=f"{filename} not yet generated — run export_geojson_pilot.py")
    return FileResponse(str(path), media_type="application/json",
                        headers={"Cache-Control": "public, max-age=3600"})


# ── Event inventory ────────────────────────────────────────────────────────────

@router.get("/events/flood", summary="Flood event catalogue v2 (Gate A)")
async def flood_events():
    import pandas as pd
    p = PROJECT_ROOT / "data_real" / "events" / "flood" / "processed" / "flood_events_v2.parquet"
    if not p.exists():
        return {**RESEARCH_HEADER, "events": [], "note": "Run expand_flood_events.py"}
    try:
        df = pd.read_parquet(p)
        return {
            **RESEARCH_HEADER,
            "n_events": len(df),
            "gate_a_status": "PASS" if len(df) >= 10 else "NEEDS_MORE_EVENTS",
            "events": df.to_dict(orient="records"),
        }
    except Exception as e:
        return {**RESEARCH_HEADER, "error": str(e)}


@router.get("/events/landslide", summary="Landslide event catalogue v2 (Gate B)")
async def landslide_events():
    import pandas as pd
    p = PROJECT_ROOT / "data_real" / "events" / "landslide" / "processed" / "landslide_events_v2.parquet"
    if not p.exists():
        return {**RESEARCH_HEADER, "events": [], "note": "Run expand_landslide_events.py"}
    try:
        df = pd.read_parquet(p)
        return {
            **RESEARCH_HEADER,
            "n_events": len(df),
            "gate_b_status": "PASS" if len(df) >= 30 else "NEEDS_MORE_EVENTS",
            "note": f"{len(df)} curated events. Need >=30 dated dynamic for model training.",
            "events": df.to_dict(orient="records"),
        }
    except Exception as e:
        return {**RESEARCH_HEADER, "error": str(e)}


# ── Gate L: Observation coverage schema ───────────────────────────────────────

@router.get("/coverage-schema", summary="Per-region observation coverage flags (Gate L)")
async def coverage_schema():
    """Raw coverage flags per region. No collapsed score."""
    schema = {
        "uttarakhand":          {"rain_source": "CHIRPS", "river_source": "MANUAL_REQUIRED", "terrain_source": "GLO30_partial",  "label_source": "DFO_NDMA",    "label_spatial_precision": "region_wide"},
        "kerala_wayanad":       {"rain_source": "CHIRPS", "river_source": "MANUAL_REQUIRED", "terrain_source": "NONE",           "label_source": "DFO_KSNDMC",  "label_spatial_precision": "region_wide"},
        "assam":                {"rain_source": "CHIRPS", "river_source": "MANUAL_REQUIRED", "terrain_source": "NONE",           "label_source": "ASDMA_CWC",   "label_spatial_precision": "region_wide"},
        "bihar_ganga_plains":   {"rain_source": "CHIRPS_downloading", "river_source": "MANUAL_REQUIRED", "terrain_source": "NONE", "label_source": "NDMA_CWC",  "label_spatial_precision": "district_wide"},
        "odisha_coastal":       {"rain_source": "CHIRPS_downloading", "river_source": "MANUAL_REQUIRED", "terrain_source": "NONE", "label_source": "IMD_OSDMA", "label_spatial_precision": "district_wide"},
        "odisha_mahanadi":      {"rain_source": "CHIRPS_downloading", "river_source": "MANUAL_REQUIRED", "terrain_source": "NONE", "label_source": "CWC_OSDMA", "label_spatial_precision": "district_wide"},
        "maharashtra_kolhapur": {"rain_source": "CHIRPS_downloading", "river_source": "MANUAL_REQUIRED", "terrain_source": "NONE", "label_source": "NDMA_IMD",  "label_spatial_precision": "district_wide"},
        "himachal_pradesh":     {"rain_source": "CHIRPS_downloading", "river_source": "MANUAL_REQUIRED", "terrain_source": "GLO30_planned", "label_source": "HPSDMA_NDMA", "label_spatial_precision": "district_wide"},
    }
    return {
        **RESEARCH_HEADER,
        "schema_version": "v2",
        "note": "Raw per-region flags. No collapsed confidence. CHIRPS_downloading = in progress.",
        "data_coverage_flags": schema,
        "nationwide_predictions": False,
    }


def _haversine_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _route_min_distance_km(geometry: dict, block_lat: float, block_lon: float) -> float:
    """Minimum distance in km from any vertex of a LineString route to a point."""
    coords = geometry.get("coordinates", [])
    if not coords:
        return float("inf")
    return min(_haversine_km(block_lat, block_lon, lat, lon) for lon, lat in coords)

def _nearest_segment_bearing(coords, block_lat, block_lon):
    """Bearing (degrees) of the route segment closest to the block point."""
    import math
    best_i, best_dist = 0, float("inf")
    for i, (lon, lat) in enumerate(coords):
        d = _haversine_km(block_lat, block_lon, lat, lon)
        if d < best_dist:
            best_dist, best_i = d, i
    j = min(best_i + 1, len(coords) - 1)
    lon1, lat1 = coords[best_i]
    lon2, lat2 = coords[j]
    return math.atan2(lon2 - lon1, lat2 - lat1)  # radians, arbitrary reference — only used relatively

def _offset_point_km(lat, lon, bearing_rad, distance_km):
    """Offset a lat/lon by distance_km along bearing_rad (perpendicular trick, small-distance approx)."""
    import math
    dlat = (distance_km / 110.574) * math.cos(bearing_rad)
    dlon = (distance_km / (111.320 * math.cos(math.radians(lat)))) * math.sin(bearing_rad)
    return lat + dlat, lon + dlon

async def _osrm_route(client, base_url, waypoints, alternatives=False):
    """waypoints: list of (lat, lon). Returns parsed OSRM JSON, or None on any failure
    (bad status, timeout, no route) — callers treat None as "this candidate didn't pan out"
    rather than aborting the whole request."""
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
    url = f"{base_url}/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    if alternatives:
        url += "&alternatives=true"
    try:
        resp = await client.get(url, timeout=10.0)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    return data

BLOCK_RADIUS_KM = 0.3

@router.get("/evacuation/route", summary="Real OSM evacuation routing (blocked-road aware)")
async def evacuation_route(start_lat: float, start_lon: float, dest_lat: float, dest_lon: float):
    import httpx, os
    base_url = os.getenv("ROUTING_BASE_URL", "http://router.project-osrm.org")
    try:
        async with httpx.AsyncClient() as client:
            data = await _osrm_route(client, base_url, [(start_lat, start_lon), (dest_lat, dest_lon)], alternatives=True)
            if data is None:
                return {**RESEARCH_HEADER, "error": "NoRoute", "details": "OSRM could not find a route."}

            candidates = data["routes"]
            route = candidates[0]
            rerouted = False
            block_acknowledged = False
            reroute_method = None
            avoided_labels = []

            # Reroute around any actively-reported road blocks (shared demo state).
            from backend.demo_state import road_blocks as blocked_roads
            if blocked_roads:
                default_min_dist = min(
                    _route_min_distance_km(route["geometry"], b["lat"], b["lon"])
                    for b in blocked_roads.values()
                )
                if default_min_dist < BLOCK_RADIUS_KM:
                    block_acknowledged = True
                    best, best_score = route, default_min_dist

                    # 1) Prefer a genuine OSRM alternative if one exists and clears the block.
                    for cand in candidates[1:]:
                        cand_min_dist = min(
                            _route_min_distance_km(cand["geometry"], b["lat"], b["lon"])
                            for b in blocked_roads.values()
                        )
                        if cand_min_dist > best_score:
                            best, best_score = cand, cand_min_dist
                    if best is not route and best_score >= BLOCK_RADIUS_KM:
                        route, rerouted, reroute_method = best, True, "osrm_alternative"

                    # 2) No real alternative road: force a detour waypoint around the nearest
                    #    block and see if OSRM can find a materially different path via it.
                    #    Clearly labelled as a demo-only detour, not a verified safe road.
                    if not rerouted:
                        blocker = min(
                            blocked_roads.values(),
                            key=lambda b: _route_min_distance_km(route["geometry"], b["lat"], b["lon"]),
                        )
                        bearing = _nearest_segment_bearing(route["geometry"]["coordinates"], blocker["lat"], blocker["lon"])
                        for offset_km in (0.6, 1.2, 2.0, 3.5):
                            for side in (1, -1):
                                off_lat, off_lon = _offset_point_km(
                                    blocker["lat"], blocker["lon"], bearing + side * 1.5708, offset_km
                                )
                                detour = await _osrm_route(
                                    client, base_url,
                                    [(start_lat, start_lon), (off_lat, off_lon), (dest_lat, dest_lon)],
                                )
                                if detour is None:
                                    continue
                                cand = detour["routes"][0]
                                cand_score = min(
                                    _route_min_distance_km(cand["geometry"], b["lat"], b["lon"])
                                    for b in blocked_roads.values()
                                )
                                if cand_score > best_score:
                                    best, best_score = cand, cand_score
                            if best_score >= BLOCK_RADIUS_KM:
                                break  # stop widening once we've found a real detour
                        if best is not route and best_score >= BLOCK_RADIUS_KM:
                            route, rerouted, reroute_method = best, True, "waypoint_detour"

                    if rerouted:
                        avoided_labels = [b["label"] for b in blocked_roads.values()]

            warning = "OSM road route to selected facility (Research routing using OpenStreetMap road network — not an emergency navigation service)."
            if reroute_method == "waypoint_detour":
                warning += " Rerouted via a demo detour waypoint around the reported block — not an independently-verified alternate road."
            elif block_acknowledged and not rerouted:
                warning += " A road block was reported near this route but no clear alternate road could be found — proceed with caution."

            return {
                **RESEARCH_HEADER,
                "type": "Feature",
                "geometry": route["geometry"],
                "properties": {
                    "distance_m": route.get("distance", 0),
                    "duration_s": route.get("duration", 0),
                    "provider": "OSRM",
                    "provenance": "OpenStreetMap road network",
                    "warning": warning,
                    "rerouted": rerouted,
                    "reroute_method": reroute_method,
                    "block_acknowledged": block_acknowledged,
                    "avoided": avoided_labels,
                }
            }
    except Exception as e:
        return {**RESEARCH_HEADER, "error": f"Routing exception: {str(e)}"}


@router.get("/routing/health", summary="OSRM routing service reachability check")
async def routing_health():
    """Lightweight liveness probe for the Technical/Admin data-source health
    panel — a real request against a tiny fixed pair of coordinates, not a
    cached/assumed status."""
    import httpx, os, time
    base_url = os.getenv("ROUTING_BASE_URL", "http://router.project-osrm.org")
    url = f"{base_url}/route/v1/driving/76.9327,31.7119;77.0184,31.79778?overview=false"
    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
        elapsed_ms = round((time.monotonic() - started) * 1000)
        if resp.status_code == 200 and resp.json().get("code") == "Ok":
            return {"status": "AVAILABLE", "provider": "OSRM", "latency_ms": elapsed_ms}
        return {"status": "UNREACHABLE", "provider": "OSRM", "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "UNREACHABLE", "provider": "OSRM", "detail": str(e)}

