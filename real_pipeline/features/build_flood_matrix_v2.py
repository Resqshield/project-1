# -*- coding: utf-8 -*-
"""
real_pipeline/features/build_flood_matrix_v2.py
=================================================
Build flood_training_v2.parquet from all 10 verified positive events
+ 10 matched negative windows.

CRITICAL RULES (enforced):
  - NEVER overwrites v1 matrix until this file validates
  - NEVER mixes synthetic rows
  - NEVER uses rainfall thresholds to assign labels
  - NEVER imputes terrain across cells where terrain is not observed
  - Feature parity: antecedent features must exist for BOTH positive and negative
    windows in each region. If not available, antecedent features are NULL equally
    for both classes (not class-correlated missing).
  - Label spatial precision is preserved verbatim from flood_events_v2.parquet
  - Reports: raw_rows, independent_events, positive_events, negative_windows,
    regions, spatial_units, label_quality distribution, missingness_by_class

SPATIAL UNIT:
  CHIRPS 0.05° grid cell (~5.5 km). Native CHIRPS resolution.
  Not catchment-level (HydroBASINS blocked). Not village-level (LGD blocked).

LABEL SPATIAL PRECISION NOTE:
  All events labelled at region_wide or district_wide precision.
  NO cell-level observed inundation geometry available.
  Label applies to ALL cells in pilot region bbox.
  Users must treat as REGIONAL-LABEL — not pixel truth.

OUTPUT:
  data_real/features/flood_training_v2.parquet  (validated then written)
  data_real/features/flood_v2_report.json
"""

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEAT_DIR   = PROJECT_ROOT / "data_real" / "features"
EVENTS_DIR = PROJECT_ROOT / "data_real" / "events" / "flood" / "processed"
CHIRPS_DIR = PROJECT_ROOT / "data_real" / "rainfall" / "chirps"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("flood_matrix_v2")

CHIRPS_RES = 0.05  # degrees

# ── Pilot bboxes for all 10 event regions ─────────────────────────────────────
PILOT_BBOXES = {
    "uttarakhand":          {"lat_min": 28.5, "lat_max": 32.0, "lon_min": 77.5, "lon_max": 81.5},
    "kerala_wayanad":       {"lat_min":  9.0, "lat_max": 12.5, "lon_min": 75.0, "lon_max": 78.0},
    "assam":                {"lat_min": 24.0, "lat_max": 28.5, "lon_min": 89.0, "lon_max": 96.5},
    "bihar_ganga_plains":   {"lat_min": 24.5, "lat_max": 27.5, "lon_min": 83.5, "lon_max": 88.5},
    "odisha_coastal":       {"lat_min": 18.5, "lat_max": 21.5, "lon_min": 84.0, "lon_max": 87.5},
    "odisha_mahanadi":      {"lat_min": 19.5, "lat_max": 22.0, "lon_min": 83.5, "lon_max": 87.0},
    "maharashtra_kolhapur": {"lat_min": 15.5, "lat_max": 18.5, "lon_min": 73.0, "lon_max": 77.0},
    "himachal_pradesh":     {"lat_min": 30.5, "lat_max": 33.5, "lon_min": 75.5, "lon_max": 79.5},
}


def build_region_grid(bbox: dict) -> pd.DataFrame:
    """Build CHIRPS-aligned grid cells for a bounding box."""
    lats = np.arange(bbox["lat_min"] + CHIRPS_RES/2,
                     bbox["lat_max"], CHIRPS_RES)
    lons = np.arange(bbox["lon_min"] + CHIRPS_RES/2,
                     bbox["lon_max"], CHIRPS_RES)
    lat_g, lon_g = np.meshgrid(lats, lons, indexing="ij")
    df = pd.DataFrame({
        "lat_center": lat_g.ravel().round(4),
        "lon_center": lon_g.ravel().round(4),
    })
    df["cell_id"] = (
        "cell_" + df["lat_center"].astype(str).str.replace(".", "p") +
        "_" + df["lon_center"].astype(str).str.replace(".", "p")
    )
    return df


