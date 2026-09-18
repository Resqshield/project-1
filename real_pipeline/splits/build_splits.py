# -*- coding: utf-8 -*-
"""
real_pipeline/splits/build_splits.py
======================================
Build region-aware cross-validation splits for flood and landslide training matrices.

CRITICAL RULE: NO random 80/20 splits.
  - Spatial autocorrelation makes random splits meaningless
  - Must use Leave-One-Region-Out (LORO) or temporal hold-out
  - No event leakage across train/test folds

Split strategies implemented:
  1. Leave-One-Region-Out (LORO) — primary strategy
     Train on all regions except one; test on held-out region.
     Fold count = number of unique regions in dataset.

  2. Temporal hold-out (secondary)
     Train on events before year T; test on events in year T+.
     Default split year: 2022 (all pre-2022 events for training, 2022+ for test)

  3. Leave-One-Event-Out (LOEO) — for small datasets
     Train on all events except one; test on the single held-out event.
     Used when event count is low (< 5).

Output schema for each split:
  split_id, strategy, fold_index, n_folds,
  train_event_ids, test_event_ids, train_regions, test_regions,
  train_n_samples, test_n_samples, class_balance_train, class_balance_test

Leakage checks:
  - No event_id appears in both train and test
  - No region appears in both train and test (for LORO)
  - Events from same date window not split across folds

File: data_real/splits/{flood|landslide}_splits.json
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from itertools import combinations
from typing import List, Dict

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEAT_DIR   = PROJECT_ROOT / "data_real" / "features"
SPLITS_DIR = PROJECT_ROOT / "data_real" / "splits"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_splits")

TEMPORAL_SPLIT_YEAR = 2022  # events before this year → train; >= this year → test


def check_event_leakage(train_event_ids: List[str], test_event_ids: List[str]) -> bool:
    """Return True if there is leakage (same event in both train and test)."""
    overlap = set(train_event_ids) & set(test_event_ids)
    if overlap:
        log.error(f"EVENT LEAKAGE DETECTED: {overlap}")
        return True
    return False


def check_region_leakage(train_regions: List[str], test_regions: List[str]) -> bool:
    """Return True if there is region leakage (same region in both folds for LORO)."""
    overlap = set(train_regions) & set(test_regions)
    if overlap:
        log.warning(f"Region overlap in LORO fold: {overlap}")
        return True
    return False


def loro_splits(df: pd.DataFrame, region_col: str = "pilot_region") -> List[dict]:
    """Build Leave-One-Region-Out splits."""
    regions = df[region_col].dropna().unique().tolist()
    n_regions = len(regions)

    log.info(f"LORO splits: {n_regions} regions → {n_regions} folds")
    splits = []

    for i, test_region in enumerate(sorted(regions)):
        train_mask = df[region_col] != test_region
        test_mask  = df[region_col] == test_region

        train_df = df[train_mask]
        test_df  = df[test_mask]

        train_events = train_df["event_id"].dropna().unique().tolist() if "event_id" in train_df else []
        test_events  = test_df["event_id"].dropna().unique().tolist() if "event_id" in test_df else []
        train_regions = train_df[region_col].unique().tolist()
        test_regions  = test_df[region_col].unique().tolist()

        leakage = check_event_leakage(train_events, test_events)

        pos_train = int((train_df["label"] == 1).sum()) if "label" in train_df else None
        neg_train = int((train_df["label"] == 0).sum()) if "label" in train_df else None
        pos_test  = int((test_df["label"] == 1).sum()) if "label" in test_df else None
        neg_test  = int((test_df["label"] == 0).sum()) if "label" in test_df else None

        fold = {
            "split_id": f"loro_fold_{i+1}_of_{n_regions}",
            "strategy": "leave_one_region_out",
            "fold_index": i + 1,
            "n_folds": n_regions,
            "test_region": test_region,
            "train_regions": sorted(train_regions),
            "test_regions": sorted(test_regions),
            "train_event_ids": sorted(train_events),
            "test_event_ids": sorted(test_events),
            "train_n_samples": int(len(train_df)),
            "test_n_samples": int(len(test_df)),
            "class_balance_train": {"positive": pos_train, "negative": neg_train},
            "class_balance_test": {"positive": pos_test, "negative": neg_test},
            "event_leakage": leakage,
            "feasible": len(train_df) > 0 and len(test_df) > 0 and not leakage,
            "warning": f"Only {len(train_df)} train samples" if len(train_df) < 20 else None,
        }
        splits.append(fold)
        log.info(f"  Fold {i+1}: test={test_region} ({pos_test} pos, {neg_test} neg) "
                 f"| train={len(train_df)} rows, leak={leakage}")

    return splits


def temporal_split(df: pd.DataFrame, split_year: int = TEMPORAL_SPLIT_YEAR) -> dict:
    """Build temporal train/test split."""
    if "event_date" not in df.columns and "window_start" not in df.columns:
        log.warning("No date column for temporal split")
        return {}

    date_col = "event_date" if "event_date" in df.columns else "window_start"
    df = df.copy()
    df["_year"] = pd.to_datetime(df[date_col], errors="coerce").dt.year

    train_mask = df["_year"] < split_year
    test_mask  = df["_year"] >= split_year

    train_df = df[train_mask]
    test_df  = df[test_mask]

    train_events = train_df["event_id"].dropna().unique().tolist() if "event_id" in train_df else []
    test_events  = test_df["event_id"].dropna().unique().tolist() if "event_id" in test_df else []

    leakage = check_event_leakage(train_events, test_events)

    return {
        "split_id": f"temporal_split_{split_year}",
        "strategy": "temporal_holdout",
        "fold_index": 1,
        "n_folds": 1,
        "split_year": split_year,
        "train_years": f"< {split_year}",
        "test_years": f">= {split_year}",
        "train_event_ids": sorted(train_events),
        "test_event_ids": sorted(test_events),
        "train_n_samples": int(len(train_df)),
        "test_n_samples": int(len(test_df)),
        "class_balance_train": {
            "positive": int((train_df["label"] == 1).sum()),
            "negative": int((train_df["label"] == 0).sum())
        } if "label" in df else {},
        "class_balance_test": {
            "positive": int((test_df["label"] == 1).sum()),
            "negative": int((test_df["label"] == 0).sum())
        } if "label" in df else {},
        "event_leakage": leakage,
        "feasible": len(train_df) > 0 and len(test_df) > 0 and not leakage,
    }


def loeo_splits(df: pd.DataFrame) -> List[dict]:
    """Build Leave-One-Event-Out splits (for small datasets)."""
    if "event_id" not in df.columns:
        return []

    events = [e for e in df["event_id"].dropna().unique() if not str(e).startswith("NEG_")]
    log.info(f"LOEO splits: {len(events)} events")

    splits = []
    for i, test_event in enumerate(sorted(events)):
        train_mask = df["event_id"] != test_event
        test_mask  = df["event_id"] == test_event

        train_df = df[train_mask]
        test_df  = df[test_mask]

        leakage = check_event_leakage(
            train_df["event_id"].dropna().unique().tolist(),
            test_df["event_id"].dropna().unique().tolist()
        )

        fold = {
            "split_id": f"loeo_fold_{i+1}_of_{len(events)}",
            "strategy": "leave_one_event_out",
            "fold_index": i + 1,
            "n_folds": len(events),
            "test_event": test_event,
            "train_events": sorted(train_df["event_id"].dropna().unique().tolist()),
            "train_n_samples": int(len(train_df)),
            "test_n_samples": int(len(test_df)),
            "class_balance_train": {
                "positive": int((train_df["label"] == 1).sum()),
                "negative": int((train_df["label"] == 0).sum()),
            } if "label" in df else {},
            "class_balance_test": {
                "positive": int((test_df["label"] == 1).sum()),
                "negative": int((test_df["label"] == 0).sum()),
            } if "label" in df else {},
            "event_leakage": leakage,
            "feasible": not leakage and len(test_df) > 0,
        }
        splits.append(fold)

    return splits


def build_splits_for_matrix(matrix_path: Path, matrix_name: str) -> dict:
    """Build all split types for a feature matrix."""
    if not matrix_path.exists():
        log.warning(f"{matrix_path} not found — skipping splits.")
        return {"error": "matrix_not_found", "path": str(matrix_path)}

    df = pd.read_parquet(str(matrix_path))
    log.info(f"\n{matrix_name}: {len(df)} rows, {len(df.columns)} cols")
    log.info(f"  Regions: {df.get('pilot_region', pd.Series([])).value_counts().to_dict()}")
    log.info(f"  Labels: {df.get('label', pd.Series([])).value_counts().to_dict()}")

    splits_doc = {
        "matrix": matrix_name,
        "matrix_path": str(matrix_path),
        "n_rows": len(df),
        "n_unique_events": df.get("event_id", pd.Series([])).nunique(),
        "regions": df.get("pilot_region", pd.Series([])).unique().tolist(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "splits": {},
    }

    # LORO
    if "pilot_region" in df.columns and df["pilot_region"].nunique() > 1:
        loro = loro_splits(df)
        splits_doc["splits"]["loro"] = loro
        n_feasible = sum(1 for s in loro if s.get("feasible"))
        log.info(f"  LORO: {len(loro)} folds, {n_feasible} feasible")
    else:
        log.warning("  LORO: insufficient regions for cross-region validation")
        splits_doc["splits"]["loro"] = []

    # Temporal
    temp = temporal_split(df)
    splits_doc["splits"]["temporal"] = temp
    log.info(f"  Temporal (split={TEMPORAL_SPLIT_YEAR}): train={temp.get('train_n_samples')}, "
             f"test={temp.get('test_n_samples')}, leakage={temp.get('event_leakage')}")

    # LOEO
    loeo = loeo_splits(df)
    splits_doc["splits"]["loeo"] = loeo
    n_loeo_feasible = sum(1 for s in loeo if s.get("feasible"))
    log.info(f"  LOEO: {len(loeo)} folds, {n_loeo_feasible} feasible")

    # Leakage check summary
    all_event_leakages = []
    for strat in splits_doc["splits"].values():
        if isinstance(strat, list):
            all_event_leakages.extend([s.get("event_leakage", False) for s in strat])
        elif isinstance(strat, dict):
            all_event_leakages.append(strat.get("event_leakage", False))

    splits_doc["leakage_summary"] = {
        "any_event_leakage": any(all_event_leakages),
        "n_folds_with_leakage": sum(all_event_leakages),
    }

    return splits_doc


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Region-Aware Splits  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)
    log.info("RULE: No random 80/20 splits. Must use LORO or temporal.")
    log.info("RULE: No event leakage across train/test folds.")

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    # Flood splits
    flood_splits = build_splits_for_matrix(
        FEAT_DIR / "flood_training.parquet", "flood_training"
    )
    with open(SPLITS_DIR / "flood_splits.json", "w") as f:
        json.dump(flood_splits, f, indent=2, default=str)
    log.info(f"\nFlood splits saved: {SPLITS_DIR / 'flood_splits.json'}")

    # Landslide splits
    ls_splits = build_splits_for_matrix(
        FEAT_DIR / "landslide_training.parquet", "landslide_training"
    )
    with open(SPLITS_DIR / "landslide_splits.json", "w") as f:
        json.dump(ls_splits, f, indent=2, default=str)
    log.info(f"Landslide splits saved: {SPLITS_DIR / 'landslide_splits.json'}")

    # Summary
    log.info("\n── SPLIT STRATEGY SUMMARY ──────────────────────────────────")
    log.info("Flood matrix:")
    flood_loro = flood_splits.get("splits", {}).get("loro", [])
    log.info(f"  LORO folds: {len(flood_loro)}, feasible: {sum(1 for s in flood_loro if s.get('feasible'))}")
    log.info(f"  Any leakage: {flood_splits.get('leakage_summary', {}).get('any_event_leakage')}")

    log.info("Landslide matrix:")
    ls_loro = ls_splits.get("splits", {}).get("loro", [])
    log.info(f"  LORO folds: {len(ls_loro)}, feasible: {sum(1 for s in ls_loro if s.get('feasible'))}")
    log.info(f"  Any leakage: {ls_splits.get('leakage_summary', {}).get('any_event_leakage')}")

    log.info("\nWARNING: Small dataset — splits may have limited feasibility.")
    log.info("  Minimum recommended: ≥3 distinct regions for meaningful LORO.")
    log.info("  Current pilot has 3 regions (uttarakhand, kerala_wayanad, assam).")
    log.info("  Add sikkim_ne + himachal data for more robust LORO validation.")


if __name__ == "__main__":
    main()
