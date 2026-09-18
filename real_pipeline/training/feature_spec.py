# -*- coding: utf-8 -*-
"""
real_pipeline/training/feature_spec.py
=======================================
Canonical feature specification for ResQ Shield real-data models.

ARCHITECTURE:
  core_common_features:
    Features with adequate coverage across ALL events and regions.
    Antecedent features included ONLY after verifying class-parity.

  terrain_enriched_subset:
    Features available only for Uttarakhand (1 GLO-30 tile).
    Exploratory only — cannot train/evaluate on terrain features for other regions.

BLACKLIST (never use as predictors):
  - Identity columns: cell_id, sample_id, event_id
  - Group columns: pilot_region (leaks region identity in LORO)
  - Label metadata: label_source, source_quality, label_confidence, label_type, event_type
  - Provenance: rain_source, river_source, soil_source, terrain_source, terrain_source_col, data_type
  - Coverage flags: data_coverage, terrain_available, twi_note
  - Window metadata: window_start, window_end, n_days_window
  - Counts of valid data: n_days_valid_chirps, n_days_ant_3d, n_days_ant_7d, n_days_ant_14d
    (these directly encode whether antecedent was downloaded → class-correlated)
  - Spatial ID-proxies in LORO context: lat_center, lon_center

ANTECEDENT PARITY RULE:
  ant_3d_mm / ant_7d_mm / ant_14d_mm are ONLY included if:
  - missingness delta between positive and negative class < 5%
  - Verified by class_conditional_missingness() in independence_audit.py
  If parity cannot be verified: antecedent features are DROPPED from core model.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

# ── Feature blacklist ─────────────────────────────────────────────────────────
FEATURE_BLACKLIST = [
    # Identity / IDs
    "cell_id", "sample_id", "event_id",
    # Group / regional identity (leaks in LORO)
    "pilot_region",
    # Label metadata (obviously leaky)
    "label", "label_source", "source_quality", "label_confidence",
    "label_type", "event_type",
    # Provenance / source fields
    "rain_source", "river_source", "soil_source",
    "terrain_source", "terrain_source_col", "data_type",
    # Coverage flags (class-correlated by construction)
    "data_coverage", "terrain_available", "twi_note",
    # Window metadata
    "window_start", "window_end",
    # Count of valid days (encodes whether data was downloaded → leaks class)
    "n_days_window", "n_days_valid_chirps",
    "n_days_ant_3d", "n_days_ant_7d", "n_days_ant_14d",
]

# ── Spatial features ──────────────────────────────────────────────────────────
# lat/lon encode region identity → include only for non-LORO models
SPATIAL_FEATURES = ["lat_center", "lon_center"]

# ── Rainfall features (core, event-window) ───────────────────────────────────
RAINFALL_EVENT_FEATURES = [
    "rain_event_sum_mm",    # total rainfall during event/reference window
    "rain_event_mean_mm",   # daily mean
    "rain_event_max_mm",    # daily maximum
    "rain_event_p90_mm",    # 90th percentile daily
]

# ── Antecedent rainfall features ─────────────────────────────────────────────
# ONLY included after antecedent parity verification (class-conditional missingness < 5%)
ANTECEDENT_FEATURES = [
    "ant_3d_mm",   # 3-day antecedent sum
    "ant_7d_mm",   # 7-day antecedent sum
    "ant_14d_mm",  # 14-day antecedent sum
]

# ── Structural distance feature ───────────────────────────────────────────────
STRUCTURAL_FEATURES = [
    "nearest_cwc_dist_km",  # distance to nearest gauged river (structural, not event-specific)
]

# ── Terrain features (enriched subset only) ───────────────────────────────────
TERRAIN_FEATURES = [
    "elev_mean_m",
    "slope_mean_deg",
    "twi_proxy_simplified",
    # NOT included: elev_max/min/std, slope_max/std (highly correlated with above)
    # NOT included: aspect_mean_deg (weak signal for flood)
    # NOT included: pct_slope_gt_30/45 (>98% missing, only 441 cells)
]

# ── Data quality indicator (optional) ─────────────────────────────────────────
# chirps_coverage_pct: fraction of valid CHIRPS pixels in event window
# NOT class-correlated after antecedent parity fix, OK to include
QUALITY_FEATURES = [
    "chirps_coverage_pct",
]


@dataclass
class FeatureSet:
    name: str
    features: List[str]
    includes_spatial: bool = False
    includes_antecedent: bool = False
    includes_terrain: bool = False
    coverage_note: str = ""
    for_loro: bool = True  # exclude spatial features for LORO


def get_core_common_features(
    antecedent_ok: bool = True,
    include_spatial_in_nonloro: bool = False,
) -> FeatureSet:
    """
    Core feature set valid for ALL events and regions.
    Antecedent features conditionally included based on parity check.
    """
    feats = list(RAINFALL_EVENT_FEATURES) + list(QUALITY_FEATURES) + list(STRUCTURAL_FEATURES)

    if antecedent_ok:
        feats = feats + list(ANTECEDENT_FEATURES)
        note  = "Antecedent features included (class-conditional missingness parity verified: delta<5%)."
    else:
        note = (
            "Antecedent features EXCLUDED — class-conditional missingness imbalanced. "
            "Positive windows have antecedent data; negative windows do not. "
            "Including would trivially leak the label."
        )

    return FeatureSet(
        name="core_common",
        features=feats,
        includes_spatial=include_spatial_in_nonloro,
        includes_antecedent=antecedent_ok,
        includes_terrain=False,
        coverage_note=note,
        for_loro=True,
    )


def get_terrain_enriched_features(antecedent_ok: bool = True) -> FeatureSet:
    """
    Enriched feature set with terrain — valid only for Uttarakhand subset.
    ~7.9% of cells have terrain data. Use only where terrain_available == True.
    EXPLORATORY ONLY — cannot be primary evaluation.
    """
    core = get_core_common_features(antecedent_ok)
    feats = core.features + list(TERRAIN_FEATURES)
    return FeatureSet(
        name="terrain_enriched",
        features=feats,
        includes_spatial=False,
        includes_antecedent=antecedent_ok,
        includes_terrain=True,
        coverage_note=(
            "Terrain features from 1 GLO-30 tile (N29E078): 441/5,600 UK cells (7.9% of UK, ~1% of all). "
            "EXPLORATORY ONLY. Cannot evaluate across all regions."
        ),
        for_loro=False,
    )


def assert_no_blacklist_in_features(features: list, context: str = "") -> None:
    """Assert no blacklisted features are in the predictor list."""
    bad = [f for f in features if f in FEATURE_BLACKLIST]
    if bad:
        raise ValueError(f"LEAKAGE: Blacklisted features in predictor list {context}: {bad}")


def print_feature_spec(feature_set: FeatureSet) -> None:
    print(f"\n{'='*60}")
    print(f"Feature set: {feature_set.name}")
    print(f"  n_features: {len(feature_set.features)}")
    print(f"  includes_spatial:    {feature_set.includes_spatial}")
    print(f"  includes_antecedent: {feature_set.includes_antecedent}")
    print(f"  includes_terrain:    {feature_set.includes_terrain}")
    print(f"  for_loro:            {feature_set.for_loro}")
    note_safe = feature_set.coverage_note[:120].encode("ascii", "replace").decode()
    print(f"  note: {note_safe}")

    print(f"  features: {feature_set.features}")
    print(f"{'='*60}")
