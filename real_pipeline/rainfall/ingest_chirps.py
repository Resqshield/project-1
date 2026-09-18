# -*- coding: utf-8 -*-
"""
real_pipeline/rainfall/ingest_chirps.py
=========================================
Ingest CHIRPS v2.0 daily rainfall for pilot event windows.

CHIRPS = Climate Hazards Group InfraRed Precipitation with Station data
Provider: Climate Hazards Center, UC Santa Barbara
URL: https://www.chc.ucsb.edu/data/chirps
Access: PUBLIC — no login, no API key required
Resolution: 0.05° (~5.5 km) global, daily, 1981–present
Format: GeoTIFF (.tif.gz), one file per day, global coverage
Size: ~5–8 MB per day compressed (global); ~0.3 MB after India clip
License: Free to use, cite Funk et al. 2015

Download URL pattern:
  https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/{YYYY}/
  File: chirps-v2.0.{YYYY}.{MM}.{DD}.tif.gz

Coverage: 50°S–50°N, 180°W–180°E
India bounding box (used for clipping): 6°–38°N, 67°–98°E

Usage:
    # Download and clip for Uttarakhand 2013 flood event:
    python real_pipeline/rainfall/ingest_chirps.py --event uk_2013_flood

    # Download specific date range:
    python real_pipeline/rainfall/ingest_chirps.py --start 2013-06-13 --end 2013-06-21 --region uttarakhand

    # Download pre-event antecedent window:
    python real_pipeline/rainfall/ingest_chirps.py --start 2013-05-30 --end 2013-06-21 --region uttarakhand

Reference: Funk, C., et al. (2015). The climate hazards infrared precipitation with stations—a new environmental record for monitoring extremes. Scientific data, 2(1), 1-21.
"""

import sys
import gzip
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import date, timedelta, datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR      = PROJECT_ROOT / "data_real" / "rainfall" / "chirps"
PROC_DIR     = PROJECT_ROOT / "data_real" / "rainfall" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
log = logging.getLogger("chirps_ingest")

# ── India bounding box ─────────────────────────────────────────────────────────
INDIA_BBOX = {"lat_min": 6.0, "lat_max": 38.0, "lon_min": 67.0, "lon_max": 98.0}

# ── Pilot region bounding boxes ────────────────────────────────────────────────
PILOT_BBOXES = {
    "uttarakhand":   {"lat_min": 28.5, "lat_max": 32.0, "lon_min": 77.5, "lon_max": 81.5},
    "himachal":      {"lat_min": 30.0, "lat_max": 33.5, "lon_min": 75.5, "lon_max": 79.0},
    "sikkim_ne":     {"lat_min": 26.0, "lat_max": 30.0, "lon_min": 88.0, "lon_max": 97.5},
    "kerala_wayanad":{"lat_min":  9.0, "lat_max": 12.5, "lon_min": 75.0, "lon_max": 78.0},
    "assam":         {"lat_min": 24.0, "lat_max": 28.5, "lon_min": 89.0, "lon_max": 96.5},
    "india":         INDIA_BBOX,
}