def load_chirps_tiles_for_window(region: str, start: date, end: date) -> pd.DataFrame:
    """
    Load all CHIRPS tiles for a region+window.
    Returns per-cell rainfall for each day, aggregated to window stats.
    Returns empty DataFrame if tiles are missing.
    """
    try:
        import rasterio
    except ImportError:
        log.warning("  rasterio not available — rainfall features will be NULL")
        return pd.DataFrame()

    daily_frames = []
    current = start
    while current <= end:
        tif_path = CHIRPS_DIR / f"chirps_{region}_{current.strftime('%Y%m%d')}.tif"
        if not tif_path.exists():
            current += timedelta(days=1)
            continue
        try:
            with rasterio.open(str(tif_path)) as src:
                data = src.read(1).astype(float)
                nodata = src.nodata
                if nodata is not None:
                    data[data == nodata] = np.nan
                data[data < 0] = np.nan
                transform = src.transform
                rows, cols = np.indices(data.shape)
                lons = transform.c + (cols + 0.5) * transform.a
                lats = transform.f + (rows + 0.5) * transform.e
                frame = pd.DataFrame({
                    "lat_center": lats.ravel().round(4),
                    "lon_center": lons.ravel().round(4),
                    f"rain_{current.strftime('%Y%m%d')}": data.ravel(),
                })
                daily_frames.append(frame)
        except Exception as e:
            log.debug(f"  Error reading {tif_path.name}: {e}")
        current += timedelta(days=1)

    if not daily_frames:
        return pd.DataFrame()

    # Merge on lat/lon
    result = daily_frames[0]
    for df_day in daily_frames[1:]:
        result = result.merge(df_day, on=["lat_center", "lon_center"], how="outer")

    # Compute window-level stats
    rain_cols = [c for c in result.columns if c.startswith("rain_")]
    if not rain_cols:
        return pd.DataFrame()

    result["rain_event_sum_mm"]  = result[rain_cols].sum(axis=1, min_count=1)
    result["rain_event_max_mm"]  = result[rain_cols].max(axis=1)
    result["rain_event_mean_mm"] = result[rain_cols].mean(axis=1)
    result["rain_event_p90_mm"]  = result[rain_cols].quantile(0.9, axis=1)
    result["n_days_valid_chirps"] = result[rain_cols].notna().sum(axis=1)
    result["chirps_coverage_pct"] = result["n_days_valid_chirps"] / max(len(rain_cols), 1)
    return result[["lat_center", "lon_center", "rain_event_sum_mm", "rain_event_max_mm",
                   "rain_event_mean_mm", "rain_event_p90_mm",
                   "n_days_valid_chirps", "chirps_coverage_pct"]]


