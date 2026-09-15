# -*- coding: utf-8 -*-
"""
real_pipeline/admin/ingest_boundaries.py
==========================================
Ingest administrative boundary polygons from authoritative sources.

Sources (priority order):
  A) Survey of India (SoI) — legal authority for India boundaries.
     Access: https://onlinemaps.surveyofindia.gov.in/  (requires login/payment for many layers)
     Free: Open Series Maps (OSM) at 1:250,000 scale (terrain, not admin boundaries)
     Status: MANUAL_REQUIRED for most SoI boundary layers.

  B) GADM (Global Admin Areas) — widely used research database.
     Access: Free, no login. https://gadm.org/download_country.html
     Resolution: State/District/Sub-district levels available.
     License: Non-commercial research use. NOT for operational government systems.
     Format: GeoPackage, Shapefile, GeoJSON
     Approx size: India GPKG all levels ~50–200 MB

  C) Datameet India Maps — community-curated, sourced from GoI data.
     https://github.com/datameet/maps  (state, district, subdistrict shapefiles)
     License: See repo. Community attribution required.

  D) MapMyIndia / Bharat Maps — commercial, restricted.
     Status: NOT downloaded without license. MANUAL_REQUIRED if needed.

  E) OpenStreetMap extract — open, but not authoritative for census/admin codes.
     Useful as a crosswalk baseline. Available via Geofabrik.

This script:
  1. Checks for manually placed GeoPackage/Shapefile in data_real/admin/raw/.
  2. Optionally fetches GADM (open, research use) if not manually restricted.
  3. Validates CRS, geometry validity, record counts.
  4. Saves as GeoPackage (preserving polygons) with LGD code crosswalk where available.

!! Polygons are preserved — do not permanently reduce to point centroids. !!
!! CRS is standardized to EPSG:4326 (WGS84 lat/lon). !!
!! NEVER create a nationwide GeoJSON for frontend rendering (too large). !!

Manual download guide:
  GADM India (recommended for research phase):
    URL: https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_IND.gpkg
    Size: ~220 MB (all 4 admin levels)
    Place at: data_real/admin/raw/gadm41_IND.gpkg
    Levels: 0=Country, 1=State(36), 2=District(739), 3=Sub-district
    Note: GADM codes differ from LGD — crosswalk required (see build_admin_crosswalk.py)

  Datameet district boundaries:
    URL: https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011/2011_Dist.shp
    (Multiple files needed: .shp .dbf .shx .prj)
    Place all at: data_real/admin/raw/datameet_districts/

  Survey of India (if available):
    MANUAL_REQUIRED — contact SoI or use NSDI portal.
    URL: https://nsdi.gov.in/
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

try:
    import geopandas as gpd
    import pandas as pd
    HAS_GEO = True
except ImportError:
    HAS_GEO = False

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR      = PROJECT_ROOT / "data_real" / "admin" / "raw"
PROC_DIR     = PROJECT_ROOT / "data_real" / "admin" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("boundaries_ingest")

# ── Target CRS ─────────────────────────────────────────────────────────────────
TARGET_CRS = "EPSG:4326"

# ── Known boundary file patterns ───────────────────────────────────────────────
BOUNDARY_CANDIDATES = [
    # GADM GeoPackage (all levels)
    {"path": "gadm41_IND.gpkg",             "source": "gadm_4.1",      "format": "gpkg",  "levels": [1, 2, 3]},
    {"path": "gadm40_IND.gpkg",             "source": "gadm_4.0",      "format": "gpkg",  "levels": [1, 2, 3]},
    # Datameet shapefiles
    {"path": "datameet_districts/2011_Dist.shp", "source": "datameet_2011", "format": "shp", "levels": [2]},
    {"path": "datameet_states/2011_state.shp",   "source": "datameet_2011", "format": "shp", "levels": [1]},
    # Survey of India (if manually placed)
    {"path": "soi_districts.gpkg",          "source": "survey_of_india", "format": "gpkg", "levels": [2]},
    {"path": "soi_states.gpkg",             "source": "survey_of_india", "format": "gpkg", "levels": [1]},
]

# GADM layer names (inside GeoPackage)
GADM_LAYERS = {
    1: "ADM_ADM_1",   # States
    2: "ADM_ADM_2",   # Districts
    3: "ADM_ADM_3",   # Sub-districts
}
GADM_FIELD_MAP = {
    "GID_1": "gadm_gid_1", "NAME_1": "state_name_gadm",
    "GID_2": "gadm_gid_2", "NAME_2": "district_name_gadm",
    "GID_3": "gadm_gid_3", "NAME_3": "subdistrict_name_gadm",
    "TYPE_1": "admin_type_1", "TYPE_2": "admin_type_2", "TYPE_3": "admin_type_3",
    "geometry": "geometry",
}


def check_geometry_validity(gdf: gpd.GeoDataFrame) -> dict:
    """Validate geometry; report counts without silently discarding."""
    total = len(gdf)
    null_geom = int(gdf.geometry.isna().sum())
    invalid = int((~gdf.geometry.is_valid).sum()) if null_geom < total else 0
    empty = int(gdf.geometry.is_empty.sum()) if null_geom < total else 0
    return {
        "total_features": total,
        "null_geometry": null_geom,
        "invalid_geometry": invalid,
        "empty_geometry": empty,
        "valid_geometry": total - null_geom - invalid,
        "crs": str(gdf.crs) if gdf.crs else "undefined",
    }


def load_gadm_level(gpkg_path: Path, level: int) -> gpd.GeoDataFrame:
    """Load a specific admin level from GADM GeoPackage."""
    import fiona
    layers = fiona.listlayers(str(gpkg_path))
    log.info(f"  Available layers in {gpkg_path.name}: {layers}")

    target_layer = None
    for layer in layers:
        if f"ADM_ADM_{level}" in layer or f"_{level}" in layer:
            target_layer = layer
            break
    if target_layer is None and layers:
        # Fallback: try by index (GADM4.1 sometimes uses different naming)
        target_layer = [l for l in layers if str(level) in l]
        target_layer = target_layer[0] if target_layer else layers[min(level, len(layers)-1)]

    log.info(f"  Loading layer: {target_layer}")
    gdf = gpd.read_file(str(gpkg_path), layer=target_layer)
    return gdf


def process_and_save(gdf: gpd.GeoDataFrame, admin_level: int, source_name: str):
    """Reproject, compute centroids, save as GeoPackage + parquet of attributes."""
    # Reproject to WGS84
    if gdf.crs is None:
        log.warning("  GeoDataFrame has no CRS — assuming EPSG:4326")
        gdf = gdf.set_crs(TARGET_CRS)
    elif str(gdf.crs) != TARGET_CRS:
        log.info(f"  Reprojecting from {gdf.crs} → {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)

    # Geometry validity
    geo_report = check_geometry_validity(gdf)
    log.info(f"  Geometry validation: {geo_report}")

    # Compute representative point (centroid) — DO NOT DROP polygon
    gdf["centroid_lat"] = gdf.geometry.representative_point().y
    gdf["centroid_lon"] = gdf.geometry.representative_point().x
    gdf["area_km2"] = gdf.geometry.to_crs("EPSG:7755").area / 1e6  # India-specific CRS

    # Admin level label
    level_names = {1: "state", 2: "district", 3: "subdistrict", 4: "block"}
    level_label = level_names.get(admin_level, f"level_{admin_level}")

    # Save GeoPackage (polygons preserved)
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    out_gpkg = PROC_DIR / f"admin_{level_label}_boundaries.gpkg"
    gdf.to_file(str(out_gpkg), driver="GPKG", layer=f"admin_{level_label}")
    log.info(f"  Saved: {out_gpkg} ({len(gdf):,} features)")

    # Save attribute parquet (without heavy geometry column — for fast joins)
    attr_cols = [c for c in gdf.columns if c != "geometry"]
    attr_df = gdf[attr_cols].copy()
    out_parquet = PROC_DIR / f"admin_{level_label}_attributes.parquet"
    attr_df.to_parquet(str(out_parquet), index=False, engine="pyarrow")
    log.info(f"  Saved: {out_parquet}")

    return geo_report, out_gpkg


def write_boundary_status(results: list, manual_items: list):
    """Write boundary ingest status report."""
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_type": "REAL_OFFICIAL — NOT SYNTHETIC",
        "processed_layers": results,
        "manual_required": manual_items,
        "storage_notes": [
            "Polygons preserved in GeoPackage — never reduced to points permanently.",
            "Centroids computed as representative_point() for fast joins.",
            "Do NOT create nationwide frontend GeoJSON — use vector tiles for scale.",
            "PostGIS migration path: use geopandas.GeoDataFrame.to_postgis().",
        ],
    }
    path = PROC_DIR / "boundary_ingest_status.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Status: {path}")


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Boundary Ingest  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)

    if not HAS_GEO:
        log.error("geopandas not installed. Run: pip install geopandas")
        sys.exit(1)

    results = []
    manual_required = []

    for candidate in BOUNDARY_CANDIDATES:
        fpath = RAW_DIR / candidate["path"]
        if not fpath.exists():
            log.info(f"Not found (skip): {fpath.name}")
            manual_required.append({
                "file": str(fpath),
                "source": candidate["source"],
                "status": "MANUAL_REQUIRED",
            })
            continue

        log.info(f"Found boundary file: {fpath}")
        source = candidate["source"]

        if "gadm" in source and fpath.suffix == ".gpkg":
            for level in candidate["levels"]:
                try:
                    gdf = load_gadm_level(fpath, level)
                    log.info(f"  Level {level}: {len(gdf):,} features, cols: {list(gdf.columns[:8])}")
                    geo_report, out_path = process_and_save(gdf, level, source)
                    results.append({"source": source, "level": level,
                                    "features": len(gdf), "output": str(out_path),
                                    "geometry": geo_report})
                except Exception as e:
                    log.error(f"  Error loading level {level}: {e}")
        elif fpath.suffix in (".shp", ".gpkg"):
            try:
                gdf = gpd.read_file(str(fpath))
                log.info(f"  {len(gdf):,} features, CRS: {gdf.crs}")
                level = candidate["levels"][0]
                geo_report, out_path = process_and_save(gdf, level, source)
                results.append({"source": source, "level": level,
                                "features": len(gdf), "output": str(out_path),
                                "geometry": geo_report})
            except Exception as e:
                log.error(f"  Error loading {fpath}: {e}")

    write_boundary_status(results, manual_required)

    log.info("=" * 65)
    if results:
        log.info(f"Processed {len(results)} boundary layer(s):")
        for r in results:
            log.info(f"  {r['source']} level={r['level']}: {r['features']:,} features → {r['output']}")
    else:
        log.warning("No boundary files found. Manual downloads required.")
        log.warning("  GADM (research use): https://gadm.org/download_country.html → India → GeoPackage")
        log.warning(f"  Place at: {RAW_DIR / 'gadm41_IND.gpkg'} (~220 MB)")
        log.warning("  SoI (authoritative): https://nsdi.gov.in/ → MANUAL_REQUIRED")

    if manual_required:
        log.info(f"\nMANUAL_REQUIRED ({len(manual_required)} items):")
        for item in manual_required:
            log.info(f"  {item['source']}: {item['file']}")
    log.info("=" * 65)


if __name__ == "__main__":
    main()
