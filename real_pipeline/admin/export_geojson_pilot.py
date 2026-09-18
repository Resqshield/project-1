# -*- coding: utf-8 -*-
"""
real_pipeline/admin/export_geojson_pilot.py
============================================
Export pilot-region admin boundaries as GeoJSON for MapLibre prototype.

Strategy:
  - Full India state boundaries → states.geojson (compact, simplified)
  - Pilot region districts → districts_pilot.geojson
  - Full district GeoJSON → districts_india.geojson (for vector tiles)

Note: We use simplified geometries (Douglas-Peucker) to keep tile sizes small.
Simplification tolerance: 0.01 deg for state, 0.005 deg for district.

Output: data_real/admin/processed/geojson/
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("export_geojson")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMIN_DIR = PROJECT_ROOT / "data_real" / "admin" / "processed"
OUT_DIR   = ADMIN_DIR / "geojson"

PILOT_STATES = ["Uttarakhand", "Kerala", "Assam", "Bihar", "Odisha", "Maharashtra",
                "Himachal Pradesh", "Manipur", "Mizoram", "Karnataka"]


def load_admin(level: str) -> gpd.GeoDataFrame:
    path = ADMIN_DIR / f"{level}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Admin parquet not found: {path}")
    gdf = gpd.read_parquet(path)
    return gdf


def simplify_and_export(gdf: gpd.GeoDataFrame, path: Path,
                        tolerance: float = 0.01) -> dict:
    """Simplify geometry, ensure CRS, export GeoJSON. Return stats."""
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    orig_size = gdf.memory_usage(deep=True).sum()
    gdf_s = gdf.copy()
    gdf_s["geometry"] = gdf_s["geometry"].simplify(tolerance, preserve_topology=True)

    # Drop heavy columns, keep key identifiers
    drop_cols = [c for c in gdf_s.columns
                 if c not in ["geometry", "state_code", "state_name", "district_code",
                              "district_name", "subdistrict_code", "subdistrict_name",
                              "state_name", "hasc_code", "level"]]
    gdf_s = gdf_s.drop(columns=[c for c in drop_cols if c in gdf_s.columns])

    path.parent.mkdir(parents=True, exist_ok=True)
    gdf_s.to_file(str(path), driver="GeoJSON")

    size_kb = path.stat().st_size / 1024
    log.info(f"  Exported: {path.name} ({size_kb:.0f} KB, {len(gdf_s)} features, "
             f"simplified={tolerance})")
    return {"path": str(path), "n_features": len(gdf_s), "size_kb": round(size_kb, 1),
            "simplification": tolerance}


def main():
    log.info("=" * 60)
    log.info("ResQ Shield — GeoJSON Export for MapLibre Prototype")
    log.info("=" * 60)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # States — full India
    log.info("\nExporting states (full India)...")
    states = load_admin("states")
    log.info(f"  Loaded {len(states)} states")
    r = simplify_and_export(states, OUT_DIR / "states_india.geojson", tolerance=0.02)
    results["states_india"] = r

    # Districts — full India (simplified for overview zoom)
    log.info("\nExporting districts (full India, simplified)...")
    districts = load_admin("districts")
    log.info(f"  Loaded {len(districts)} districts")
    r = simplify_and_export(districts, OUT_DIR / "districts_india.geojson", tolerance=0.01)
    results["districts_india"] = r

    # Pilot states only (higher quality for prototype)
    log.info("\nExporting pilot districts...")
    pilot_districts = districts[districts["state_name"].isin(PILOT_STATES)]
    log.info(f"  Pilot districts: {len(pilot_districts)}")
    r = simplify_and_export(pilot_districts, OUT_DIR / "districts_pilot.geojson", tolerance=0.005)
    results["districts_pilot"] = r

    # Sub-districts — pilot states only (finer detail)
    log.info("\nExporting pilot sub-districts...")
    subdistricts = load_admin("subdistricts")
    pilot_subs = subdistricts[subdistricts["state_name"].isin(PILOT_STATES)]
    log.info(f"  Pilot sub-districts: {len(pilot_subs)}")
    r = simplify_and_export(pilot_subs, OUT_DIR / "subdistricts_pilot.geojson", tolerance=0.002)
    results["subdistricts_pilot"] = r

    # Summary JSON (for MapLibre to know available layers)
    layers_meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": "GADM v4.1",
        "data_type": "REAL_DATA — NOT SYNTHETIC",
        "license": "Non-commercial research use — gadm.org/license.html",
        "layers": {
            "states": {
                "file": "states_india.geojson",
                "zoom_min": 4, "zoom_max": 7,
                "n_features": results["states_india"]["n_features"],
                "size_kb": results["states_india"]["size_kb"],
            },
            "districts": {
                "file": "districts_india.geojson",
                "zoom_min": 6, "zoom_max": 9,
                "n_features": results["districts_india"]["n_features"],
                "size_kb": results["districts_india"]["size_kb"],
            },
            "districts_pilot": {
                "file": "districts_pilot.geojson",
                "zoom_min": 7, "zoom_max": 10,
                "n_features": results["districts_pilot"]["n_features"],
                "size_kb": results["districts_pilot"]["size_kb"],
            },
            "subdistricts_pilot": {
                "file": "subdistricts_pilot.geojson",
                "zoom_min": 9, "zoom_max": 12,
                "n_features": results["subdistricts_pilot"]["n_features"],
                "size_kb": results["subdistricts_pilot"]["size_kb"],
            },
        },
        "village_layer": "MANUAL_REQUIRED — LGD/Census 2011 village polygons needed",
    }

    with open(OUT_DIR / "layers_meta.json", "w") as f:
        json.dump(layers_meta, f, indent=2)

    log.info(f"\n{'='*50}")
    log.info("GeoJSON Export Summary:")
    for name, r in results.items():
        log.info(f"  {name}: {r['n_features']} features, {r['size_kb']:.0f} KB")
    log.info(f"\nLayers meta: {OUT_DIR}/layers_meta.json")


if __name__ == "__main__":
    main()