# ── Pre-defined pilot events (event + antecedent window) ──────────────────────
# Rationale: well-documented major disasters with open data
PILOT_EVENTS = {
    "uk_2013_flood": {
        "name": "Uttarakhand Flash Floods / Kedarnath Disaster",
        "region": "uttarakhand",
        "event_start": "2013-06-14",
        "event_end":   "2013-06-21",
        "antecedent_days": 14,   # 14-day pre-event window
        "description": "Catastrophic cloudbursts triggered flash floods and landslides in Kedarnath valley. Mandakini river overflow. ~5000+ deaths. Major rainfall on 2013-06-16 to 06-17.",
        "label_source": "DFO #3891 + NDMA reports",
    },
    "kerala_2018_flood": {
        "name": "Kerala Great Flood 2018",
        "region": "kerala_wayanad",
        "event_start": "2018-08-14",
        "event_end":   "2018-08-22",
        "antecedent_days": 14,
        "description": "Extreme monsoon rainfall. Idukki, Wayanad, Ernakulam most affected. ~483 deaths, 1.5M displaced. Red alert 14 districts.",
        "label_source": "DFO #4581 + KSEB + CWRDM reports",
    },
    "assam_2022_flood": {
        "name": "Assam Floods 2022",
        "region": "assam",
        "event_start": "2022-06-15",
        "event_end":   "2022-07-05",
        "antecedent_days": 10,
        "description": "Brahmaputra river flooding, 1.1M affected across 29 districts. Silchar severely inundated.",
        "label_source": "DFO + ASDMA reports",
    },
    "wayanad_2024_landslide": {
        "name": "Wayanad Landslide 2024 (Mundakkai-Chooralmala)",
        "region": "kerala_wayanad",
        "event_start": "2024-07-29",
        "event_end":   "2024-08-02",
        "antecedent_days": 7,
        "description": "Two massive landslides in Mundakkai and Chooralmala villages, Wayanad district. 200+ deaths. Extreme antecedent rainfall.",
        "label_source": "IMD + KSDMA reports",
    },
    "uk_2021_chamoli": {
        "name": "Chamoli Glacier Lake Outburst Flood 2021",
        "region": "uttarakhand",
        "event_start": "2021-02-07",
        "event_end":   "2021-02-08",
        "antecedent_days": 3,
        "description": "Rock/ice avalanche triggered GLOF on Rishiganga/Dhauliganga rivers. 204 deaths/missing. Hydro plant damage.",
        "label_source": "DFO + ISRO + NDMA 2021",
    },
}

CHIRPS_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05"


def chirps_url(d: date) -> str:
    return f"{CHIRPS_BASE}/{d.year}/chirps-v2.0.{d.strftime('%Y.%m.%d')}.tif.gz"


def chirps_local_path(d: date, region: str, raw: bool = False) -> Path:
    if raw:
        return RAW_DIR / f"chirps_{d.strftime('%Y%m%d')}_raw.tif.gz"
    return RAW_DIR / f"chirps_{region}_{d.strftime('%Y%m%d')}.tif"


def download_chirps_day(d: date, region: str = "india", bbox: dict = None,
                        skip_existing: bool = True) -> Optional[Path]:
    """
    Download + decompress + clip one CHIRPS daily file.
    Returns clipped GeoTIFF path or None on failure.
    """
    bbox = bbox or PILOT_BBOXES.get(region, INDIA_BBOX)
    out_path = chirps_local_path(d, region)
    if skip_existing and out_path.exists():
        log.info(f"  Exists: {out_path.name}")
        return out_path

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    url = chirps_url(d)
    gz_path = RAW_DIR / f"chirps_{d.strftime('%Y%m%d')}_dl.tif.gz"

    # Download
    try:
        resp = requests.get(url, stream=True, timeout=120)
        if resp.status_code == 200:
            total_bytes = 0
            with open(gz_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=131072):
                    f.write(chunk)
                    total_bytes += len(chunk)
            log.info(f"  Downloaded {d}: {total_bytes/1e6:.1f} MB → {gz_path.name}")
        else:
            log.warning(f"  HTTP {resp.status_code} for {d}: {url}")
            return None
    except Exception as e:
        log.error(f"  Download error {d}: {e}")
        return None

    # Decompress + clip with rasterio
    try:
        import rasterio
        from rasterio.windows import from_bounds
        from rasterio.transform import from_bounds as tfrom_bounds

        # Decompress to temp file
        tif_tmp = RAW_DIR / f"chirps_{d.strftime('%Y%m%d')}_global.tif"
        with gzip.open(gz_path, "rb") as gz_f, open(tif_tmp, "wb") as tif_f:
            shutil.copyfileobj(gz_f, tif_f)
        gz_path.unlink()  # remove gz

        # Clip to region bbox
        with rasterio.open(str(tif_tmp)) as src:
            window = from_bounds(
                left=bbox["lon_min"], bottom=bbox["lat_min"],
                right=bbox["lon_max"], top=bbox["lat_max"],
                transform=src.transform
            )
            data = src.read(1, window=window)
            nodata = src.nodata if src.nodata is not None else -9999.0

            transform_clip = src.window_transform(window)
            profile = src.profile.copy()
            profile.update(
                width=window.width, height=window.height,
                transform=transform_clip, compress="lzw"
            )
            # Replace CHIRPS nodata (-9999) with NaN-flagged float
            data = data.astype("float32")
            data[data == nodata] = np.nan
            data[data < 0] = np.nan
            profile.update(dtype="float32", nodata=np.nan)

            with rasterio.open(str(out_path), "w", **profile) as dst:
                dst.write(data, 1)

        try:
            tif_tmp.unlink()
        except Exception:
            pass  # Windows may lock file briefly; non-fatal, will be overwritten next run

        log.info(f"  Clipped to {region}: {out_path.name} ({data.shape})")
        return out_path

    except Exception as e:
        log.error(f"  Process error {d}: {e}")
        if gz_path.exists():
            gz_path.unlink()
        return None


