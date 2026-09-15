# -*- coding: utf-8 -*-
"""
real_pipeline/admin/ingest_lgd.py
==================================
Ingest Local Government Directory (LGD) administrative hierarchy from
authoritative Government of India sources.

LGD is the canonical authority for:
  State → District → Sub-district (Tehsil/Taluk) → Block → GP → Village

Official portals:
  Primary  : https://lgdirectory.gov.in/      (login required for bulk export)
  Data.gov : https://data.gov.in/             (some LGD snapshots, open)
  Open data: https://lgdirectory.gov.in/api/  (partially open endpoints)

Access notes:
  - Full LGD bulk export requires OTP/login: MANUAL_REQUIRED for bulk CSV/Excel.
  - data.gov.in hosts periodic LGD snapshots (open, no login needed).
  - Individual state data available without login from lgdirectory.gov.in:
      Reports → Download → Village List (by state) → CSV.

This script:
  1. Attempts open data.gov.in endpoints (no auth).
  2. Falls back to cached/manually placed files if in data_real/admin/raw/.
  3. Validates and exports canonical admin_locations.parquet + CSV.

!! NEVER INVENTS COORDINATES — null if no official geometry. !!
!! NEVER MIXES WITH SYNTHETIC DATA — writes only to data_real/. !!

Usage:
    python real_pipeline/admin/ingest_lgd.py [--source auto|manual|datagov] [--pages N]

Manual download instructions:
    1. Visit https://lgdirectory.gov.in/
    2. Navigate: Reports → Download → Village with Panchayat (select state) → CSV
    3. Place at: data_real/admin/raw/lgd_villages_<state_code>.csv
       OR nationwide: data_real/admin/raw/lgd_national_villages.csv
    4. Re-run with: python real_pipeline/admin/ingest_lgd.py --source manual

For nationwide bulk:
    LGD bulk export requires OTP-verified login → MANUAL_REQUIRED.
    Expected Excel columns:
      StateLGDCode, StateName, DistrictLGDCode, DistrictName,
      SubDistrictLGDCode, SubDistrictName, BlockLGDCode, BlockName,
      GPLGDCode, GPName, VillageLGDCode, VillageName, VillageStatus
    Place at: data_real/admin/raw/lgd_national_villages.xlsx
"""

import sys
import json
import logging
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

# ── Path setup ─────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).resolve().parents[2]
RAW_DIR       = PROJECT_ROOT / "data_real" / "admin" / "raw"
PROC_DIR      = PROJECT_ROOT / "data_real" / "admin" / "processed"
CROSSWALK_DIR = PROJECT_ROOT / "data_real" / "admin" / "crosswalk"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("lgd_ingest")

# ── Canonical column schema ────────────────────────────────────────────────────
CANONICAL_COLS = [
    "state_code",          # LGD state code (int)
    "state_name",
    "district_code",       # LGD district code (int)
    "district_name",
    "subdistrict_code",    # LGD sub-district / tehsil code (int)
    "subdistrict_name",
    "block_code",          # LGD block code (int, may differ from sub-dist)
    "block_name",
    "gp_code",             # LGD Gram Panchayat code (int)
    "gp_name",
    "village_code",        # LGD village code (int) — PRIMARY KEY
    "village_name",
    "latitude",            # Official centroid if available, else NULL (never invented)
    "longitude",
    "geometry_available",  # bool
    "geometry_source",     # e.g. "lgd_centroid", "survey_of_india", null
    "admin_source",        # e.g. "lgd_data.gov.in_2023"
    "source_date",         # ISO date string of dataset
    "boundary_area_km2",   # null if not computed
    "village_status",      # "Active", "Deleted", "Merged", etc.
]

