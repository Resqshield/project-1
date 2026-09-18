# -*- coding: utf-8 -*-
"""
real_pipeline/features/build_flood_matrix.py
==============================================
Build the flood training feature matrix from real data.

Spatial unit: CHIRPS 0.05° grid cell (~5.5 km × 5.5 km)
  - Rationale: CHIRPS is the primary open rainfall source; grid cell is its native resolution
  - Future upgrade: catchment/HydroBASINS polygon when boundaries are available
  - Village linkage: grid cell → village(s) after LGD data ingested

Time window: (cell, event_window) pair
  - Each row = one spatial cell × one event/non-event window
  - POSITIVE samples: cells in pilot region during verified flood event
  - NEGATIVE samples: same cells during verified non-flood reference windows

Label source: flood_events.parquet (from ingest_flood_events.py)
  - NEVER labeled from our own feature thresholds
  - NEVER using 'missing data period = non-flood'
  - Verified non-flood from non_flood_reference_windows.parquet

Rainfall features (from CHIRPS):
  rain_1d_mm, rain_3d_mm, rain_7d_mm, rain_14d_mm (antecedent sums)
  rain_event_max_mm (max daily during event window)
  rain_event_mean_mm (mean daily during event window)
  rain_anomaly_mm (deviation from climatological mean — if available)
  chirps_coverage_pct (fraction of valid pixels)

River features (from CWC):
  All null until CWC data manually placed; flagged in coverage metadata.

Terrain/static (from static_terrain_*.parquet):
  elev_mean_m, slope_mean_deg, pct_slope_gt_30, terrain_available,
  nearest_cwc_dist_km, twi_proxy_simplified

Quality/provenance fields:
  rain_source, river_source, soil_source, label_source, data_coverage,
  terrain_available, chirps_coverage_pct

Output: data_real/features/flood_training.parquet
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEAT_DIR   = PROJECT_ROOT / "data_real" / "features"
EVENTS_DIR = PROJECT_ROOT / "data_real" / "events" / "flood" / "processed"
CHIRPS_DIR = PROJECT_ROOT / "data_real" / "rainfall" / "chirps"
CHIRPS_PROC= PROJECT_ROOT / "data_real" / "rainfall" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("flood_matrix")

CHIRPS_RES = 0.05

PILOT_BBOXES = {
    "uttarakhand":    {"lat_min": 28.5, "lat_max": 32.0, "lon_min": 77.5, "lon_max": 81.5},
    "kerala_wayanad": {"lat_min":  9.0, "lat_max": 12.5, "lon_min": 75.0, "lon_max": 78.0},
    "assam":          {"lat_min": 24.0, "lat_max": 28.5, "lon_min": 89.0, "lon_max": 96.5},
}

EVENT_TO_REGION = {
    "IND_FLOOD_2013_UK_001":    "uttarakhand",
    "IND_FLOOD_2018_KL_001":    "kerala_wayanad",
    "IND_FLOOD_2022_AS_001":    "assam",
    "IND_FLOOD_2021_UK_GLOF_001": "uttarakhand",
    "IND_FLOOD_2023_SK_GLOF_001": "sikkim_ne",  # not in pilot terrain yet
}

CHIRPS_EVENT_KEY_MAP = {
    "IND_FLOOD_2013_UK_001": "uk_2013_flood",
    "IND_FLOOD_2018_KL_001": "kerala_2018_flood",
    "IND_FLOOD_2022_AS_001": "assam_2022_flood",
    "IND_FLOOD_2021_UK_GLOF_001": "uk_2021_chamoli",
}


def load_chirps_daily_stats() -> pd.DataFrame:
    """Load pre-computed CHIRPS daily stats."""
    parquet_path = CHIRPS_PROC / "chirps_event_daily_stats.parquet"
    if parquet_path.exists():
        df = pd.read_parquet(str(parquet_path))
        log.info(f"Loaded CHIRPS stats: {len(df)} days across {df['event_key'].nunique()} events")
        return df
    log.warning("CHIRPS processed stats not found. Run ingest_chirps.py first.")
    return pd.DataFrame()


def load_chirps_grid_for_day(d: date, region: str) -> np.ndarray:
    """Load a specific CHIRPS tile (clipped to region) for per-cell features."""
    tif_path = CHIRPS_DIR / f"chirps_{region}_{d.strftime('%Y%m%d')}.tif"
    if not tif_path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(str(tif_path)) as src:
            data = src.read(1).astype("float32")
            data[data < 0] = np.nan
            return data, src.transform, src.bounds
    except Exception as e:
        log.warning(f"Could not load {tif_path}: {e}")
        return None


def compute_window_rainfall(region: str, event_key: str,
                             window_start: date, window_end: date) -> pd.DataFrame:
    """
    Compute per-grid-cell rainfall features for a time window.
    Returns DataFrame with cell_id, rainfall features, coverage.
    """
    import rasterio

    bbox = PILOT_BBOXES.get(region)
    if not bbox:
        return pd.DataFrame()

    lats = np.arange(bbox["lat_min"] + CHIRPS_RES/2, bbox["lat_max"], CHIRPS_RES)
    lons = np.arange(bbox["lon_min"] + CHIRPS_RES/2, bbox["lon_max"], CHIRPS_RES)
    n_cells = len(lats) * len(lons)

    # Accumulate per-pixel daily values for window
    day_arrays = []
    current = window_start
    while current <= window_end:
        result = load_chirps_grid_for_day(current, region)
        if result is not None:
            data, transform, bounds = result
            day_arrays.append((current, data))
        current += timedelta(days=1)

    if not day_arrays:
        log.warning(f"  No CHIRPS tiles found for {region} {window_start}–{window_end}")
        return pd.DataFrame()

    n_days = len(day_arrays)
    log.info(f"  {region} {window_start}–{window_end}: {n_days} CHIRPS tiles loaded")

    # Stack arrays
    stack = np.stack([arr for _, arr in day_arrays], axis=0)  # (days, H, W)
    days_list = [d for d, _ in day_arrays]

    # Compute features per pixel
    with rasterio.open(str(CHIRPS_DIR / f"chirps_{region}_{days_list[0].strftime('%Y%m%d')}.tif")) as src:
        transform = src.transform
        height, width = src.height, src.width

    rows = []
    for row_i in range(height):
        for col_j in range(width):
            pixel = stack[:, row_i, col_j]
            valid = pixel[~np.isnan(pixel)]
            if len(valid) == 0:
                coverage = 0.0
            else:
                coverage = float(len(valid) / len(pixel))

            lat = transform.f + (row_i + 0.5) * transform.e
            lon = transform.c + (col_j + 0.5) * transform.a

            cell_id = f"chirps_{lat:.3f}_{lon:.3f}"

            row = {
                "cell_id": cell_id,
                "lat_center": round(lat, 4),
                "lon_center": round(lon, 4),
                "pilot_region": region,
                "event_id": event_key,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "n_days_window": len(day_arrays),
                "n_days_valid_chirps": int(len(valid)) if len(valid) > 0 else 0,
                "chirps_coverage_pct": round(coverage * 100, 1),

                # Rainfall features (null if no valid data)
                "rain_event_sum_mm":  float(np.nansum(pixel)) if len(valid) > 0 else None,
                "rain_event_mean_mm": float(np.nanmean(valid)) if len(valid) > 0 else None,
                "rain_event_max_mm":  float(np.nanmax(valid)) if len(valid) > 0 else None,
                "rain_event_p90_mm":  float(np.nanpercentile(valid, 90)) if len(valid) > 0 else None,
            }
            rows.append(row)

    return pd.DataFrame(rows)


def compute_antecedent_rainfall(region: str, event_start: date, ant_days: int = 7) -> pd.DataFrame:
    """
    Compute antecedent rainfall (3d, 7d) from CHIRPS for period before event.
    Returns per-cell antecedent sums.
    """
    ant_end   = event_start - timedelta(days=1)
    ant_3d_start  = event_start - timedelta(days=3)
    ant_7d_start  = event_start - timedelta(days=7)
    ant_14d_start = event_start - timedelta(days=14)

    # Load antecedent pixel arrays
    def load_window(start, end):
        arrays = []
        current = start
        while current <= end:
            result = load_chirps_grid_for_day(current, region)
            if result is not None:
                arrays.append(result[0])
            current += timedelta(days=1)
        return arrays

    arrays_3d  = load_window(ant_3d_start, ant_end)
    arrays_7d  = load_window(ant_7d_start, ant_end)
    arrays_14d = load_window(ant_14d_start, ant_end)

    if not arrays_3d and not arrays_7d:
        return pd.DataFrame()

    # Use widest available window as shape reference
    ref_arrays = arrays_14d or arrays_7d or arrays_3d

    def mean_stack(arrays):
        if not arrays:
            return None
        stack = np.stack(arrays, axis=0)
        return np.nanmean(stack, axis=0)

    def sum_stack(arrays):
        if not arrays:
            return None
        stack = np.stack(arrays, axis=0)
        return np.nansum(stack, axis=0)

    ant_3d_grid  = sum_stack(arrays_3d)
    ant_7d_grid  = sum_stack(arrays_7d)
    ant_14d_grid = sum_stack(arrays_14d)

    ref_grid = ref_arrays[0]
    height, width = ref_grid.shape

    import rasterio
    with rasterio.open(str(list(CHIRPS_DIR.glob(f"chirps_{region}_*.tif"))[0])) as src:
        transform = src.transform

    rows = []
    for row_i in range(height):
        for col_j in range(width):
            lat = transform.f + (row_i + 0.5) * transform.e
            lon = transform.c + (col_j + 0.5) * transform.a
            cell_id = f"chirps_{lat:.3f}_{lon:.3f}"

            rows.append({
                "cell_id": cell_id,
                "pilot_region": region,
                "ant_3d_mm":  float(ant_3d_grid[row_i, col_j])  if ant_3d_grid  is not None else None,
                "ant_7d_mm":  float(ant_7d_grid[row_i, col_j])  if ant_7d_grid  is not None else None,
                "ant_14d_mm": float(ant_14d_grid[row_i, col_j]) if ant_14d_grid is not None else None,
                "n_days_ant_3d":  len(arrays_3d),
                "n_days_ant_7d":  len(arrays_7d),
                "n_days_ant_14d": len(arrays_14d),
            })

    return pd.DataFrame(rows)


def load_static_terrain(region: str) -> pd.DataFrame:
    """Load pre-computed static terrain features for a region."""
    path = FEAT_DIR / f"static_terrain_{region}.parquet"
    if path.exists():
        df = pd.read_parquet(str(path))
        log.info(f"  Static terrain: {len(df)} cells for {region}")
        return df
    log.warning(f"  Static terrain not found for {region}. Run build_static_features.py first.")
    return pd.DataFrame()


def build_positive_samples(events_df: pd.DataFrame) -> pd.DataFrame:
    """Build positive (flood) training samples."""
    all_samples = []

    for _, ev in events_df.iterrows():
        region = EVENT_TO_REGION.get(ev["event_id"])
        if not region or region not in PILOT_BBOXES:
            log.info(f"  Skipping {ev['event_id']}: region not in pilot bboxes")
            continue

        ev_start = pd.to_datetime(ev["date_start"]).date()
        ev_end   = pd.to_datetime(ev["date_end"]).date()

        log.info(f"\nBuilding positive samples: {ev['event_id']} ({region})")

        # Rainfall for event window
        event_rain = compute_window_rainfall(region, ev["event_id"], ev_start, ev_end)

        if event_rain.empty:
            log.warning(f"  No CHIRPS data for {ev['event_id']} — cannot build samples")
            continue

        # Antecedent rainfall
        ant_rain = compute_antecedent_rainfall(region, ev_start, ant_days=14)

        if not ant_rain.empty:
            event_rain = event_rain.merge(
                ant_rain.drop(columns=["pilot_region"], errors="ignore"),
                on="cell_id", how="left"
            )

        # Static terrain
        terrain_df = load_static_terrain(region)
        if not terrain_df.empty:
            terrain_cols = ["cell_id"] + [c for c in terrain_df.columns if c not in
                           ["cell_id", "lat_center", "lon_center", "lat_min", "lat_max",
                            "lon_min", "lon_max", "pilot_region", "spatial_unit_type",
                            "data_type", "ingested_at"]]
            event_rain = event_rain.merge(
                terrain_df[terrain_cols],
                on="cell_id", how="left"
            )

        # Labels
        event_rain["label"] = 1
        event_rain["label_source"] = str(ev.get("label_source", "curated"))
        event_rain["source_quality"] = str(ev.get("source_quality", "dfo_validated"))
        event_rain["label_confidence"] = str(ev.get("label_confidence", "high"))
        event_rain["label_type"] = "dynamic_event_flood"
        event_rain["event_type"] = str(ev.get("event_type", "flood"))

        # Provenance
        event_rain["rain_source"] = "CHIRPS-2.0"
        event_rain["river_source"] = None  # CWC MANUAL_REQUIRED
        event_rain["soil_source"] = None   # ERA5/SMAP MANUAL_REQUIRED
        event_rain["terrain_source_col"] = event_rain.get("terrain_source", None)

        # Data coverage score (fraction of expected features present)
        feature_cols = ["rain_event_sum_mm", "ant_7d_mm", "elev_mean_m"]
        available = sum(1 for c in feature_cols if c in event_rain.columns and event_rain[c].notna().any())
        event_rain["data_coverage"] = round(available / len(feature_cols), 2)

        event_rain["data_type"] = "REAL_DATA — NOT SYNTHETIC"
        event_rain["sample_id"] = event_rain["cell_id"] + "__" + ev["event_id"]

        all_samples.append(event_rain)
        log.info(f"  Built {len(event_rain)} positive samples for {ev['event_id']}")

    return pd.concat(all_samples, ignore_index=True) if all_samples else pd.DataFrame()


def build_negative_samples(neg_windows_df: pd.DataFrame) -> pd.DataFrame:
    """Build negative (non-flood) training samples with antecedent parity."""
    all_samples = []

    for _, win in neg_windows_df.iterrows():
        region_map = {
            "uttarakhand": "uttarakhand",
            "kerala_wayanad": "kerala_wayanad",
            "kerala": "kerala_wayanad",
            "assam": "assam",
        }
        state_lower = str(win.get("state", "")).lower()
        region = next((r for k, r in region_map.items() if k in state_lower), None)
        if not region:
            # Try region field
            region = win.get("region", None)

        if not region or region not in PILOT_BBOXES:
            log.info(f"  Skipping negative {win['window_id']}: region not in pilot")
            continue

        win_start = pd.to_datetime(win["date_start"]).date()
        win_end   = pd.to_datetime(win["date_end"]).date()

        # Limit negative window to 14 days to balance with positives
        if (win_end - win_start).days > 14:
            win_end = win_start + timedelta(days=13)

        log.info(f"\nBuilding negative samples: {win['window_id']} ({region})")

        neg_rain = compute_window_rainfall(region, win["window_id"], win_start, win_end)

        if neg_rain.empty:
            log.warning(f"  No CHIRPS data for {win['window_id']} — cannot build negatives")
            continue

        # ── Antecedent rainfall — PARITY with positives (leakage fix) ─────────
        # Pre-window CHIRPS must be downloaded before this step.
        # Negative windows have antecedent CHIRPS downloaded:
        #   UK Apr 2013   → antecedent: Mar 18-31 2013
        #   Kerala Mar 2019 → antecedent: Feb 15-28 2019
        #   Assam Jan 2022 → antecedent: Dec 18-31 2021
        ant_rain = compute_antecedent_rainfall(region, win_start, ant_days=14)
        if not ant_rain.empty:
            neg_rain = neg_rain.merge(
                ant_rain.drop(columns=["pilot_region"], errors="ignore"),
                on="cell_id", how="left"
            )
            n_ant = int(ant_rain["n_days_ant_7d"].iloc[0]) if "n_days_ant_7d" in ant_rain.columns else "?"
            log.info(f"  Antecedent: {n_ant} days for 7d window (parity with positives)")
        else:
            log.warning(f"  No antecedent CHIRPS for {win['window_id']} "
                        f"— ant_* will be null (parity broken for this window)")

        terrain_df = load_static_terrain(region)
        if not terrain_df.empty:
            terrain_cols = ["cell_id"] + [c for c in terrain_df.columns if c not in
                           ["cell_id", "lat_center", "lon_center", "lat_min", "lat_max",
                            "lon_min", "lon_max", "pilot_region", "spatial_unit_type",
                            "data_type", "ingested_at"]]
            neg_rain = neg_rain.merge(terrain_df[terrain_cols], on="cell_id", how="left")

        neg_rain["label"] = 0
        neg_rain["label_source"] = str(win.get("source", "verified_non_flood"))
        neg_rain["source_quality"] = "verified_reference_window"
        neg_rain["label_confidence"] = str(win.get("confidence", "medium"))
        neg_rain["label_type"] = "verified_non_event"
        neg_rain["event_type"] = "non_event"
        neg_rain["rain_source"] = "CHIRPS-2.0"
        neg_rain["river_source"] = None
        neg_rain["soil_source"] = None
        neg_rain["terrain_source_col"] = neg_rain.get("terrain_source", None)
        neg_rain["data_type"] = "REAL_DATA — NOT SYNTHETIC"
        neg_rain["sample_id"] = neg_rain["cell_id"] + "__" + win["window_id"]

        feature_cols = ["rain_event_sum_mm", "ant_7d_mm", "elev_mean_m"]
        available = sum(1 for c in feature_cols
                        if c in neg_rain.columns and neg_rain[c].notna().any())
        neg_rain["data_coverage"] = round(available / len(feature_cols), 2)

        all_samples.append(neg_rain)
        log.info(f"  Built {len(neg_rain)} negative samples for {win['window_id']}")

    return pd.concat(all_samples, ignore_index=True) if all_samples else pd.DataFrame()


def validate_matrix(df: pd.DataFrame) -> dict:
    """Validate the feature matrix before saving."""
    report = {}

    report["n_rows"] = len(df)
    report["n_cols"] = len(df.columns)
    report["n_duplicates"] = df.duplicated(subset=["sample_id"]).sum() if "sample_id" in df.columns else "N/A"
    report["label_distribution"] = df["label"].value_counts().to_dict() if "label" in df.columns else {}
    report["region_distribution"] = df["pilot_region"].value_counts().to_dict() if "pilot_region" in df.columns else {}
    report["event_distribution"] = df["event_id"].value_counts().to_dict() if "event_id" in df.columns else {}
    report["data_type_check"] = "PASS" if df.get("data_type", pd.Series([""])).str.startswith("REAL").all() else "FAIL"

    # Missingness
    report["missingness"] = {}
    key_cols = ["rain_event_sum_mm", "ant_7d_mm", "elev_mean_m", "slope_mean_deg",
                "label", "label_source", "data_coverage"]
    for col in key_cols:
        if col in df.columns:
            null_pct = 100 * df[col].isna().mean()
            report["missingness"][col] = f"{null_pct:.1f}%"

    # Range checks
    report["range_checks"] = {}
    if "rain_event_sum_mm" in df.columns:
        min_r = df["rain_event_sum_mm"].min()
        max_r = df["rain_event_sum_mm"].max()
        report["range_checks"]["rain_event_sum_mm"] = {"min": min_r, "max": max_r,
                                                        "plausible": bool(min_r >= 0 and max_r < 3000)}
    if "elev_mean_m" in df.columns:
        min_e = df["elev_mean_m"].min()
        max_e = df["elev_mean_m"].max()
        report["range_checks"]["elev_mean_m"] = {"min": min_e, "max": max_e,
                                                   "plausible": bool(-100 <= min_e and max_e < 9000)}

    # Synthetic check
    synthetic_check = (df.get("data_type", pd.Series([""])) == "REAL_DATA — NOT SYNTHETIC").all()
    report["synthetic_contamination"] = "NONE" if synthetic_check else "POSSIBLE_CONTAMINATION"

    # Class balance
    if "label" in df.columns:
        pos = (df["label"] == 1).sum()
        neg = (df["label"] == 0).sum()
        report["class_balance"] = {"positive": int(pos), "negative": int(neg),
                                    "imbalance_ratio": f"1:{neg//pos}" if pos > 0 else "N/A"}

    return report


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Flood Training Matrix  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)

    FEAT_DIR.mkdir(parents=True, exist_ok=True)

    # Load events
    events_path = EVENTS_DIR / "flood_events.parquet"
    neg_path    = EVENTS_DIR / "non_flood_reference_windows.parquet"

    if not events_path.exists():
        log.error("Flood events not found. Run ingest_flood_events.py first.")
        sys.exit(1)

    events_df = pd.read_parquet(str(events_path))
    neg_df    = pd.read_parquet(str(neg_path)) if neg_path.exists() else pd.DataFrame()

    log.info(f"Events: {len(events_df)} positive, {len(neg_df)} negative windows")

    # Build samples
    pos_df = build_positive_samples(events_df)
    neg_df_samples = build_negative_samples(neg_df) if not neg_df.empty else pd.DataFrame()

    if pos_df.empty and neg_df_samples.empty:
        log.error("No samples built. Ensure CHIRPS data and static terrain are available.")
        sys.exit(1)

    # Combine
    all_parts = [df for df in [pos_df, neg_df_samples] if not df.empty]
    combined = pd.concat(all_parts, ignore_index=True)

    log.info(f"\nTotal flood training rows: {len(combined)}")
    log.info(f"  Positive: {(combined['label'] == 1).sum()}")
    log.info(f"  Negative: {(combined['label'] == 0).sum()}")
    log.info(f"  Features: {len(combined.columns)}")

    # Validate
    val_report = validate_matrix(combined)
    log.info(f"\nValidation report:")
    for k, v in val_report.items():
        log.info(f"  {k}: {v}")

    # Save
    out_path = FEAT_DIR / "flood_training.parquet"
    combined.to_parquet(str(out_path), index=False, engine="pyarrow")
    combined.to_csv(str(FEAT_DIR / "flood_training.csv"), index=False)
    log.info(f"\nSaved: {out_path}")

    # Save validation report
    val_report["timestamp"] = datetime.now(timezone.utc).isoformat()
    val_report["data_type"] = "REAL_DATA — NOT SYNTHETIC"
    with open(FEAT_DIR / "flood_training_validation.json", "w") as f:
        json.dump(val_report, f, indent=2, default=str)

    log.info("\nREADY FOR REVIEW — NOT yet for model training.")
    log.info("Next steps before training:")
    log.info("  1. Ingest IMERG sub-daily for 1h/3h/6h intensity features")
    log.info("  2. Ingest CWC river level data (MANUAL_REQUIRED)")
    log.info("  3. Verify negative samples against actual low-flow periods")
    log.info("  4. Add more DEM tiles for full pilot region terrain coverage")


if __name__ == "__main__":
    main()
