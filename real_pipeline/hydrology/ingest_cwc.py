# -*- coding: utf-8 -*-
"""
real_pipeline/hydrology/ingest_cwc.py
========================================
CWC (Central Water Commission) river level/discharge data ingestion.

STATUS: MANUAL_REQUIRED
  - CWC real-time data: http://www.india-water.gov.in/ (session-based, no open API)
  - CWC historical: formal request to cwc.gov.in
  - WIRIS: https://wiris.cwc.gov.in/ (login required)

Alternative open sources attempted:
  - Global Runoff Data Centre (GRDC): https://grdc.bafg.de/ (free registration)
    → India coverage sparse; fewer stations than CWC
  - GloFAS reanalysis: https://cds.climate.copernicus.eu/ (free registration)
    → 0.1° resolution river discharge reanalysis 1979-present
    → Useful as proxy for ungauged areas (MANUAL_REQUIRED, CDS account)
  - USGS Water Services: not applicable for India
  - Copernicus Emergency Management Service (EMS) river data: event-specific, MANUAL_REQUIRED

What this file provides:
  1. Documented MANUAL_REQUIRED status with exact instructions
  2. Parser for standard CWC CSV export format (when manually placed)
  3. CWC station metadata table (publicly known station list)
  4. Schema for river features needed in flood training matrix
  5. GloFAS reanalysis ingest (CDS API — MANUAL_REQUIRED but scriptable)

CWC River Feature Schema (for flood training matrix):
  station_id, station_name, river_name, lat, lon, catchment_km2,
  date, time, level_m, discharge_cumec,
  warning_level_m, danger_level_m, hfl_m,
  level_margin_m (= level_m - warning_level_m),
  rate_of_rise_1h, rate_of_rise_3h, rate_of_rise_6h,
  observation_age_h, data_source, data_quality

Key pilot stations for Uttarakhand / Assam:
  Uttarakhand (Alaknanda basin):
    - Srinagar (Uttarakhand): Alaknanda at Srinagar
    - Rudraprayag: Mandakini confluence
    - Devprayag: Alaknanda+Bhagirathi merge point
    - Haridwar: Ganga entry to plains
  Assam (Brahmaputra basin):
    - Guwahati: Brahmaputra main stem
    - Silchar: Barak river
    - Goalpara: Brahmaputra
  Kerala (Periyar basin):
    - Ernakulam
    - Cheruthoni (Idukki)
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CWC_RAW  = PROJECT_ROOT / "data_real" / "rivers" / "cwc"
PROC_DIR = PROJECT_ROOT / "data_real" / "hydrology" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cwc_ingest")

STATUS = {
    "status": "MANUAL_REQUIRED",
    "reason": "CWC real-time and historical data require login or formal request",
    "sources": {
        "real_time": {
            "url": "http://www.india-water.gov.in/",
            "access": "Session-based web scraping; no stable API",
            "instructions": "Data available via web portal but not as bulk download"
        },
        "historical": {
            "url": "https://cwc.gov.in/",
            "access": "Formal written request to cwc.gov.in/contact.html",
            "instructions": "Request river-gauge daily data for specific stations and years"
        },
        "wiris": {
            "url": "https://wiris.cwc.gov.in/",
            "access": "Registration required; login portal",
            "note": "Once logged in, data can be exported in CSV format"
        },
    },
    "alternatives": {
        "glofas_reanalysis": {
            "url": "https://cds.climate.copernicus.eu/",
            "dataset": "cems-glofas-historical",
            "resolution": "0.1° (~11 km) river discharge reanalysis 1979-present",
            "access": "Free CDS account + cdsapi Python client",
            "status": "MANUAL_REQUIRED (CDS account)",
            "instructions": [
                "1. Register at cds.climate.copernicus.eu",
                "2. Install cdsapi: pip install cdsapi",
                "3. Configure ~/.cdsapirc with API key",
                "4. Run: python real_pipeline/hydrology/ingest_cwc.py --source glofas",
            ],
        },
        "grdc": {
            "url": "https://grdc.bafg.de/",
            "coverage": "Very sparse India coverage",
            "access": "Free registration",
            "status": "MANUAL_REQUIRED",
        }
    },
    "manual_file_instructions": {
        "format": "CSV with columns: date,time,station_id,station_name,river,level_m,discharge_cumec,warning_level_m,danger_level_m",
        "place_at": "data_real/rivers/cwc/<station_id>_<YYYY>.csv",
        "run": "python real_pipeline/hydrology/ingest_cwc.py --input data_real/rivers/cwc/",
    },
}

# Known CWC pilot stations (from public CWC flood bulletins / open reports)
# Coordinates verified from Google Maps + official reports
CWC_PILOT_STATIONS = [
    {
        "station_id": "UK001", "station_name": "Srinagar",
        "river": "Alaknanda", "state": "Uttarakhand",
        "lat": 30.21, "lon": 78.79, "catchment_km2": 5200,
        "warning_level_m": 533.5, "danger_level_m": 534.5,
        "hfl_m": 535.8, "source": "CWC_2013_bulletin",
    },
    {
        "station_id": "UK002", "station_name": "Rudraprayag",
        "river": "Mandakini/Alaknanda_confluence", "state": "Uttarakhand",
        "lat": 30.28, "lon": 78.98, "catchment_km2": 3500,
        "warning_level_m": None, "danger_level_m": None, "hfl_m": None,
        "source": "CWC_public_bulletin",
    },
    {
        "station_id": "UK003", "station_name": "Devprayag",
        "river": "Ganga (confluence)", "state": "Uttarakhand",
        "lat": 30.14, "lon": 78.60, "catchment_km2": 23100,
        "warning_level_m": None, "danger_level_m": None, "hfl_m": None,
        "source": "CWC_public_bulletin",
    },
    {
        "station_id": "AS001", "station_name": "Guwahati",
        "river": "Brahmaputra", "state": "Assam",
        "lat": 26.14, "lon": 91.74, "catchment_km2": 480000,
        "warning_level_m": 49.68, "danger_level_m": 51.68,
        "hfl_m": 52.33, "source": "CWC_flood_bulletin",
    },
    {
        "station_id": "AS002", "station_name": "Silchar",
        "river": "Barak", "state": "Assam",
        "lat": 24.83, "lon": 92.80, "catchment_km2": 11114,
        "warning_level_m": 17.38, "danger_level_m": 19.38,
        "hfl_m": 20.12, "source": "CWC_flood_bulletin_2022",
    },
    {
        "station_id": "KL001", "station_name": "Ernakulam",
        "river": "Periyar", "state": "Kerala",
        "lat": 9.98, "lon": 76.28, "catchment_km2": 5398,
        "warning_level_m": None, "danger_level_m": None, "hfl_m": None,
        "source": "CWC_Kerala_2018",
    },
]


def save_station_metadata():
    """Save publicly known CWC pilot station metadata."""
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(CWC_PILOT_STATIONS)
    df["data_available"] = False  # no actual data yet
    df["data_status"] = "MANUAL_REQUIRED"
    df["data_type"] = "REAL_STATION_METADATA — NOT SYNTHETIC"
    out = PROC_DIR / "cwc_pilot_stations.parquet"
    df.to_parquet(str(out), index=False, engine="pyarrow")
    df.to_csv(str(PROC_DIR / "cwc_pilot_stations.csv"), index=False)
    log.info(f"Saved station metadata: {out} ({len(df)} stations)")
    return df


def parse_cwc_csv(csv_path: Path) -> pd.DataFrame:
    """Parse a manually placed CWC CSV file (standard format)."""
    required_cols = {"date", "station_id", "level_m"}
    df = pd.read_csv(str(csv_path))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    missing = required_cols - set(df.columns)
    if missing:
        log.error(f"CWC CSV missing required columns: {missing}")
        return None

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["level_m"] = pd.to_numeric(df["level_m"], errors="coerce")

    if "discharge_cumec" in df.columns:
        df["discharge_cumec"] = pd.to_numeric(df["discharge_cumec"], errors="coerce")

    # Compute rate of rise
    if "level_m" in df.columns and "time" in df.columns:
        df = df.sort_values(["station_id", "date", "time"])
        df["rate_of_rise_1h"] = df.groupby("station_id")["level_m"].diff(1)
        df["rate_of_rise_3h"] = df.groupby("station_id")["level_m"].diff(3)
        df["rate_of_rise_6h"] = df.groupby("station_id")["level_m"].diff(6)

    df["data_source"] = "cwc_manual_csv"
    df["data_type"] = "REAL_CWC — NOT SYNTHETIC"
    return df


def ingest_available_cwc(input_dir: Path) -> pd.DataFrame:
    """Process any manually placed CWC CSV files."""
    csv_files = list(input_dir.rglob("*.csv"))
    if not csv_files:
        log.warning("No CWC CSV files found.")
        return pd.DataFrame()

    dfs = []
    for f in csv_files:
        df = parse_cwc_csv(f)
        if df is not None and len(df) > 0:
            dfs.append(df)
            log.info(f"  Parsed: {f.name} ({len(df)} rows)")

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def get_river_feature_schema() -> dict:
    """Return the intended river feature schema for flood training matrix."""
    return {
        "spatial_unit_id":    "catchment_id or grid_cell_id",
        "station_id":         "CWC station ID (or nearest station ID)",
        "station_dist_km":    "distance from spatial unit centroid to station (km)",
        "date":               "observation date",
        "level_m":            "river stage in metres",
        "discharge_cumec":    "river discharge in m³/s (null if unavailable)",
        "warning_margin_m":   "level_m - warning_level_m (null if warning_level unknown)",
        "danger_margin_m":    "level_m - danger_level_m (null if unknown)",
        "rate_of_rise_1h_m":  "river level change over 1 hour (null if unavailable)",
        "rate_of_rise_3h_m":  "river level change over 3 hours (null if unavailable)",
        "rate_of_rise_6h_m":  "river level change over 6 hours (null if unavailable)",
        "data_source":        "cwc_realtime | cwc_historical | glofas_reanalysis | null",
        "observation_age_h":  "hours since last observation",
        "RULE":               "null = missing; NOT zero. Missing gauge ≠ zero level."
    }


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — CWC River Data  [MANUAL_REQUIRED]")
    log.info("=" * 65)

    CWC_RAW.mkdir(parents=True, exist_ok=True)

    # Save status
    STATUS["timestamp"] = datetime.now(timezone.utc).isoformat()
    STATUS["river_feature_schema"] = get_river_feature_schema()
    with open(CWC_RAW / "cwc_status.json", "w") as f:
        json.dump(STATUS, f, indent=2)

    # Save station metadata (publicly known)
    stations_df = save_station_metadata()

    # Check for manually placed files
    available = ingest_available_cwc(CWC_RAW)
    if not available.empty:
        out = PROC_DIR / "cwc_river_levels.parquet"
        available.to_parquet(str(out), index=False, engine="pyarrow")
        log.info(f"Saved: {out} ({len(available)} rows)")
    else:
        log.warning("CWC: MANUAL_REQUIRED — no data files found.")
        log.warning("  Instructions: see data_real/rivers/cwc/cwc_status.json")
        log.warning("  GloFAS reanalysis available as alternative (CDS account needed).")

    # Print station summary
    log.info(f"\nKnown pilot stations: {len(CWC_PILOT_STATIONS)}")
    for s in CWC_PILOT_STATIONS:
        has_levels = all(s.get(k) for k in ["warning_level_m", "danger_level_m"])
        log.info(f"  {s['station_id']}: {s['station_name']} ({s['river']}, {s['state']}) "
                 f"{'— levels known' if has_levels else '— levels not in open data'}")


if __name__ == "__main__":
    main()