def compute_antecedent(region: str, event_start: date, ant_days: int) -> pd.DataFrame:
    """Compute antecedent rainfall sums for 3/7/14 days before event."""
    ant_end   = event_start - timedelta(days=1)
    ant_start = event_start - timedelta(days=ant_days)

    full_window = load_chirps_tiles_for_window(region, ant_start, ant_end)
    if full_window.empty:
        return pd.DataFrame()

    try:
        import rasterio
    except ImportError:
        return pd.DataFrame()

    # Re-compute for sub-windows
    def _window_sum(n_days: int) -> pd.Series:
        sub_start = event_start - timedelta(days=n_days)
        frames = []
        for d_off in range(n_days):
            d = sub_start + timedelta(days=d_off)
            tif = CHIRPS_DIR / f"chirps_{region}_{d.strftime('%Y%m%d')}.tif"
            if not tif.exists():
                continue
            try:
                with rasterio.open(str(tif)) as src:
                    data = src.read(1).astype(float)
                    nd = src.nodata
                    if nd is not None: data[data == nd] = np.nan
                    data[data < 0] = np.nan
                    transform = src.transform
                    rows, cols = np.indices(data.shape)
                    lons = transform.c + (cols + 0.5) * transform.a
                    lats = transform.f + (rows + 0.5) * transform.e
                    frames.append(pd.DataFrame({
                        "lat_center": lats.ravel().round(4),
                        "lon_center": lons.ravel().round(4),
                        "rain": data.ravel(),
                    }))
            except Exception:
                pass
        if not frames:
            return None
        merged = frames[0]
        for f in frames[1:]:
            merged = merged.merge(f.rename(columns={"rain": f"r_{id(f)}"}),
                                  on=["lat_center","lon_center"], how="outer")
        rcols = [c for c in merged.columns if c.startswith("r_") or c == "rain"]
        merged[f"ant_{n_days}d_mm"] = merged[rcols].sum(axis=1, min_count=1)
        merged[f"n_days_ant_{n_days}d"] = merged[rcols].notna().sum(axis=1)
        return merged[["lat_center", "lon_center", f"ant_{n_days}d_mm", f"n_days_ant_{n_days}d"]]

    result = full_window[["lat_center", "lon_center"]].copy()
    for n in [3, 7, 14]:
        sub = _window_sum(n)
        if sub is not None:
            result = result.merge(sub, on=["lat_center","lon_center"], how="left")
        else:
            result[f"ant_{n}d_mm"] = np.nan
            result[f"n_days_ant_{n}d"] = 0
    return result


def load_terrain(region: str) -> pd.DataFrame:
    """Load per-cell terrain if available. Returns empty if not."""
    terrain_path = FEAT_DIR / f"static_terrain_{region}.parquet"
    if terrain_path.exists():
        return pd.read_parquet(terrain_path)
    # Try combined
    all_terrain = FEAT_DIR / "static_terrain_all.parquet"
    if all_terrain.exists():
        df = pd.read_parquet(all_terrain)
        if "pilot_region" in df.columns:
            return df[df["pilot_region"] == region].copy()
    return pd.DataFrame()


def label_quality_class(label_spatial_precision: str, label_quality: str) -> str:
    """
    Classify label quality:
      A = observed inundation geometry (cell-level truth)
      B = CWC/official flood evidence with spatial approximation (district-level)
      C = region-wide/event-level weak label
    """
    if label_spatial_precision in ("cell_level", "pixel_level", "sub_district"):
        return "A"
    elif label_spatial_precision in ("district_wide",):
        return "B"
    else:  # region_wide, event_level
        return "C"