# ── data.gov.in open endpoints ─────────────────────────────────────────────────
# NOTE: Resource IDs may change with dataset updates; verify at data.gov.in.
DATAGOV_ENDPOINTS = {
    "villages_lgd": {
        "url": "https://api.data.gov.in/resource/13c04e89-02aa-4e87-8f0e-5d11d84a1e9b",
        "params": {
            "api-key": "579b464db66ec23bdd000001",   # demo key; register for production
            "format": "csv",
            "offset": 0,
            "limit": 5000,
        },
        "description": "All Villages LGD snapshot (data.gov.in)",
        "note": "Paginated 5000 rows/page. Full dataset ~650k villages needs ~130 pages.",
    },
}

MANUAL_FILE_PATTERNS = [
    "lgd_national_villages.xlsx",
    "lgd_national_villages.csv",
    "lgd_villages_*.csv",
    "lgd_villages_*.xlsx",
    "lgd_district_*.csv",
    "lgd_subdistrict_*.csv",
]

# ── Column name normalization ──────────────────────────────────────────────────
LGD_COLUMN_MAP = {
    "statelgdcode": "state_code", "state_lgd_code": "state_code",
    "state lgd code": "state_code", "statecode": "state_code",
    "statename": "state_name", "state name": "state_name",
    "districtlgdcode": "district_code", "district_lgd_code": "district_code",
    "district lgd code": "district_code", "districtcode": "district_code",
    "districtname": "district_name", "district name": "district_name",
    "subdistrictlgdcode": "subdistrict_code", "subdistrict_lgd_code": "subdistrict_code",
    "sub district lgd code": "subdistrict_code", "tehsilcode": "subdistrict_code",
    "subdistrictname": "subdistrict_name", "sub district name": "subdistrict_name",
    "tehsilname": "subdistrict_name",
    "blocklgdcode": "block_code", "block_lgd_code": "block_code",
    "block lgd code": "block_code", "blockcode": "block_code",
    "blockname": "block_name", "block name": "block_name",
    "gplgdcode": "gp_code", "gp_lgd_code": "gp_code",
    "gp lgd code": "gp_code", "gpcode": "gp_code",
    "gpname": "gp_name", "gp name": "gp_name",
    "grampanchayatcode": "gp_code", "grampanchayatname": "gp_name",
    "gram panchayat name": "gp_name", "gram panchayat code": "gp_code",
    "villagelgdcode": "village_code", "village_lgd_code": "village_code",
    "village lgd code": "village_code", "villagecode": "village_code",
    "villagename": "village_name", "village name": "village_name",
    "status": "village_status", "villagestatus": "village_status",
    "village status": "village_status",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace("-", "_") for c in df.columns]
    df = df.rename(columns={k: v for k, v in LGD_COLUMN_MAP.items() if k in df.columns})
    return df


def add_missing_canonical_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in CANONICAL_COLS:
        if col not in df.columns:
            df[col] = None
    return df[CANONICAL_COLS]


def try_datagov_sample(pages: int = 2) -> Optional[pd.DataFrame]:
    """Fetch sample from data.gov.in open LGD endpoint (no auth for sample)."""
    ep = DATAGOV_ENDPOINTS["villages_lgd"]
    all_dfs = []
    log.info(f"Attempting data.gov.in LGD endpoint (sample, {pages} page(s))…")
    for page in range(pages):
        params = ep["params"].copy()
        params["offset"] = page * params["limit"]
        try:
            resp = requests.get(ep["url"], params=params, timeout=30)
            if resp.status_code == 200:
                from io import StringIO
                df_page = pd.read_csv(StringIO(resp.text))
                all_dfs.append(df_page)
                log.info(f"  Page {page+1}: {len(df_page)} rows")
                if len(df_page) < params["limit"]:
                    break
            elif resp.status_code in (401, 403):
                log.warning(f"  HTTP {resp.status_code} — API key required or endpoint restricted.")
                return None
            elif resp.status_code == 404:
                log.warning("  HTTP 404 — resource ID may have changed at data.gov.in.")
                return None
            else:
                log.warning(f"  HTTP {resp.status_code}")
                return None
        except requests.exceptions.ConnectionError:
            log.warning("  Connection error — offline or endpoint unreachable.")
            return None
        except requests.exceptions.Timeout:
            log.warning("  Request timeout.")
            return None
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return None