def extract_chirps_stats(tif_path: Path, d: date, region: str) -> dict:
    """Extract daily rainfall statistics from clipped CHIRPS tile."""
    try:
        import rasterio
        with rasterio.open(str(tif_path)) as src:
            data = src.read(1).astype("float32")
            data[data < 0] = np.nan
            valid = data[~np.isnan(data)]
            if len(valid) == 0:
                return None

        return {
            "date": d.isoformat(),
            "region": region,
            "source": "CHIRPS-2.0",
            "resolution_deg": 0.05,
            "pixels_valid": int(len(valid)),
            "pixels_total": int(data.size),
            "coverage_pct": float(100 * len(valid) / data.size),
            "rain_mean_mm": float(np.nanmean(valid)),
            "rain_max_mm":  float(np.nanmax(valid)),
            "rain_p90_mm":  float(np.nanpercentile(valid, 90)),
            "rain_p99_mm":  float(np.nanpercentile(valid, 99)),
            "pct_gt_50mm":  float(100 * (valid > 50).mean()),
            "pct_gt_100mm": float(100 * (valid > 100).mean()),
            "pct_gt_200mm": float(100 * (valid > 200).mean()),
            "tif_path": str(tif_path),
        }
    except Exception as e:
        log.error(f"Stats error {tif_path}: {e}")
        return None


def build_event_rainfall_table(event_key: str) -> pd.DataFrame:
    """
    Build per-day rainfall stats table for a pilot event + antecedent window.
    Returns DataFrame with daily stats.
    """
    ev = PILOT_EVENTS[event_key]
    region = ev["region"]
    bbox = PILOT_BBOXES[region]

    event_start = date.fromisoformat(ev["event_start"])
    event_end   = date.fromisoformat(ev["event_end"])
    ant_days    = ev["antecedent_days"]
    dl_start    = event_start - timedelta(days=ant_days)

    total_days = (event_end - dl_start).days + 1
    log.info(f"Event: {ev['name']}")
    log.info(f"  Window: {dl_start} to {event_end} ({total_days} days, {ant_days} antecedent + event)")
    log.info(f"  Region: {region} {bbox}")
    log.info(f"  CHIRPS: public, no auth required")

    rows = []
    current = dl_start
    while current <= event_end:
        tif_path = download_chirps_day(current, region, bbox)
        if tif_path:
            stats = extract_chirps_stats(tif_path, current, region)
            if stats:
                stats["event_key"] = event_key
                stats["is_event_day"] = event_start <= current <= event_end
                stats["days_before_event_start"] = (event_start - current).days
                rows.append(stats)
        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    return df