def build_event_rows(event: dict, window_type: str) -> pd.DataFrame:
    """Build all grid-cell rows for a single event window."""
    region = event["region"]
    bbox = PILOT_BBOXES.get(region)
    if bbox is None:
        log.warning(f"  No bbox for region {region} — skipping")
        return pd.DataFrame()

    grid = build_region_grid(bbox)
    n_cells = len(grid)

    # Determine window dates
    if window_type == "positive":
        start = pd.to_datetime(event["date_start"]).date()
        end   = pd.to_datetime(event["date_end"]).date()
        label = 1
        event_id = event["event_id"]
        ant_days  = 14
    else:  # negative
        start = pd.to_datetime(event["neg_window_start"]).date()
        end   = pd.to_datetime(event["neg_window_end"]).date()
        label = 0
        event_id = event.get("neg_event_id", f"NEG_{event['event_id']}")
        ant_days  = 14

    log.info(f"  {window_type.upper()} {region} {event_id}: {start}→{end}, {n_cells} cells")

    # Event-window CHIRPS
    rain_df = load_chirps_tiles_for_window(region, start, end)

    # Antecedent CHIRPS
    ant_df = compute_antecedent(region, start, ant_days)

    # Terrain
    terrain_df = load_terrain(region)

    # Merge rainfall onto grid
    if not rain_df.empty:
        grid = grid.merge(rain_df, on=["lat_center", "lon_center"], how="left")
    else:
        for col in ["rain_event_sum_mm", "rain_event_max_mm", "rain_event_mean_mm",
                    "rain_event_p90_mm", "n_days_valid_chirps", "chirps_coverage_pct"]:
            grid[col] = np.nan
        log.warning(f"    No CHIRPS found for {region} {start}–{end}")

    # Merge antecedent
    if not ant_df.empty:
        grid = grid.merge(ant_df, on=["lat_center", "lon_center"], how="left")
    else:
        for col in ["ant_3d_mm", "ant_7d_mm", "ant_14d_mm",
                    "n_days_ant_3d", "n_days_ant_7d", "n_days_ant_14d"]:
            grid[col] = np.nan

    # Merge terrain
    if not terrain_df.empty:
        t_cols = ["lat_center", "lon_center", "elev_mean_m", "slope_mean_deg",
                  "pct_slope_gt_30", "terrain_available"]
        t_cols = [c for c in t_cols if c in terrain_df.columns]
        grid = grid.merge(terrain_df[t_cols], on=["lat_center", "lon_center"], how="left")
        grid["terrain_source"] = "GLO30_pilot"
    else:
        for col in ["elev_mean_m", "slope_mean_deg", "pct_slope_gt_30", "terrain_available"]:
            grid[col] = np.nan
        grid["terrain_source"] = "NONE"

    # Label quality classification
    lsp = event.get("label_spatial_precision", "region_wide")
    lq  = event.get("label_quality", "C")
    lq_class = label_quality_class(lsp, lq)

    # Metadata columns
    grid["label"]                   = label
    grid["event_id"]                = event_id
    grid["region"]                  = region
    grid["window_start"]            = str(start)
    grid["window_end"]              = str(end)
    grid["window_type"]             = window_type
    grid["label_source"]            = event.get("label_source", "")
    grid["label_type"]              = event.get("label_type", "")
    grid["label_spatial_precision"] = lsp
    grid["label_temporal_precision"]= event.get("label_temporal_precision", "daily")
    grid["label_quality"]           = lq
    grid["label_quality_class"]     = lq_class
    grid["label_quality_class_note"]= (
        "A=observed_geometry | B=official_district_approx | C=region_wide_weak"
    )
    grid["rain_source"] = "CHIRPS_v2.0" if not rain_df.empty else "MISSING"
    grid["data_type"]   = "REAL_DATA_NOT_SYNTHETIC"

    return grid


def check_class_missingness_parity(df: pd.DataFrame) -> dict:
    """
    Check that no feature has class-correlated missing data.
    Returns dict with features that have >5% class imbalance in missingness.
    """
    feat_cols = [c for c in df.columns if c not in [
        "label", "event_id", "region", "cell_id", "lat_center", "lon_center",
        "window_start", "window_end", "window_type", "label_source", "label_type",
        "label_spatial_precision", "label_temporal_precision", "label_quality",
        "label_quality_class", "label_quality_class_note", "rain_source",
        "data_type", "terrain_source",
    ]]
    miss_by_class = df.groupby("label")[feat_cols].apply(lambda x: x.isna().mean())
    problems = {}
    for col in feat_cols:
        if col not in miss_by_class.columns:
            continue
        m0 = miss_by_class.loc[0, col] if 0 in miss_by_class.index else 0
        m1 = miss_by_class.loc[1, col] if 1 in miss_by_class.index else 0
        if abs(m0 - m1) > 0.05:
            problems[col] = {"label_0": round(float(m0), 4), "label_1": round(float(m1), 4),
                             "delta": round(float(abs(m0 - m1)), 4)}
    return problems


