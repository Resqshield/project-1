# -*- coding: utf-8 -*-
"""
real_pipeline/hydrology/ingest_hydrobasins.py
===============================================
Download and process HydroBASINS Level 7 (India/South Asia) catchments.

HydroBASINS:
  - Source: HydroSHEDS / HydroBASINS project (WWF/USGS)
  - URL: https://www.hydrosheds.org/products/hydrobasins
  - License: Free for non-commercial academic/research use
  - Format: Shapefile or GeoPackage
  - Level 7: avg catchment area ~1,000 km² (suitable for regional analysis)
  - Level 8: avg catchment area ~250 km² (finer, preferred for village linkage)

STRATEGY:
  1. Download South Asia sub-basin shapefile from HydroSHEDS mirror
  2. Clip to India extent (3.5°N - 37.5°N, 66.5°E - 98.0°E)
  3. Validate geometry, area, unique IDs
  4. Build pilot linkage for existing pilot regions

OUTPUT:
  data_real/hydrology/catchments/hydrobasins_india_l7.parquet
  data_real/hydrology/catchments/hydrobasins_india_l8.parquet (if available)
  data_real/hydrology/catchments/hydrobasins_report.json

VILLAGE-CATCHMENT LINKAGE:
  Run after GADM admin data is available.
  Links: village_code -> dominant_catchment_id + overlap_fraction
  Script: build_village_catchment_link.py (separate)
"""

import json
import logging
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest_hydrobasins")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data_real" / "hydrology" / "catchments" / "hydrobasins"
RAW_DIR = PROJECT_ROOT / "data_real" / "hydrology" / "catchments"

INDIA_BOUNDS = {
    "minx": 66.5, "miny": 3.5, "maxx": 98.0, "maxy": 37.5
}

# HydroBASINS South Asia direct download URLs
# Multiple mirrors tried in sequence
HYDROBASINS_URLS = {
    "level7_as_south": [
        # HydroSHEDS direct (requires registration but data is free)
        "https://data.hydrosheds.org/file/HydroBASINS/standard/as/hybas_as_lev07_v1c.zip",
        # Alternate mirror (may work without login)
        "https://hydrosheds.cr.usgs.gov/as/hybas_as_lev07_v1c.zip",
    ],
    "level8_as_south": [
        "https://data.hydrosheds.org/file/HydroBASINS/standard/as/hybas_as_lev08_v1c.zip",
    ],
}


def try_download(urls: list, out_path: Path) -> bool:
    """Try downloading from multiple URLs."""
    for url in urls:
        log.info(f"  Trying: {url}")
        try:
            resp = requests.get(url, stream=True, timeout=60,
                               headers={"User-Agent": "ResQShield-Research/1.0"})
            if resp.status_code == 403:
                log.warning(f"  403 Forbidden — HydroSHEDS requires registration for direct download")
                log.warning(f"  See: https://www.hydrosheds.org/products/hydrobasins")
                continue
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and downloaded % (10 * 1024 * 1024) < 1024 * 1024:
                        log.info(f"  Progress: {100*downloaded/total:.0f}%")
            log.info(f"  Downloaded: {out_path} ({downloaded/1e6:.1f} MB)")
            return True
        except requests.exceptions.HTTPError as e:
            log.warning(f"  HTTP error: {e}")
        except requests.exceptions.Timeout:
            log.warning(f"  Timeout")
        except Exception as e:
            log.warning(f"  Error: {type(e).__name__}: {e}")
    return False


def clip_to_india(gdf: "gpd.GeoDataFrame") -> "gpd.GeoDataFrame":
    """Clip GeoDataFrame to India extent."""
    from shapely.geometry import box
    india_box = box(INDIA_BOUNDS["minx"], INDIA_BOUNDS["miny"],
                    INDIA_BOUNDS["maxx"], INDIA_BOUNDS["maxy"])
    return gdf[gdf.geometry.intersects(india_box)].copy()


def validate_hydrobasins(gdf: "gpd.GeoDataFrame", level: int) -> dict:
    """Validate HydroBASINS data."""
    report = {
        "level": level,
        "n_catchments": len(gdf),
        "n_unique_ids": gdf["HYBAS_ID"].nunique() if "HYBAS_ID" in gdf.columns else "N/A",
        "n_duplicate_ids": int(gdf["HYBAS_ID"].duplicated().sum()) if "HYBAS_ID" in gdf.columns else 0,
        "n_valid_geoms": int(gdf.geometry.is_valid.sum()),
        "n_invalid_geoms": int((~gdf.geometry.is_valid).sum()),
        "total_area_km2": float(gdf["SUB_AREA"].sum()) if "SUB_AREA" in gdf.columns else None,
        "mean_area_km2": float(gdf["SUB_AREA"].mean()) if "SUB_AREA" in gdf.columns else None,
    }
    report["pass"] = (report["n_duplicate_ids"] == 0 and
                      report["n_invalid_geoms"] == 0 and
                      report["n_catchments"] > 0)
    return report


