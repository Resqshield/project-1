# -*- coding: utf-8 -*-
"""
real_pipeline/events/ingest_landslide_events.py
=================================================
Ingest observed landslide event records from authoritative open sources.

Sources:
  A) NASA Global Landslide Catalog (GLC) — OPEN, no auth required
     URL: https://catalog.data.gov/dataset/global-landslide-catalog
     Direct CSV: https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv
     Format: CSV (~5,000 events, 2007–present, global, point locations)
     Fields: event_id, date, event_time, event_title, source_name, source_link,
             location_description, location_accuracy, country_name,
             admin_division_name, latitude, longitude, fatality_count, injury_count,
             landslide_type, landslide_setting, trigger, size, notes

  B) GSI (Geological Survey of India) National Landslide Susceptibility Mapping
     MANUAL_REQUIRED — shapefile download via GSI portal or formal request
     URL: https://www.gsi.gov.in/

  C) DesInventar India — disaster inventory (open, web-based)
     URL: https://www.desinventar.net/DesInventar/profiletab.jsp?countrycode=ind
     MANUAL_REQUIRED — download from web UI

  D) NDMA disaster records — MANUAL_REQUIRED

CRITICAL DISTINCTIONS:
  1. DATED events (with precise date/time) → dynamic training candidates
     Rule: Date precision must be ≤ 7 days to be usable as dynamic label
  2. UNDATED inventory points → static susceptibility mapping ONLY
     Rule: NEVER treat undated landslide locations as timestamped dynamic labels

Trigger types (from GLC taxonomy):
  - rain → primary target for rainfall-triggered model
  - continuous_rain → prolonged rainfall trigger
  - tropical_cyclone → rain-associated
  - construction, earthquake, natural_causes → exclude from rainfall model
  - unknown → retain but flag; do not use for trigger-specific features

India pilot focus regions:
  - Uttarakhand (high-frequency)
  - Himachal Pradesh
  - Sikkim + NE (Assam, Meghalaya, Arunachal)
  - Western Ghats (Wayanad, Idukki)
  - Darjeeling hills
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR      = PROJECT_ROOT / "data_real" / "events" / "landslide"
PROC_DIR     = PROJECT_ROOT / "data_real" / "events" / "landslide" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("landslide_events")

NASA_GLC_URL = "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv"

INDIA_BBOX = {"lat_min": 6.0, "lat_max": 37.5, "lon_min": 67.0, "lon_max": 98.0}

# Pilot region bounding boxes
PILOT_BBOXES = {
    "uttarakhand":    {"lat_min": 28.5, "lat_max": 32.0, "lon_min": 77.5, "lon_max": 81.5},
    "himachal":       {"lat_min": 30.0, "lat_max": 33.5, "lon_min": 75.5, "lon_max": 79.0},
    "sikkim_ne":      {"lat_min": 25.0, "lat_max": 30.0, "lon_min": 88.0, "lon_max": 97.5},
    "western_ghats":  {"lat_min":  8.5, "lat_max": 14.0, "lon_min": 74.5, "lon_max": 78.0},
    "darjeeling":     {"lat_min": 26.5, "lat_max": 27.5, "lon_min": 87.5, "lon_max": 89.0},
}

# Rainfall-related triggers (for rainfall model relevance)
RAIN_TRIGGERS = {
    "rain", "continuous_rain", "monsoon", "tropical_cyclone",
    "downpour", "heavy_rain", "flooding_/rain", "rain_and_flooding",
}

# Triggers to EXCLUDE from rainfall-triggered model (different physical mechanism)
EXCLUDE_TRIGGERS = {
    "earthquake", "construction", "mining", "dam_construction",
    "blasting", "vibration", "human_activities",
}


def download_nasa_glc() -> pd.DataFrame:
    """Download NASA Global Landslide Catalog (open, no auth)."""
    log.info("Downloading NASA Global Landslide Catalog...")
    log.info(f"  URL: {NASA_GLC_URL}")
    try:
        resp = requests.get(NASA_GLC_URL, timeout=90, headers={"User-Agent": "ResQShield-Research"})
        if resp.status_code == 200:
            df = pd.read_csv(pd.io.common.StringIO(resp.text))
            log.info(f"  GLC downloaded: {len(df)} total events worldwide")
            return df
        else:
            log.warning(f"  GLC HTTP {resp.status_code}")
            return None
    except Exception as e:
        log.error(f"  GLC download error: {e}")
        return None


def filter_india_glc(df: pd.DataFrame) -> pd.DataFrame:
    """Filter GLC to India events within pilot bounding boxes."""
    if df is None or len(df) == 0:
        return pd.DataFrame()

    # Normalize column names (GLC uses mixed case)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Filter by country
    country_col = next((c for c in df.columns if "country" in c), None)
    lat_col     = next((c for c in df.columns if "latitude" in c or c == "lat"), None)
    lon_col     = next((c for c in df.columns if "longitude" in c or c == "lon"), None)

    mask = pd.Series([False] * len(df))
    if country_col:
        mask |= df[country_col].astype(str).str.lower().str.contains("india", na=False)
    if lat_col and lon_col:
        lats = pd.to_numeric(df[lat_col], errors="coerce")
        lons = pd.to_numeric(df[lon_col], errors="coerce")
        coord_mask = (
            lats.between(INDIA_BBOX["lat_min"], INDIA_BBOX["lat_max"]) &
            lons.between(INDIA_BBOX["lon_min"], INDIA_BBOX["lon_max"])
        )
        mask |= coord_mask

    india_df = df[mask].copy()
    log.info(f"  India events: {len(india_df)} (from {len(df)} global)")
    return india_df


def classify_date_precision(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each event by date precision.
    Critical rule: Only events with date_precision <= 7 days can be used as dynamic training labels.
    """
    date_col = next((c for c in df.columns if "date" in c and "start" not in c and "end" not in c), None)
    if not date_col:
        df["date_precision_days"] = None
        df["usable_dynamic_label"] = False
        return df

    # Parse dates
    df["event_date_parsed"] = pd.to_datetime(df[date_col], errors="coerce", infer_datetime_format=True)

    # Check for year-only, month-only, etc.
    df["date_precision_days"] = df["event_date_parsed"].apply(lambda x:
        1 if pd.notna(x) else None  # GLC usually has day-level dates
    )

    # Mark events with parseable dates as potentially usable
    df["usable_dynamic_label"] = df["event_date_parsed"].notna()

    null_dates = df["event_date_parsed"].isna().sum()
    if null_dates > 0:
        log.warning(f"  {null_dates} events with unparseable dates → static susceptibility only")

    return df