def scan_manual_files() -> list:
    found = []
    for pattern in MANUAL_FILE_PATTERNS:
        found.extend(list(RAW_DIR.glob(pattern)))
    return found


def load_manual_file(path: Path) -> pd.DataFrame:
    log.info(f"Loading manual file: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
            try:
                df = pd.read_csv(path, dtype=str, encoding=enc)
                log.info(f"  {len(df)} rows, encoding={enc}")
                return df
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode CSV {path}")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
        log.info(f"  {len(df)} rows from Excel")
        return df
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def validate_lgd_df(df: pd.DataFrame) -> dict:
    """Validate ingested LGD data. Does NOT silently discard rows."""
    report: dict = {"total_rows": len(df), "issues": [], "warnings": []}

    if "village_code" not in df.columns:
        report["issues"].append("CRITICAL: village_code column missing")
        return report

    null_vc = int(df["village_code"].isna().sum())
    if null_vc > 0:
        report["warnings"].append(f"{null_vc} rows with null village_code")

    dupes = int(df["village_code"].dropna().duplicated().sum())
    if dupes > 0:
        report["warnings"].append(f"{dupes} duplicate village_code values")

    for col in ["state_name", "district_name", "village_name"]:
        if col in df.columns:
            n = int(df[col].isna().sum())
            if n > 0:
                report["warnings"].append(f"{n} rows with null {col}")

    if "latitude" in df.columns and df["latitude"].notna().any():
        lats = pd.to_numeric(df["latitude"], errors="coerce")
        bad = int(((lats < 6) | (lats > 38)).sum())
        if bad:
            report["warnings"].append(f"{bad} latitudes outside India [6°,38°N]")

    if "longitude" in df.columns and df["longitude"].notna().any():
        lons = pd.to_numeric(df["longitude"], errors="coerce")
        bad = int(((lons < 67) | (lons > 98)).sum())
        if bad:
            report["warnings"].append(f"{bad} longitudes outside India [67°,98°E]")

    # Hierarchy counts
    for level, col in [
        ("states", "state_code"), ("districts", "district_code"),
        ("subdistricts", "subdistrict_code"), ("blocks", "block_code"),
        ("gps", "gp_code"), ("villages", "village_code"),
    ]:
        if col in df.columns:
            report[f"unique_{level}"] = int(df[col].dropna().nunique())

    return report


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def save_canonical(df: pd.DataFrame, source_label: str, source_date: str):
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    df["admin_source"] = source_label
    df["source_date"] = source_date

    for col in ["state_code", "district_code", "subdistrict_code",
                "block_code", "gp_code", "village_code"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["latitude", "longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["geometry_available"] = df["latitude"].notna() & df["longitude"].notna()

    out_parquet = PROC_DIR / "admin_locations.parquet"
    out_csv     = PROC_DIR / "admin_locations.csv"

    try:
        df.to_parquet(out_parquet, index=False, engine="pyarrow")
        log.info(f"Saved GeoParquet: {out_parquet} ({len(df):,} rows)")
    except Exception as e:
        log.warning(f"Parquet save failed ({e}); CSV only.")

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    log.info(f"Saved CSV: {out_csv} ({len(df):,} rows)")
    return out_parquet if out_parquet.exists() else out_csv


def write_report(report: dict, source: str):
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    report["ingest_timestamp"] = datetime.now(timezone.utc).isoformat()
    report["source"] = source
    path = PROC_DIR / "lgd_ingest_report.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Report: {path}")


def main():
    parser = argparse.ArgumentParser(description="Ingest LGD admin hierarchy")
    parser.add_argument("--source", choices=["auto", "manual", "datagov"], default="auto")
    parser.add_argument("--pages", type=int, default=2, help="data.gov.in pages (5k rows each)")
    parser.add_argument("--state", type=str, default=None, help="Filter by LGD state code")
    args = parser.parse_args()

    log.info("=" * 65)
    log.info("ResQ Shield — LGD Admin Ingest  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)

    df = None
    source_label = None
    source_date  = None

    # Priority 1: manual files
    if args.source in ("auto", "manual"):
        manual = scan_manual_files()
        if manual:
            target = sorted(manual, key=lambda p: p.stat().st_size, reverse=True)[0]
            raw = load_manual_file(target)
            raw = normalize_columns(raw)
            df = add_missing_canonical_cols(raw)
            source_label = f"lgd_manual_{target.stem}"
            source_date = datetime.fromtimestamp(
                target.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d")
            log.info(f"File SHA256: {sha256_file(target)}")
        elif args.source == "manual":
            log.error("No manual LGD files in data_real/admin/raw/  →  MANUAL_REQUIRED")
            log.error("  Download: https://lgdirectory.gov.in/ → Reports → Download → Village with Panchayat")
            log.error(f"  Place at: {RAW_DIR / 'lgd_national_villages.csv'}")
            sys.exit(1)

    # Priority 2: data.gov.in open API
    if df is None and args.source in ("auto", "datagov"):
        raw_api = try_datagov_sample(pages=args.pages)
        if raw_api is not None:
            raw_api = normalize_columns(raw_api)
            df = add_missing_canonical_cols(raw_api)
            source_label = "lgd_data.gov.in_api_sample"
            source_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log.info(f"Fetched {len(df):,} rows (sample — use --pages 130 for full nationwide)")
        else:
            log.warning("data.gov.in API unavailable.")

    if df is None:
        log.error("No LGD data source accessible.  →  MANUAL_REQUIRED")
        log.error("  See data_real/admin/processed/lgd_status.json for instructions.")
        status = {
            "status": "MANUAL_REQUIRED",
            "reason": "Neither data.gov.in open API nor manual files found",
            "options": [
                {
                    "label": "Option A — LGD portal (login required for bulk)",
                    "url": "https://lgdirectory.gov.in/",
                    "instructions": "Reports → Download → Village with Panchayat → CSV",
                    "place_at": str(RAW_DIR / "lgd_national_villages.csv"),
                },
                {
                    "label": "Option B — data.gov.in snapshot (no login)",
                    "url": "https://data.gov.in/resource/all-villages-lgd",
                    "instructions": "Download CSV → place at lgd_national_villages.csv",
                    "place_at": str(RAW_DIR / "lgd_national_villages.csv"),
                },
            ],
            "expected_columns": (
                "StateLGDCode, StateName, DistrictLGDCode, DistrictName, "
                "SubDistrictLGDCode, SubDistrictName, BlockLGDCode, BlockName, "
                "GPLGDCode, GPName, VillageLGDCode, VillageName, Status"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        PROC_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROC_DIR / "lgd_status.json", "w") as f:
            json.dump(status, f, indent=2)
        sys.exit(2)

    # Optional state filter
    if args.state and "state_code" in df.columns:
        df = df[df["state_code"].astype(str) == str(args.state)].copy()
        log.info(f"Filtered to state_code={args.state}: {len(df):,} rows")

    report = validate_lgd_df(df)
    log.info("Validation:")
    for k, v in report.items():
        if k not in ("issues", "warnings"):
            log.info(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
    for issue in report["issues"]:
        log.error(f"  ISSUE: {issue}")
    for warn in report["warnings"]:
        log.warning(f"  WARN: {warn}")

    if report["issues"]:
        log.error("Critical issues — aborting.")
        sys.exit(3)

    save_canonical(df, source_label, source_date)
    write_report(report, source_label)

    log.info("=" * 65)
    log.info("LGD ingest complete.")
    for k in ["unique_states", "unique_districts", "unique_subdistricts",
              "unique_blocks", "unique_gps", "unique_villages"]:
        if k in report:
            log.info(f"  {k}: {report[k]:,}")
    log.info("=" * 65)


if __name__ == "__main__":
    main()