def main():
    import geopandas as gpd

    log.info("=" * 65)
    log.info("ResQ Shield — HydroBASINS Ingestion  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    for level, level_key in [(7, "level7_as_south"), (8, "level8_as_south")]:
        zip_path = RAW_DIR / f"hybas_as_lev0{level}_v1c.zip"
        gpkg_out = OUT_DIR / f"hydrobasins_india_l{level}.parquet"

        if gpkg_out.exists():
            log.info(f"\nLevel {level} already processed: {gpkg_out}")
            results[f"level{level}"] = {"status": "ALREADY_DONE", "path": str(gpkg_out)}
            continue

        log.info(f"\n{'='*40}")
        log.info(f"Processing HydroBASINS Level {level}...")

        urls = HYDROBASINS_URLS.get(level_key, [])
        downloaded = try_download(urls, zip_path)

        if not downloaded:
            log.warning(f"  Level {level} download FAILED — MANUAL_REQUIRED")
            results[f"level{level}"] = {
                "status": "MANUAL_REQUIRED",
                "urls": urls,
                "action": (
                    f"Register at hydrosheds.org, download hybas_as_lev0{level}_v1c.zip, "
                    f"place in {RAW_DIR}/"
                ),
            }
            continue

        # Extract shapefile
        log.info(f"  Extracting ZIP...")
        extract_dir = RAW_DIR / f"hydrobasins_l{level}"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # Find shapefile
        shp_files = list(extract_dir.glob("*.shp"))
        if not shp_files:
            log.error(f"  No shapefile found in {extract_dir}")
            results[f"level{level}"] = {"status": "ERROR", "reason": "No .shp in ZIP"}
            continue

        # Load and clip
        log.info(f"  Loading shapefile: {shp_files[0].name}")
        gdf = gpd.read_file(shp_files[0], engine="pyogrio")
        log.info(f"  Total features (Asia): {len(gdf)}")

        gdf_india = clip_to_india(gdf)
        log.info(f"  Clipped to India: {len(gdf_india)} catchments")

        if len(gdf_india) == 0:
            log.error("  No catchments found in India bounds!")
            results[f"level{level}"] = {"status": "ERROR", "reason": "No India features"}
            continue

        # Validate
        report = validate_hydrobasins(gdf_india, level)
        log.info(f"  Validation: {report}")

        # Add metadata
        gdf_india["level"] = level
        gdf_india["data_source"] = "HydroBASINS_v1c"
        gdf_india["data_type"] = "REAL_DATA — NOT SYNTHETIC"
        gdf_india["ingested_at"] = datetime.now(timezone.utc).isoformat()

        # Save
        try:
            gdf_india.to_parquet(str(gpkg_out), index=False, engine="pyarrow")
            log.info(f"  Saved GeoParquet: {gpkg_out}")
        except Exception as e:
            log.warning(f"  GeoParquet failed: {e}. Saving without geometry...")
            df_out = gdf_india.drop(columns=["geometry"], errors="ignore")
            df_out.to_parquet(str(gpkg_out), index=False)

        gdf_india.drop(columns=["geometry"]).to_csv(
            str(OUT_DIR / f"hydrobasins_india_l{level}.csv"), index=False)

        results[f"level{level}"] = {"status": "SUCCESS", **report}

    # Summary
    any_success = any(v.get("status") == "SUCCESS" for v in results.values())
    all_manual = all(v.get("status") == "MANUAL_REQUIRED" for v in results.values())

    gate_d_status = (
        "PILOT_READY" if any_success
        else "MANUAL_REQUIRED" if all_manual
        else "PARTIAL"
    )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_type": "REAL_DATA — NOT SYNTHETIC",
        "source": "HydroBASINS v1c (HydroSHEDS)",
        "license": "Free non-commercial research — hydrosheds.org",
        "gate_d_decision": gate_d_status,
        "results": results,
        "village_catchment_linkage": "NOT_YET — run build_village_catchment_link.py after admin data ready",
        "note": (
            "HydroSHEDS requires free registration for direct bulk download. "
            "If MANUAL_REQUIRED: register at hydrosheds.org, download, place in "
            f"{RAW_DIR}/"
        ),
    }
    with open(OUT_DIR / "hydrobasins_report.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    log.info(f"\nGate D: {gate_d_status}")
    log.info(f"Report: {OUT_DIR}/hydrobasins_report.json")


if __name__ == "__main__":
    main()