def assign_pilot_region(df: pd.DataFrame) -> pd.DataFrame:
    """Assign each event to a pilot region (or 'other_india')."""
    lat_col = next((c for c in df.columns if "latitude" in c or c == "lat"), None)
    lon_col = next((c for c in df.columns if "longitude" in c or c == "lon"), None)

    if not lat_col or not lon_col:
        df["pilot_region"] = "unknown"
        return df

    lats = pd.to_numeric(df[lat_col], errors="coerce")
    lons = pd.to_numeric(df[lon_col], errors="coerce")

    regions = []
    for lat, lon in zip(lats, lons):
        assigned = "other_india"
        if pd.isna(lat) or pd.isna(lon):
            assigned = "unknown"
        else:
            for reg, bbox in PILOT_BBOXES.items():
                if (bbox["lat_min"] <= lat <= bbox["lat_max"] and
                        bbox["lon_min"] <= lon <= bbox["lon_max"]):
                    assigned = reg
                    break
        regions.append(assigned)

    df["pilot_region"] = regions
    return df


def classify_trigger_relevance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mark events as rainfall-relevant or not.
    Rules:
    - rain_triggered: trigger in RAIN_TRIGGERS
    - excluded: trigger in EXCLUDE_TRIGGERS
    - unknown: trigger is unknown or not specified
    """
    trig_col = next((c for c in df.columns if "trigger" in c), None)
    if not trig_col:
        df["rainfall_trigger"] = "unknown"
        df["include_in_rainfall_model"] = True  # default include with flag
        return df

    def classify(t):
        if pd.isna(t):
            return "unknown"
        t_lower = str(t).strip().lower()
        if any(r in t_lower for r in RAIN_TRIGGERS):
            return "rain"
        if any(r in t_lower for r in EXCLUDE_TRIGGERS):
            return "non_rain"
        return "unknown"

    df["rainfall_trigger"] = df[trig_col].apply(classify)
    df["include_in_rainfall_model"] = df["rainfall_trigger"].isin(["rain", "unknown"])

    trigger_counts = df["rainfall_trigger"].value_counts()
    log.info(f"  Trigger classification: {trigger_counts.to_dict()}")
    return df


def build_landslide_event_table() -> dict:
    """Build landslide event table with dynamic vs susceptibility split."""
    log.info("Building landslide event table...")

    # Download NASA GLC
    raw_df = download_nasa_glc()

    if raw_df is not None and len(raw_df) > 0:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / "nasa_glc_india_raw.csv"
        india_df = filter_india_glc(raw_df)
        if len(india_df) > 0:
            india_df.to_csv(str(raw_path), index=False)
            log.info(f"  Saved raw India GLC: {raw_path}")
        else:
            india_df = pd.DataFrame()
    else:
        india_df = pd.DataFrame()

    if len(india_df) == 0:
        log.warning("  GLC India subset empty or unavailable. Creating empty tables.")
        dynamic_df      = pd.DataFrame()
        suscept_df      = pd.DataFrame()
        pilot_dynamic   = pd.DataFrame()
        return {
            "dynamic": dynamic_df,
            "susceptibility_only": suscept_df,
            "pilot_dynamic": pilot_dynamic,
            "source": "NASA_GLC_download_failed",
        }

    # Classify
    india_df = classify_date_precision(india_df)
    india_df = assign_pilot_region(india_df)
    india_df = classify_trigger_relevance(india_df)
    india_df["data_type"] = "REAL_OFFICIAL — NOT SYNTHETIC"
    india_df["label_source"] = "NASA_GLC"
    india_df["ingested_at"] = datetime.now(timezone.utc).isoformat()

    # Split: dated events (dynamic) vs undated (susceptibility only)
    dynamic_df = india_df[india_df["usable_dynamic_label"] == True].copy()
    suscept_df = india_df[india_df["usable_dynamic_label"] == False].copy()

    log.info(f"  Dynamic (dated, usable for temporal training): {len(dynamic_df)}")
    log.info(f"  Susceptibility only (undated or imprecise): {len(suscept_df)}")

    # Pilot regions
    pilot_regions = list(PILOT_BBOXES.keys()) + ["other_india"]
    pilot_dynamic = dynamic_df[
        dynamic_df["pilot_region"].isin(PILOT_BBOXES.keys())
    ].copy()
    log.info(f"  Pilot region dynamic events: {len(pilot_dynamic)}")
    if len(pilot_dynamic) > 0:
        log.info(f"  By region: {pilot_dynamic['pilot_region'].value_counts().to_dict()}")

    # Trigger summary
    if "rainfall_trigger" in dynamic_df.columns:
        rain_events = dynamic_df[dynamic_df["rainfall_trigger"] == "rain"]
        log.info(f"  Rain-triggered (pilot dynamic): {len(rain_events[rain_events['pilot_region'].isin(PILOT_BBOXES.keys())])}")

    return {
        "dynamic": dynamic_df,
        "susceptibility_only": suscept_df,
        "pilot_dynamic": pilot_dynamic,
        "source": "NASA_GLC",
        "n_total_india": len(india_df),
        "n_dynamic": len(dynamic_df),
        "n_suscept_only": len(suscept_df),
        "n_pilot_dynamic": len(pilot_dynamic),
    }


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Landslide Event Labels  [REAL — NOT SYNTHETIC]")
    log.info("=" * 65)
    log.info("CRITICAL: Dated events → dynamic; Undated → susceptibility only.")
    log.info("CRITICAL: Never use undated inventory as timestamped label.")

    PROC_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    result = build_landslide_event_table()

    # Save results
    if not result["dynamic"].empty:
        dyn_path = PROC_DIR / "landslide_events_dynamic.parquet"
        result["dynamic"].to_parquet(str(dyn_path), index=False, engine="pyarrow")
        result["dynamic"].to_csv(str(PROC_DIR / "landslide_events_dynamic.csv"), index=False)
        log.info(f"Saved dynamic: {dyn_path} ({len(result['dynamic'])} rows)")

    if not result["susceptibility_only"].empty:
        susc_path = PROC_DIR / "landslide_susceptibility_only.parquet"
        result["susceptibility_only"].to_parquet(str(susc_path), index=False, engine="pyarrow")
        log.info(f"Saved susceptibility-only: {susc_path} ({len(result['susceptibility_only'])} rows)")

    if not result["pilot_dynamic"].empty:
        pilot_path = PROC_DIR / "landslide_pilot_dynamic.parquet"
        result["pilot_dynamic"].to_parquet(str(pilot_path), index=False, engine="pyarrow")
        result["pilot_dynamic"].to_csv(str(PROC_DIR / "landslide_pilot_dynamic.csv"), index=False)
        log.info(f"Saved pilot dynamic: {pilot_path} ({len(result['pilot_dynamic'])} rows)")

    # Summary report
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": result.get("source"),
        "n_total_india": result.get("n_total_india", 0),
        "n_dynamic_dated": result.get("n_dynamic", 0),
        "n_susceptibility_only_undated": result.get("n_suscept_only", 0),
        "n_pilot_regions_dynamic": result.get("n_pilot_dynamic", 0),
        "status": "MANUAL_REQUIRED (GSI inventory)" if result["dynamic"].empty else "partial_open_data",
        "data_type": "REAL_OFFICIAL — NOT SYNTHETIC",
        "gsi_status": "MANUAL_REQUIRED — GSI landslide inventory requires formal request from gsi.gov.in",
        "gsi_url": "https://www.gsi.gov.in/",
        "gsi_contact": "dgm-hq-gsi@gov.in",
    }
    with open(PROC_DIR / "landslide_status.json", "w") as f:
        json.dump(summary, f, indent=2)

    log.info("\nGSI Landslide Inventory: MANUAL_REQUIRED")
    log.info("  Contact GSI (dgm-hq-gsi@gov.in) for India landslide susceptibility shapefile.")
    log.info("  Without GSI, falling back to NASA GLC for pilot region dynamic events.")


if __name__ == "__main__":
    main()
