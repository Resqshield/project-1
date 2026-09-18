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


@router.get("/evacuation/route", summary="Real OSM evacuation routing")
async def evacuation_route(start_lat: float, start_lon: float, dest_lat: float, dest_lon: float):
    import httpx, os
    base_url = os.getenv("ROUTING_BASE_URL", "http://router.project-osrm.org")
    url = f"{base_url}/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code != 200:
                return {**RESEARCH_HEADER, "error": f"OSRM API error: {resp.status_code}", "details": resp.text}
            data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return {**RESEARCH_HEADER, "error": "NoRoute", "details": "OSRM could not find a route."}
            route = data["routes"][0]
            return {
                **RESEARCH_HEADER,
                "type": "Feature",
                "geometry": route["geometry"],
                "properties": {
                    "distance_m": route.get("distance", 0),
                    "duration_s": route.get("duration", 0),
                    "provider": "OSRM",
                    "provenance": "OpenStreetMap road network",
                    "warning": "OSM road route to selected facility (Research routing using OpenStreetMap road network — not an emergency navigation service)."
                }
            }
    except Exception as e:
        return {**RESEARCH_HEADER, "error": f"Routing exception: {str(e)}"}

