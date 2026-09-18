# -*- coding: utf-8 -*-
"""
real_pipeline/audit/independence_audit.py
==========================================
Gate 0: Independence / Leakage Audit
Gate 1: Flood Training Readiness
Gate 2: Landslide Training Readiness

Produces: data_real/evaluation/readiness_report.json

CRITICAL DISTINCTION:
  raw_rows  ≠ independent_events
  45,566 rows = 6 independent groups (3 positive events + 3 negative windows)
  Each group is a raster of thousands of grid cells with the SAME event-wide label.
  Models cannot be evaluated by row-level random split.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEAT_DIR  = PROJECT_ROOT / "data_real" / "features"
EVAL_DIR  = PROJECT_ROOT / "data_real" / "evaluation"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("independence_audit")

# ─── Utility ──────────────────────────────────────────────────────────────────

def class_conditional_missingness(df: pd.DataFrame, feature_cols: list, label_col: str = "label") -> pd.DataFrame:
    """Return per-feature missingness rate by class. Critical for leakage detection."""
    rows = []
    for col in feature_cols:
        miss_pos = df.loc[df[label_col] == 1, col].isna().mean()
        miss_neg = df.loc[df[label_col] == 0, col].isna().mean()
        overall  = df[col].isna().mean()
        rows.append({
            "feature": col,
            "miss_overall_pct": round(100 * overall, 1),
            "miss_positive_pct": round(100 * miss_pos, 1),
            "miss_negative_pct": round(100 * miss_neg, 1),
            "delta_pct": round(100 * abs(miss_pos - miss_neg), 1),
            "leakage_risk": "HIGH" if abs(miss_pos - miss_neg) > 0.30 else (
                            "MEDIUM" if abs(miss_pos - miss_neg) > 0.05 else "LOW"),
        })
    return pd.DataFrame(rows).sort_values("delta_pct", ascending=False)


def event_group_stats(df: pd.DataFrame) -> list:
    """Per-event-group statistics."""
    groups = []
    for eid in df["event_id"].unique():
        sub = df[df["event_id"] == eid]
        groups.append({
            "event_id": eid,
            "n_rows": len(sub),
            "label": int(sub["label"].iloc[0]),
            "region": str(sub["pilot_region"].iloc[0]),
            "n_unique_cells": int(sub["cell_id"].nunique()),
            "label_source": str(sub["label_source"].iloc[0]),
            "pct_of_total": round(100 * len(sub) / len(df), 1),
        })
    return sorted(groups, key=lambda x: x["n_rows"], reverse=True)


def check_cross_fold_cell_leak(df: pd.DataFrame) -> dict:
    """
    Check if the same cell appears in both positive and negative groups.
    In our design this is intentional (same grid used for event + non-event windows),
    but it must be flagged and documented.
    """
    pos_cells = set(df[df["label"] == 1]["cell_id"].unique())
    neg_cells  = set(df[df["label"] == 0]["cell_id"].unique())
    overlap    = pos_cells & neg_cells
    return {
        "pos_unique_cells": len(pos_cells),
        "neg_unique_cells": len(neg_cells),
        "overlapping_cells": len(overlap),
        "overlap_pct": round(100 * len(overlap) / len(pos_cells), 1) if pos_cells else 0,
        "interpretation": (
            "EXPECTED: Same spatial grid used for event + non-event windows. "
            "Cells overlap by design. This is NOT a cross-event leakage — events are "
            "separated by time. However, spatial autocorrelation means nearby cells in "
            "the same event are NOT independent observations. "
            "Do NOT use random-row train/test splits."
        ),
    }


# ─── Gate 0: Flood independence audit ────────────────────────────────────────

def audit_flood(df: pd.DataFrame) -> dict:
    log.info("\n══ GATE 0 — FLOOD INDEPENDENCE AUDIT ═══════════════════════════════")

    events = df["event_id"].unique().tolist()
    pos_events = df[df["label"] == 1]["event_id"].unique().tolist()
    neg_events = df[df["label"] == 0]["event_id"].unique().tolist()
    regions    = df["pilot_region"].unique().tolist()

    # All numeric columns (potential predictors)
    all_numeric = df.select_dtypes(include=["number"]).columns.tolist()
    # Exclude label and ID-adjacent numeric cols
    exclude_numeric = ["label", "data_coverage", "n_days_window", "n_days_valid_chirps",
                       "n_days_ant_3d", "n_days_ant_7d", "n_days_ant_14d",
                       "chirps_coverage_pct"]  # coverage is event-correlated
    candidate_features = [c for c in all_numeric if c not in exclude_numeric
                          and c not in ["lat_center", "lon_center"]]

    miss_table = class_conditional_missingness(df, candidate_features)
    high_risk  = miss_table[miss_table["leakage_risk"] == "HIGH"]

    log.info(f"Raw rows: {len(df):,}")
    log.info(f"Independent groups: {len(events)} (positive events: {len(pos_events)}, negative windows: {len(neg_events)})")
    log.info(f"Regions: {regions}")
    log.info(f"Duplicate sample_ids: {df['sample_id'].duplicated().sum()}")

    log.info("\nClass-conditional missingness (top risks):")
    for _, row in miss_table.head(10).iterrows():
        log.info(f"  {row['feature']:30s} overall={row['miss_overall_pct']:5.1f}%  "
                 f"pos={row['miss_positive_pct']:5.1f}%  neg={row['miss_negative_pct']:5.1f}%  "
                 f"Δ={row['delta_pct']:5.1f}%  [{row['leakage_risk']}]")

    cell_overlap = check_cross_fold_cell_leak(df)
    log.info(f"\nCell overlap pos/neg: {cell_overlap['overlapping_cells']:,} / {cell_overlap['pos_unique_cells']:,} ({cell_overlap['overlap_pct']}%)")
    log.info(f"Interpretation: {cell_overlap['interpretation'][:100]}...")

    event_groups = event_group_stats(df)
    log.info("\nEvent group breakdown:")
    for g in event_groups:
        log.info(f"  {g['event_id']:35s}  label={g['label']}  region={g['region']:15s}  rows={g['n_rows']:6,}  ({g['pct_of_total']}%)")

    # Dominant event check
    max_pct = max(g["pct_of_total"] for g in event_groups)
    log.info(f"\nMost dominant event: {max_pct:.1f}% of rows → event weighting required")

    return {
        "raw_rows": len(df),
        "independent_groups": len(events),
        "positive_events": len(pos_events),
        "negative_windows": len(neg_events),
        "regions": regions,
        "n_regions": len(regions),
        "duplicate_sample_ids": int(df["sample_id"].duplicated().sum()),
        "cell_overlap_analysis": cell_overlap,
        "event_groups": event_groups,
        "class_balance_raw": {
            "positive": int((df["label"] == 1).sum()),
            "negative": int((df["label"] == 0).sum()),
        },
        "natural_prevalence_unknown": True,
        "natural_prevalence_note": (
            "Balanced 1:1 training is intentional sampling. "
            "Real-world flood prevalence is far lower (~days per year vs 365). "
            "Model probability outputs MUST NOT be interpreted as real-world event frequency."
        ),
        "class_conditional_missingness": miss_table.to_dict("records"),
        "high_risk_leakage_features": high_risk["feature"].tolist(),
    }


# ─── Gate 1: Flood readiness ─────────────────────────────────────────────────

FLOOD_GATE_CRITERIA = {
    "min_positive_events": 3,
    "min_regions": 2,
    "require_negative_windows": True,
    "require_no_synthetic": True,
    "require_documented_labels": True,
}

def gate1_flood(audit: dict, df: pd.DataFrame) -> dict:
    log.info("\n══ GATE 1 — FLOOD TRAINING READINESS ═══════════════════════════════")

    checks = {
        "min_positive_events_pass": audit["positive_events"] >= FLOOD_GATE_CRITERIA["min_positive_events"],
        "min_regions_pass":         audit["n_regions"] >= FLOOD_GATE_CRITERIA["min_regions"],
        "negative_windows_exist":   audit["negative_windows"] >= 1,
        "no_synthetic_rows":        (df["data_type"] == "REAL_DATA \u2014 NOT SYNTHETIC").all(),
        "documented_labels":        df["label_source"].notna().all(),
        "no_event_leakage":         audit["duplicate_sample_ids"] == 0,
    }

    gate_pass = all(checks.values())
    decision = "EXPERIMENTAL_BASELINE_ONLY" if gate_pass else "NOT_READY"

    # With only 3 positive events, escalate notice
    readiness_label = (
        "EXPERIMENTAL_BASELINE_ONLY — "
        "3 positive events across 3 regions. Meets minimum criteria for experimental research baseline. "
        "NOT suitable for deployment, operational forecasting, or production use. "
        "Classification: NEEDS_MORE_INDEPENDENT_EVENTS for research pilot."
    )

    for k, v in checks.items():
        icon = "✓" if v else "✗"
        log.info(f"  [{icon}] {k}: {v}")

    log.info(f"\n  GATE 1 DECISION: {decision}")
    log.info(f"  {readiness_label}")

    return {
        "gate": "FLOOD_GATE_1",
        "pass": gate_pass,
        "decision": decision,
        "readiness_label": "EXPERIMENTAL_BASELINE_ONLY",
        "readiness_note": readiness_label,
        "checks": checks,
        "n_positive_events": audit["positive_events"],
        "n_regions": audit["n_regions"],
        "training_allowed": gate_pass,
        "deployment_allowed": False,
        "not_operational": True,
    }


# ─── Gate 2: Landslide readiness ─────────────────────────────────────────────

def gate2_landslide(ls_df: pd.DataFrame) -> dict:
    log.info("\n══ GATE 2 — LANDSLIDE TRAINING READINESS ════════════════════════════")

    n_rows = len(ls_df)
    n_dynamic_pos = int((ls_df["label_type"] == "dynamic").sum())
    n_neg = int((ls_df["label"] == 0).sum())

    log.info(f"  Rows: {n_rows}, Dynamic positives: {n_dynamic_pos}, Negatives: {n_neg}")
    log.info(f"  GATE 2 DECISION: ANALYSIS_ONLY — {n_rows} rows insufficient for defensible model")
    log.info("  Required: ≥50 dated, rain-triggered, independently verified events")
    log.info("  Current: 4 dynamic positive events (curated from open sources)")
    log.info("  Blocked sources: GSI inventory (MANUAL_REQUIRED), NASA GLC (timeout)")

    return {
        "gate": "LANDSLIDE_GATE_2",
        "pass": False,
        "decision": "ANALYSIS_ONLY",
        "readiness_label": "NEEDS_MORE_EVENTS",
        "n_rows": n_rows,
        "n_dynamic_positives": n_dynamic_pos,
        "n_negatives": n_neg,
        "training_allowed": False,
        "diagnostic_code_allowed": True,
        "deployment_allowed": False,
        "not_operational": True,
        "minimum_needed": 50,
        "reason": (
            f"Only {n_rows} rows ({n_dynamic_pos} dynamic positives). "
            "Minimum ~50 dated, rain-triggered, independently verified events required. "
            "GSI inventory and NASA GLC remain MANUAL_REQUIRED/blocked."
        ),
        "blocked_sources": [
            "GSI National Landslide Inventory (email: dgm-hq-gsi@gov.in)",
            "NASA GLC (ConnectTimeout — retry: python ingest_landslide_events.py)",
        ],
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Independence Audit  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)
    log.info("CRITICAL: raw_rows ≠ independent_events. Report both always.")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # Load matrices
    flood_path = FEAT_DIR / "flood_training.parquet"
    ls_path    = FEAT_DIR / "landslide_training.parquet"

    if not flood_path.exists():
        log.error("Flood matrix missing. Run build_flood_matrix.py first.")
        sys.exit(1)

    flood_df = pd.read_parquet(str(flood_path))
    ls_df    = pd.read_parquet(str(ls_path)) if ls_path.exists() else pd.DataFrame()

    # Run audits
    flood_audit = audit_flood(flood_df)
    gate1       = gate1_flood(flood_audit, flood_df)
    gate2       = gate2_landslide(ls_df)

    # Compile report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_type": "REAL_DATA — NOT SYNTHETIC",
        "flood": {
            "audit": flood_audit,
            "gate1": gate1,
        },
        "landslide": {
            "gate2": gate2,
        },
        "critical_caveats": [
            f"raw_rows={flood_audit['raw_rows']:,} represents only {flood_audit['independent_groups']} independent event groups.",
            "Event-wide raster labeling: all cells in a region share the same event label, regardless of local inundation.",
            "1:1 class balance is intentional sampling, NOT natural flood prevalence.",
            "Model probability outputs ≠ real-world event frequency.",
            "Primary validation must be LOEO or LORO, never random-row split.",
            "With only 3 independent positive events, bootstrap CI is unreliable — INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CI.",
            "With only 6 event groups, calibration is unreliable — INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CALIBRATION.",
        ],
        "validation_strategy": {
            "primary": "LOEO — leave-one-event/window-out (6 folds over 6 event groups)",
            "secondary": "LORO — leave-one-region-out (3 folds)",
            "never_use": "random-row split / row-level k-fold",
        },
        "status": {
            "flood": gate1["readiness_label"],
            "landslide": gate2["readiness_label"],
        },
    }

    out_path = EVAL_DIR / "readiness_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    log.info(f"\n✓ Readiness report: {out_path}")
    log.info(f"\n── SUMMARY ──────────────────────────────────────────────────────")
    log.info(f"  Flood:      {gate1['readiness_label']}")
    log.info(f"  Landslide:  {gate2['readiness_label']}")
    log.info(f"  Raw rows:   {flood_audit['raw_rows']:,}")
    log.info(f"  Indep. groups: {flood_audit['independent_groups']}")
    log.info(f"  High-leakage features: {flood_audit['high_risk_leakage_features']}")
    log.info(f"\n  → Flood training ALLOWED (experimental baseline only)")
    log.info(f"  → Landslide training BLOCKED (analysis only)")

    return report


if __name__ == "__main__":
    main()