def compute_antecedent_features(event_key: str, grid_path: Path = None) -> pd.DataFrame:
    """
    Compute antecedent rainfall features (3d, 7d, 14d rolling sums) from daily CHIRPS.
    Operates on per-pixel basis if grid available, else on area-mean stats.
    """
    ev = PILOT_EVENTS[event_key]
    region = ev["region"]
    event_start = date.fromisoformat(ev["event_start"])
    ant_days = ev["antecedent_days"]
    dl_start = event_start - timedelta(days=ant_days)

    # Collect all available days
    day_data = {}
    current = dl_start
    while current <= date.fromisoformat(ev["event_end"]):
        tif_path = chirps_local_path(current, region)
        if tif_path.exists():
            try:
                import rasterio
                with rasterio.open(str(tif_path)) as src:
                    data = src.read(1).astype("float32")
                    data[data < 0] = np.nan
                    transform = src.transform
                    height, width = data.shape
                    day_data[current] = {"mean": float(np.nanmean(data)),
                                         "max":  float(np.nanmax(data))}
            except Exception:
                pass
        current += timedelta(days=1)

    if not day_data:
        log.warning("No CHIRPS data available for antecedent computation.")
        return pd.DataFrame()

    df = pd.DataFrame([
        {"date": d, "mean_rain_mm": v["mean"], "max_rain_mm": v["max"]}
        for d, v in sorted(day_data.items())
    ])
    df = df.sort_values("date").reset_index(drop=True)

    # Rolling sums
    df["rain_3d_mm"]  = df["mean_rain_mm"].rolling(3,  min_periods=1).sum()
    df["rain_7d_mm"]  = df["mean_rain_mm"].rolling(7,  min_periods=1).sum()
    df["rain_14d_mm"] = df["mean_rain_mm"].rolling(14, min_periods=1).sum()
    df["rain_24h_mm"] = df["mean_rain_mm"]  # daily = 24h

    df["region"]    = region
    df["event_key"] = event_key
    df["source"]    = "CHIRPS-2.0"
    return df


def main():
    parser = argparse.ArgumentParser(description="CHIRPS daily rainfall ingestion")
    parser.add_argument("--event", choices=list(PILOT_EVENTS.keys()), default=None)
    parser.add_argument("--start", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--end",   type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--region", choices=list(PILOT_BBOXES.keys()), default="uttarakhand")
    parser.add_argument("--all-events", action="store_true", help="Download all pilot events")
    args = parser.parse_args()

    log.info("=" * 65)
    log.info("ResQ Shield — CHIRPS Rainfall Ingest  [REAL DATA — PUBLIC]")
    log.info("Source: CHIRPS-2.0 (UC Santa Barbara, no auth required)")
    log.info("=" * 65)

    PROC_DIR.mkdir(parents=True, exist_ok=True)

    events_to_run = list(PILOT_EVENTS.keys()) if args.all_events else ([args.event] if args.event else [])

    if events_to_run:
        all_tables = []
        for ev_key in events_to_run:
            df = build_event_rainfall_table(ev_key)
            if not df.empty:
                all_tables.append(df)
                log.info(f"  {ev_key}: {len(df)} days, mean rain {df['rain_mean_mm'].mean():.1f} mm/day")

        if all_tables:
            combined = pd.concat(all_tables, ignore_index=True)
            out = PROC_DIR / "chirps_event_daily_stats.parquet"
            combined.to_parquet(str(out), index=False, engine="pyarrow")
            log.info(f"Saved: {out} ({len(combined)} rows)")

    elif args.start and args.end:
        start = date.fromisoformat(args.start)
        end   = date.fromisoformat(args.end)
        bbox  = PILOT_BBOXES[args.region]
        rows = []
        current = start
        while current <= end:
            p = download_chirps_day(current, args.region, bbox)
            if p:
                s = extract_chirps_stats(p, current, args.region)
                if s:
                    rows.append(s)
            current += timedelta(days=1)
        if rows:
            df = pd.DataFrame(rows)
            log.info(f"Downloaded {len(df)} days for {args.region}")

    else:
        log.info("No event or date range specified. Use --event or --start/--end.")
        log.info(f"Available events: {list(PILOT_EVENTS.keys())}")


if __name__ == "__main__":
    main()