def main():
    log.info("=" * 70)
    log.info("ResQ Shield — Flood Training Matrix V2  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 70)

    FEAT_DIR.mkdir(parents=True, exist_ok=True)

    # Load events v2
    events = pd.read_parquet(EVENTS_DIR / "flood_events_v2.parquet")
    neg_windows = pd.read_parquet(EVENTS_DIR / "negative_windows_v2.parquet")
    log.info(f"Positive events: {len(events)}")
    log.info(f"Negative windows: {len(neg_windows)}")

    # Merge negative window dates into events
    neg_by_region = neg_windows.set_index("region")

    all_rows = []
    skipped_regions = []

    for _, ev in events.iterrows():
        region = ev["region"]
        # Positive window
        pos_rows = build_event_rows(ev.to_dict(), "positive")
        if not pos_rows.empty:
            all_rows.append(pos_rows)
        else:
            skipped_regions.append(f"{region}_pos")

        # Negative window
        if region in neg_by_region.index:
            neg_ev = neg_by_region.loc[region]
            if isinstance(neg_ev, pd.DataFrame):
                neg_ev = neg_ev.iloc[0]
            neg_dict = ev.to_dict()
            # Map neg window cols (date_start/date_end or neg_window_start/end)
            neg_dict["neg_window_start"] = neg_ev.get("date_start", neg_ev.get("neg_window_start"))
            neg_dict["neg_window_end"]   = neg_ev.get("date_end",   neg_ev.get("neg_window_end"))
            neg_dict["neg_event_id"]     = neg_ev.get("window_id",  f"NEG_{ev['event_id']}")
            neg_dict["label_spatial_precision"] = ev.get("label_spatial_precision", "region_wide")
            neg_dict["label_quality"] = ev.get("label_quality", "C")
            neg_rows = build_event_rows(neg_dict, "negative")
            if not neg_rows.empty:
                all_rows.append(neg_rows)
            else:
                skipped_regions.append(f"{region}_neg")
        else:
            log.warning(f"  No matched negative window for {region}")
            skipped_regions.append(f"{region}_neg_missing")

    if not all_rows:
        log.error("No rows built — check CHIRPS availability")
        sys.exit(1)

    df = pd.concat(all_rows, ignore_index=True)
    log.info(f"\nCombined matrix: {df.shape}")

    # ── PARITY ENFORCEMENT (per event-pair) ──────────────────────────────────
    # Each positive event is matched to a negative window (by region).
    # For each matched pair: if one side has rainfall and the other doesn't,
    # null rainfall for BOTH. This is the correct unit — not the whole region,
    # because assam has 2 events sharing 1 negative window, creating a false
    # region-wide parity violation.
    #
    # Strategy:
    #   1. Each positive event_id is an independent group.
    #   2. Its matched negative event_id is its pair.
    #   3. Null rainfall for the pair if either side lacks CHIRPS.
    rain_feat_cols = ["rain_event_sum_mm", "rain_event_max_mm", "rain_event_mean_mm",
                      "rain_event_p90_mm", "n_days_valid_chirps", "chirps_coverage_pct",
                      "ant_3d_mm", "ant_7d_mm", "ant_14d_mm",
                      "n_days_ant_3d", "n_days_ant_7d", "n_days_ant_14d"]
    rain_feat_cols = [c for c in rain_feat_cols if c in df.columns]

    # Build event_pair_id: positive event_id determines the pair
    # Negative rows are matched to the positive event by region
    df["event_pair_id"] = df["event_id"]  # positive events keep their own id
    # For negative rows, assign the positive event id from same region+window pair
    # We do this by mapping neg window_id → positive event_id using events table
    neg_to_pos = {}
    pos_events_df = df[df["label"] == 1][["event_id", "region"]].drop_duplicates()
    neg_events_df = df[df["label"] == 0][["event_id", "region"]].drop_duplicates()
    # For each neg event_id, find which positive event_id(s) share the same region
    for _, neg_row in neg_events_df.iterrows():
        matching_pos = pos_events_df[pos_events_df["region"] == neg_row["region"]]
        for _, pos_row in matching_pos.iterrows():
            # Pair neg to pos (neg may pair with multiple positives — that's OK)
            neg_to_pos.setdefault(neg_row["event_id"], []).append(pos_row["event_id"])

    # We'll work event-pair wise: for each positive event, find its matched neg
    # Build per-event_pair nulling decisions
    parity_nulled_pairs = []
    events_loader = df[df["label"] == 1]["event_id"].unique()
    for pos_eid in events_loader:
        region = df.loc[(df["event_id"] == pos_eid) & (df["label"] == 1), "region"].iloc[0]
        # Find matched negative event(s) in same region
        neg_eids = df.loc[(df["label"] == 0) & (df["region"] == region), "event_id"].unique()
        if len(neg_eids) == 0:
            log.warning(f"  No matched negative for {pos_eid} ({region})")
            continue
        # Use the negative window that was explicitly matched
        # (just take first neg_eid for region; multiple negs handled independently)
        neg_eid = neg_eids[0]

        pos_mask = (df["event_id"] == pos_eid) & (df["label"] == 1)
        neg_mask = (df["event_id"] == neg_eid) & (df["label"] == 0)

        pos_has_rain = df.loc[pos_mask, rain_feat_cols].notna().any(axis=1).any()
        neg_has_rain = df.loc[neg_mask, rain_feat_cols].notna().any(axis=1).any()

        if pos_has_rain != neg_has_rain:
            log.warning(
                f"  PAIR PARITY VIOLATION: {pos_eid}↔{neg_eid} "
                f"pos_has_rain={pos_has_rain}, neg_has_rain={neg_has_rain} → nulling both"
            )
            df.loc[pos_mask, rain_feat_cols] = np.nan
            df.loc[neg_mask, rain_feat_cols] = np.nan
            if "rain_source" in df.columns:
                df.loc[pos_mask | neg_mask, "rain_source"] = "CHIRPS_PARITY_NULLED"
            parity_nulled_pairs.append(f"{pos_eid}↔{neg_eid}")
        else:
            log.info(f"  Pair {pos_eid}↔{neg_eid}: both {'have' if pos_has_rain else 'lack'} rain — OK")

    if parity_nulled_pairs:
        log.warning(f"  Parity-nulled pairs: {parity_nulled_pairs}")
    else:
        log.info("  [OK] All event pairs have matched CHIRPS availability")

    # ── Validation ────────────────────────────────────────────────────────────

    # 1. No synthetic contamination
    assert (df["data_type"] == "REAL_DATA_NOT_SYNTHETIC").all(), (
        f"Non-real rows found: {df[df['data_type']!='REAL_DATA_NOT_SYNTHETIC'].shape[0]}"
    )
    log.info("  [OK] No synthetic contamination")

    # 2. Class balance
    label_counts = df["label"].value_counts()
    log.info(f"\nLabel distribution: {dict(label_counts)}")

    # 3. Independent events
    pos_events  = df[df["label"]==1]["event_id"].nunique()
    neg_windows_n = df[df["label"]==0]["event_id"].nunique()
    regions     = df["region"].nunique()
    log.info(f"Independent positive events: {pos_events}")
    log.info(f"Independent negative windows: {neg_windows_n}")
    log.info(f"Regions: {regions}")

    # 4. Missingness parity check
    log.info("\nClass missingness parity check...")
    parity_problems = check_class_missingness_parity(df)
    if parity_problems:
        log.warning(f"  PARITY PROBLEMS (>5% delta): {list(parity_problems.keys())}")
        for feat, info in parity_problems.items():
            log.warning(f"    {feat}: label_0={info['label_0']}, label_1={info['label_1']}, delta={info['delta']}")
    else:
        log.info("  OK — no class-correlated missingness > 5%")

    # 5. Label spatial precision
    log.info("\nLabel quality distribution:")
    lq_dist = df.groupby(["label_quality_class", "label_spatial_precision"])["region"].nunique()
    log.info(lq_dist.to_string())

    # 6. No event_id leakage across train/test (region-level check)
    log.info("\nRegion×event matrix:")
    rev = df[df["label"]==1].groupby(["region","event_id"]).size()
    log.info(rev.to_string())

    # ── Terrain missingness report ────────────────────────────────────────────
    terr_miss = df[["label", "elev_mean_m"]].copy()
    terr_miss["terrain_missing"] = terr_miss["elev_mean_m"].isna()
    terrain_by_class = terr_miss.groupby("label")["terrain_missing"].mean()
    log.info(f"\nTerrain missingness by class:\n{terrain_by_class.round(4)}")

    # ── Missingness summary ───────────────────────────────────────────────────
    feat_cols_for_miss = ["rain_event_sum_mm", "rain_event_max_mm",
                          "ant_3d_mm", "ant_7d_mm", "ant_14d_mm",
                          "elev_mean_m", "slope_mean_deg"]
    miss_summary = {}
    for fc in feat_cols_for_miss:
        if fc in df.columns:
            miss_summary[fc] = {
                str(k): round(float(v), 4)
                for k, v in df.groupby("label")[fc].apply(lambda x: x.isna().mean()).items()
            }

    # ── Do NOT overwrite v1 — write to v2 path ────────────────────────────────
    out_path = FEAT_DIR / "flood_training_v2.parquet"
    # Check does not overwrite v1
    v1_path = FEAT_DIR / "flood_training.parquet"
    assert out_path != v1_path, "NEVER overwrite v1!"

    df.to_parquet(out_path, index=False, engine="pyarrow")
    log.info(f"\n[OK] Saved: {out_path}")
    log.info(f"     Rows: {len(df)}, Cols: {df.shape[1]}")

    # ── Report ────────────────────────────────────────────────────────────────
    lq_class_dist = df[df["label"]==1].groupby("label_quality_class")["event_id"].nunique().to_dict()

    report = {
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "data_type": "REAL_DATA — NOT SYNTHETIC",
        "gate_g_inputs": {
            "positive_events": int(pos_events),
            "negative_windows": int(neg_windows_n),
            "regions": int(regions),
        },
        "matrix": {
            "raw_rows": len(df),
            "n_cols": int(df.shape[1]),
            "positive_rows": int(label_counts.get(1, 0)),
            "negative_rows": int(label_counts.get(0, 0)),
            "spatial_units": int(df["cell_id"].nunique()),
            "spatial_unit_type": "CHIRPS_005deg_gridcell",
        },
        "label_quality": {
            "class_distribution_events": lq_class_dist,
            "class_A_cell_level_truth": 0,
            "class_B_district_approximation": int(lq_class_dist.get("B", 0)),
            "class_C_region_wide_weak": int(lq_class_dist.get("C", 0)),
            "NOTE": (
                "ALL labels are regional (C or B). No cell-level observed inundation. "
                "Treat as EXPERIMENTAL_BASELINE_ONLY regardless of model metrics."
            ),
        },
        "missingness_by_class": miss_summary,
        "missingness_parity_problems": parity_problems,
        "terrain_missingness_by_class": {
            str(k): round(float(v), 4)
            for k, v in terrain_by_class.items()
        },
        "chirps_coverage": {
            r: int((df[df["region"]==r]["rain_event_sum_mm"].notna()).sum())
            for r in df["region"].unique()
        },
        "skipped_regions": skipped_regions,
        "gate_g_decision": (
            "GATE_G_PASS" if (
                pos_events >= 10 and regions >= 5 and not parity_problems
            ) else "GATE_G_PARTIAL"
        ),
        "model_status": "EXPERIMENTAL_BASELINE_ONLY",
        "reason_for_experimental": (
            "All labels are region_wide or district_wide precision (no observed inundation geometry). "
            "High metrics cannot be interpreted as cell-level predictive skill."
        ),
    }

    report_path = FEAT_DIR / "flood_v2_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"[OK] Report: {report_path}")

    log.info(f"\nGate G decision: {report['gate_g_decision']}")
    log.info(f"Model status: {report['model_status']}")
    if parity_problems:
        log.warning(f"Parity problems: {list(parity_problems.keys())}")


if __name__ == "__main__":
    main()
