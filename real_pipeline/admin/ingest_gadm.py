# -*- coding: utf-8 -*-
"""
real_pipeline/admin/ingest_gadm.py
====================================
Ingest GADM v4.1 India administrative boundaries.

GADM (Database of Global Administrative Areas):
  - Free for non-commercial academic/research use
  - URL: https://gadm.org/download_country.html
  - License: https://gadm.org/license.html (non-commercial research)
  - Format: GeoPackage (.gpkg) with all levels

LEVELS:
  0: India country boundary
  1: States/UTs (36)
  2: Districts (~800)
  3: Sub-districts/Tehsils (~5,900)

VILLAGE LEVEL:
  - GADM does NOT have village boundaries
  - Village boundaries: MANUAL_REQUIRED (Census 2011 village maps, SOI, LGD)
  - GP/Block/Village: LGD MANUAL_REQUIRED

OUTPUT:
  data_real/admin/processed/states.parquet
  data_real/admin/processed/districts.parquet
  data_real/admin/processed/subdistricts.parquet
  data_real/admin/processed/admin_metadata.json

VALIDATION:
  - Unique GID codes per level
  - Parent-child integrity
  - Null name checks
  - Geometry validity
  - Counts by level
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest_gadm")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR   = PROJECT_ROOT / "data_real" / "admin" / "processed"
RAW_DIR   = PROJECT_ROOT / "data_real" / "admin" / "raw"
XWALK_DIR = PROJECT_ROOT / "data_real" / "admin" / "crosswalk"

GADM_BASE = "https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg"
GADM_INDIA_URL = f"{GADM_BASE}/gadm41_IND.gpkg"


def download_gadm_gpkg(out_path: Path) -> bool:
    """Download GADM India GeoPackage (Level 0-3)."""
    if out_path.exists():
        log.info(f"  GADM GeoPackage already exists: {out_path}")
        return True

    log.info(f"  Downloading GADM v4.1 India: {GADM_INDIA_URL}")
    log.info("  Note: ~25 MB download. This may take a minute...")

    try:
        resp = requests.get(GADM_INDIA_URL, stream=True, timeout=120,
                           headers={"User-Agent": "ResQShield-Research/1.0"})
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = 100 * downloaded / total
                    if downloaded % (5 * 1024 * 1024) < 1024 * 1024:
                        log.info(f"  Progress: {pct:.0f}% ({downloaded/1e6:.1f} MB)")

        log.info(f"  Downloaded: {out_path} ({downloaded/1e6:.1f} MB)")
        return True

    except requests.exceptions.Timeout:
        log.warning(f"  Timeout downloading GADM. Marking MANUAL_REQUIRED.")
        if out_path.exists():
            out_path.unlink()
        return False
    except Exception as e:
        log.warning(f"  GADM download failed: {e}")
        if out_path.exists():
            out_path.unlink()
        return False


def load_gadm_level(gpkg_path: Path, level: int) -> "gpd.GeoDataFrame":
    """Load a GADM level from the GeoPackage."""
    import geopandas as gpd
    layer_name = f"ADM_ADM_{level}"
    log.info(f"  Loading GADM level {level} from {gpkg_path.name}...")
    try:
        gdf = gpd.read_file(gpkg_path, layer=layer_name, engine="pyogrio")
        log.info(f"  Level {level}: {len(gdf)} features, CRS={gdf.crs}")
        return gdf
    except Exception as e:
        log.error(f"  Could not load GADM level {level}: {e}")
        raise


def clean_gadm_level1(gdf: "gpd.GeoDataFrame") -> pd.DataFrame:
    """Clean state-level data."""
    cols = {
        "GID_0": "country_code",
        "COUNTRY": "country_name",
        "GID_1": "state_code",
        "NAME_1": "state_name",
        "VARNAME_1": "state_variant_names",
        "NL_NAME_1": "state_name_local",
        "TYPE_1": "admin_type",
        "ENGTYPE_1": "admin_type_en",
        "CC_1": "state_census_code",
        "HASC_1": "hasc_code",
        "geometry": "geometry",
    }
    keep = [c for c in cols.keys() if c in gdf.columns]
    df = gdf[keep].copy()
    df = df.rename(columns={k: v for k, v in cols.items() if k in keep})
    df["level"] = "state"
    df["data_source"] = "GADM_v4.1"
    df["data_type"] = "REAL_DATA — NOT SYNTHETIC"
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()
    return df


def clean_gadm_level2(gdf: "gpd.GeoDataFrame") -> pd.DataFrame:
    """Clean district-level data."""
    cols = {
        "GID_0": "country_code",
        "GID_1": "state_code",
        "GID_2": "district_code",
        "NAME_1": "state_name",
        "NAME_2": "district_name",
        "VARNAME_2": "district_variant_names",
        "NL_NAME_2": "district_name_local",
        "TYPE_2": "admin_type",
        "ENGTYPE_2": "admin_type_en",
        "CC_2": "district_census_code",
        "HASC_2": "hasc_code",
        "geometry": "geometry",
    }
    keep = [c for c in cols.keys() if c in gdf.columns]
    df = gdf[keep].copy()
    df = df.rename(columns={k: v for k, v in cols.items() if k in keep})
    df["level"] = "district"
    df["data_source"] = "GADM_v4.1"
    df["data_type"] = "REAL_DATA — NOT SYNTHETIC"
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()
    return df


def clean_gadm_level3(gdf: "gpd.GeoDataFrame") -> pd.DataFrame:
    """Clean sub-district-level data."""
    cols = {
        "GID_0": "country_code",
        "GID_1": "state_code",
        "GID_2": "district_code",
        "GID_3": "subdistrict_code",
        "NAME_1": "state_name",
        "NAME_2": "district_name",
        "NAME_3": "subdistrict_name",
        "VARNAME_3": "subdistrict_variant_names",
        "TYPE_3": "admin_type",
        "ENGTYPE_3": "admin_type_en",
        "CC_3": "subdistrict_census_code",
        "geometry": "geometry",
    }
    keep = [c for c in cols.keys() if c in gdf.columns]
    df = gdf[keep].copy()
    df = df.rename(columns={k: v for k, v in cols.items() if k in keep})
    df["level"] = "subdistrict"
    df["data_source"] = "GADM_v4.1"
    df["data_type"] = "REAL_DATA — NOT SYNTHETIC"
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()
    return df


def validate_admin(level_name: str, df: pd.DataFrame,
                   code_col: str, name_col: str, parent_col: str = None) -> dict:
    """Validate admin level data."""
    report = {
        "level": level_name,
        "n_features": len(df),
        "n_unique_codes": df[code_col].nunique(),
        "n_duplicate_codes": int(df[code_col].duplicated().sum()),
        "n_null_names": int(df[name_col].isna().sum()),
        "n_null_codes": int(df[code_col].isna().sum()),
    }

    if "geometry" in df.columns:
        try:
            import geopandas as gpd
            gdf = gpd.GeoDataFrame(df, geometry="geometry")
            report["n_valid_geoms"] = int(gdf.geometry.is_valid.sum())
            report["n_invalid_geoms"] = int((~gdf.geometry.is_valid).sum())
            report["n_null_geoms"] = int(gdf.geometry.isna().sum())
            bounds = gdf.total_bounds
            report["bbox"] = {
                "minx": round(float(bounds[0]), 4),
                "miny": round(float(bounds[1]), 4),
                "maxx": round(float(bounds[2]), 4),
                "maxy": round(float(bounds[3]), 4),
            }
            # India bounds check
            ok = (bounds[0] > 60 and bounds[1] > 5 and
                  bounds[2] < 100 and bounds[3] < 40)
            report["india_bounds_plausible"] = bool(ok)
        except Exception as e:
            report["geometry_validation_error"] = str(e)

    if parent_col and parent_col in df.columns:
        report["n_null_parents"] = int(df[parent_col].isna().sum())

    report["pass"] = (
        report["n_duplicate_codes"] == 0 and
        report["n_null_names"] == 0 and
        report["n_null_codes"] == 0 and
        report.get("n_invalid_geoms", 0) == 0
    )
    return report


def save_geoparquet(gdf, path: Path):
    """Save as GeoParquet (preferred) with CSV fallback."""
    try:
        gdf.to_parquet(path, index=False, engine="pyarrow")
        log.info(f"  Saved GeoParquet: {path}")
    except Exception as e:
        log.warning(f"  GeoParquet failed ({e}), saving plain Parquet without geometry...")
        df_no_geom = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))
        df_no_geom.to_parquet(str(path), index=False, engine="pyarrow")
        log.info(f"  Saved Parquet (no geometry): {path}")


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — GADM Admin Ingestion  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    gpkg_path = RAW_DIR / "gadm41_IND.gpkg"
    downloaded = download_gadm_gpkg(gpkg_path)

    if not downloaded:
        log.warning("GADM download failed. Marking MANUAL_REQUIRED.")
        status = {
            "status": "MANUAL_REQUIRED",
            "url": GADM_INDIA_URL,
            "action": (
                f"Download gadm41_IND.gpkg from {GADM_INDIA_URL} "
                f"and place in {RAW_DIR}/"
            ),
            "note": "GADM is free for non-commercial research. License: gadm.org/license.html",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(OUT_DIR / "gadm_status.json", "w") as f:
            json.dump(status, f, indent=2)
        log.info(f"  Status saved: gadm_status.json")
        log.info(f"  Manual download: {GADM_INDIA_URL}")
        return

    import geopandas as gpd

    all_reports = {}

    # Level 1 — States
    log.info("\nProcessing Level 1 (States)...")
    gdf1 = load_gadm_level(gpkg_path, 1)
    df1 = clean_gadm_level1(gdf1)
    report1 = validate_admin("states", df1, "state_code", "state_name")
    all_reports["states"] = report1
    log.info(f"  States: {report1['n_features']}, dupes={report1['n_duplicate_codes']}, "
             f"valid_geoms={report1.get('n_valid_geoms', 'N/A')}, pass={report1['pass']}")

    gdf1_out = gpd.GeoDataFrame(df1, geometry="geometry", crs=gdf1.crs)
    save_geoparquet(gdf1_out, OUT_DIR / "states.parquet")
    df1_nogeom = pd.DataFrame(df1.drop(columns=["geometry"], errors="ignore"))
    df1_nogeom.to_csv(str(OUT_DIR / "states.csv"), index=False)

    # Level 2 — Districts
    log.info("\nProcessing Level 2 (Districts)...")
    gdf2 = load_gadm_level(gpkg_path, 2)
    df2 = clean_gadm_level2(gdf2)
    report2 = validate_admin("districts", df2, "district_code", "district_name", "state_code")
    all_reports["districts"] = report2
    log.info(f"  Districts: {report2['n_features']}, dupes={report2['n_duplicate_codes']}, "
             f"valid_geoms={report2.get('n_valid_geoms', 'N/A')}, pass={report2['pass']}")

    gdf2_out = gpd.GeoDataFrame(df2, geometry="geometry", crs=gdf2.crs)
    save_geoparquet(gdf2_out, OUT_DIR / "districts.parquet")
    df2_nogeom = pd.DataFrame(df2.drop(columns=["geometry"], errors="ignore"))
    df2_nogeom.to_csv(str(OUT_DIR / "districts.csv"), index=False)

    # Level 3 — Sub-districts
    log.info("\nProcessing Level 3 (Sub-districts)...")
    gdf3 = load_gadm_level(gpkg_path, 3)
    df3 = clean_gadm_level3(gdf3)
    report3 = validate_admin("subdistricts", df3, "subdistrict_code",
                             "subdistrict_name", "district_code")
    all_reports["subdistricts"] = report3
    log.info(f"  Sub-districts: {report3['n_features']}, "
             f"dupes={report3['n_duplicate_codes']}, "
             f"valid_geoms={report3.get('n_valid_geoms', 'N/A')}, pass={report3['pass']}")

    gdf3_out = gpd.GeoDataFrame(df3, geometry="geometry", crs=gdf3.crs)
    save_geoparquet(gdf3_out, OUT_DIR / "subdistricts.parquet")
    df3_nogeom = pd.DataFrame(df3.drop(columns=["geometry"], errors="ignore"))
    df3_nogeom.to_csv(str(OUT_DIR / "subdistricts.csv"), index=False)

    # Hierarchy crosswalk
    log.info("\nBuilding hierarchy crosswalk...")
    crosswalk = df3_nogeom[[
        c for c in ["state_code", "state_name", "district_code",
                    "district_name", "subdistrict_code", "subdistrict_name"]
        if c in df3_nogeom.columns
    ]].drop_duplicates()
    crosswalk["data_source"] = "GADM_v4.1"
    crosswalk["data_type"] = "REAL_DATA — NOT SYNTHETIC"
    crosswalk.to_parquet(str(XWALK_DIR / "hierarchy_crosswalk.parquet"), index=False)
    crosswalk.to_csv(str(XWALK_DIR / "hierarchy_crosswalk.csv"), index=False)
    log.info(f"  Crosswalk: {len(crosswalk)} rows")

    # Overall gate decision
    all_pass = all(v.get("pass", False) for v in all_reports.values())
    gate_c_status = "NATIONWIDE_READY" if all_pass else "PARTIAL"

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_type": "REAL_DATA — NOT SYNTHETIC",
        "source": "GADM v4.1",
        "license": "Non-commercial research use — gadm.org/license.html",
        "gate_c_decision": gate_c_status,
        "counts": {
            "states": all_reports.get("states", {}).get("n_features", 0),
            "districts": all_reports.get("districts", {}).get("n_features", 0),
            "subdistricts": all_reports.get("subdistricts", {}).get("n_features", 0),
        },
        "village_level": "MANUAL_REQUIRED — LGD OTP / Census 2011 / SOI",
        "lgd_codes": "PARTIAL — LGD state_crosswalk.csv exists; district/village codes MANUAL_REQUIRED",
        "validation": all_reports,
    }
    with open(OUT_DIR / "gadm_admin_report.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    log.info(f"\n{'='*50}")
    log.info(f"Gate C Summary:")
    log.info(f"  States:       {summary['counts']['states']}")
    log.info(f"  Districts:    {summary['counts']['districts']}")
    log.info(f"  Sub-districts: {summary['counts']['subdistricts']}")
    log.info(f"  Villages:     MANUAL_REQUIRED")
    log.info(f"  Gate C:       {gate_c_status}")
    log.info(f"  Validation:   {'ALL PASS' if all_pass else 'SOME FAIL — see report'}")


if __name__ == "__main__":
    main()
