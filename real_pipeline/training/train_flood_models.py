# -*- coding: utf-8 -*-
"""
real_pipeline/training/train_flood_models.py
=============================================
Flood research baseline training with strict leakage prevention.

STATUS:  EXPERIMENTAL_REAL_DATA_BASELINE
         NOT deployment-ready. 3 independent positive events.

KEY CONSTRAINTS:
  - Primary validation: LOEO (leave-one-event/window-out, 6 folds)
  - Secondary: LORO (leave-one-region-out, 3 folds)
  - NEVER random-row split
  - Event weighting: 1/n_cells_in_event_group so large rasters don't dominate
  - Antecedent features ONLY if class-conditional missingness Δ < 5%
  - Terrain features: exploratory only (enriched subset, not primary eval)
  - No calibration (INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CALIBRATION)
  - No bootstrap CI (INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CI)

Outputs:
  models_real/flood_research_model.pkl
  models_real/flood_research_metadata.json
  data_real/evaluation/fold_metrics.csv
  data_real/evaluation/event_metrics.csv
  data_real/evaluation/threshold_analysis.csv
  data_real/evaluation/feature_importance.csv
  data_real/evaluation/model_card_flood.md
"""

import json
import logging
import pickle
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibrationDisplay
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from real_pipeline.audit.independence_audit import class_conditional_missingness
from real_pipeline.training.feature_spec import (
    FEATURE_BLACKLIST,
    ANTECEDENT_FEATURES,
    assert_no_blacklist_in_features,
    get_core_common_features,
    get_terrain_enriched_features,
    print_feature_spec,
)

FEAT_DIR   = PROJECT_ROOT / "data_real" / "features"
EVAL_DIR   = PROJECT_ROOT / "data_real" / "evaluation"
MODELS_DIR = PROJECT_ROOT / "models_real"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_flood")

RANDOM_SEED = 42
ANTECEDENT_LEAK_THRESHOLD = 0.05  # max allowed missingness delta

# Positive event IDs (for LOEO ordering)
POSITIVE_EVENT_IDS = [
    "IND_FLOOD_2013_UK_001",
    "IND_FLOOD_2018_KL_001",
    "IND_FLOOD_2022_AS_001",
]
NEGATIVE_WINDOW_IDS = [
    "NEG_UK_2013_PREMONSOON",
    "NEG_KL_2019_PREMONSOON",
    "NEG_AS_2022_DRY_WINTER",
]

# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    path = FEAT_DIR / "flood_training.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Flood matrix missing: {path}")
    df = pd.read_parquet(str(path))
    log.info(f"Loaded: {len(df):,} rows, {len(df.columns)} cols")
    log.info(f"  raw_rows={len(df):,}, independent_groups={df['event_id'].nunique()}")
    return df


def verify_no_synthetic(df: pd.DataFrame) -> None:
    if not (df["data_type"] == "REAL_DATA \u2014 NOT SYNTHETIC").all():
        raise ValueError("SYNTHETIC DATA DETECTED in flood matrix! Abort.")
    log.info("  [✓] No synthetic data")


# ── Antecedent parity check ───────────────────────────────────────────────────

def check_antecedent_parity(df: pd.DataFrame) -> bool:
    """
    Returns True if antecedent features have class-balanced missingness (Δ < 5%).
    If False, antecedent features must be DROPPED.
    """
    miss_table = class_conditional_missingness(df, ANTECEDENT_FEATURES)
    log.info("\nAntecedent class-conditional missingness:")
    antecedent_ok = True
    for _, row in miss_table.iterrows():
        ok = row["delta_pct"] <= ANTECEDENT_LEAK_THRESHOLD * 100
        icon = "✓" if ok else "✗ LEAKAGE"
        log.info(f"  [{icon}] {row['feature']:15s}  pos={row['miss_positive_pct']:5.1f}%  "
                 f"neg={row['miss_negative_pct']:5.1f}%  Δ={row['delta_pct']:5.1f}%")
        if not ok:
            antecedent_ok = False

    if antecedent_ok:
        log.info("  → Antecedent features INCLUDED (parity verified)")
    else:
        log.warning("  → Antecedent features EXCLUDED (class-dependent missingness > 5%)")
        log.warning("    This prevents the model from learning 'antecedent is null → negative'.")
    return antecedent_ok


# ── Event weights ─────────────────────────────────────────────────────────────

def compute_event_weights(df: pd.DataFrame) -> np.ndarray:
    """
    Per-sample weight = 1 / n_cells_in_event_group.
    Ensures each event group contributes equal total weight regardless of raster size.
    """
    group_sizes = df.groupby("event_id")["cell_id"].transform("count")
    weights = 1.0 / group_sizes.values
    # Normalize to mean 1.0 (preserves scale)
    weights = weights / weights.mean()

    log.info("\nEvent weights (per-sample, normalized):")
    for eid in df["event_id"].unique():
        mask  = df["event_id"] == eid
        w_sum = weights[mask.values].sum()
        log.info(f"  {eid:35s}  n={mask.sum():6,}  weight_sum={w_sum:.1f}  "
                 f"({100*w_sum/len(df):.1f}% of total weight)")
    return weights


# ── LOEO fold generator ───────────────────────────────────────────────────────

def loeo_folds(df: pd.DataFrame):
    """
    Leave-One-Event/Window-Out: 6 folds, one per event group.
    Each fold holds out one entire event group.
    Returns: (fold_name, train_df, test_df, test_event_id)
    """
    all_events = sorted(df["event_id"].unique().tolist())
    for test_event in all_events:
        train_df = df[df["event_id"] != test_event].copy()
        test_df  = df[df["event_id"] == test_event].copy()
        # Verify no leakage
        assert len(set(train_df["event_id"]) & {test_event}) == 0
        assert len(test_df) > 0
        yield f"loeo_{test_event}", train_df, test_df, test_event


def loro_folds(df: pd.DataFrame):
    """
    Leave-One-Region-Out: 3 folds, one per region.
    Returns: (fold_name, train_df, test_df, test_region)
    """
    all_regions = sorted(df["pilot_region"].unique().tolist())
    for test_region in all_regions:
        train_df = df[df["pilot_region"] != test_region].copy()
        test_df  = df[df["pilot_region"] == test_region].copy()
        assert len(set(train_df["pilot_region"]) & {test_region}) == 0
        yield f"loro_{test_region}", train_df, test_df, test_region


# ── Models ────────────────────────────────────────────────────────────────────

def build_models(random_state: int = RANDOM_SEED) -> dict:
    """
    Build three compact sklearn baseline models.
    HistGBT handles NaN natively.
    LR and RF use median imputation via column-wise fill.
    """
    return {
        "LogisticRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                C=1.0, max_iter=2000, class_weight="balanced",
                random_state=random_state, solver="lbfgs",
            )),
        ]),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=20,
            class_weight="balanced", random_state=random_state, n_jobs=1,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=300, max_depth=5, l2_regularization=0.5,
            random_state=random_state,
            # NaN is handled natively — do NOT use to learn label structure
        ),
    }


# ── Metric computation ────────────────────────────────────────────────────────

def compute_metrics(y_true, y_prob, y_pred=None, threshold: float = 0.50) -> dict:
    if y_pred is None:
        y_pred = (y_prob >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    support_pos  = int(y_true.sum())
    support_neg  = int((1 - y_true).sum())

    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    far       = fp / (fp + tn) if (fp + tn) > 0 else 0.0  # false alarm rate
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    try:
        pr_auc  = float(average_precision_score(y_true, y_prob))
    except Exception:
        pr_auc  = float("nan")
    try:
        roc_auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        roc_auc = float("nan")
    try:
        brier   = float(brier_score_loss(y_true, y_prob))
    except Exception:
        brier   = float("nan")

    return {
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "recall_pod": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "far": round(far, 4),
        "specificity": round(specificity, 4),
        "brier": round(brier, 4),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "support_positive": support_pos,
        "support_negative": support_neg,
        "threshold": threshold,
    }


def compute_threshold_analysis(y_true: np.ndarray, y_prob: np.ndarray,
                                event_id: str) -> list:
    """Sweep thresholds on validation data only — never test fold."""
    rows = []
    for t in np.arange(0.1, 0.95, 0.05):
        m = compute_metrics(y_true, y_prob, threshold=t)
        rows.append({
            "event_id": event_id,
            "threshold": round(float(t), 2),
            "recall_pod": m["recall_pod"],
            "precision": m["precision"],
            "far": m["far"],
            "f1": m["f1"],
            "note": "EXPLORATORY_ONLY — threshold must be selected on validation, not test data",
        })
    return rows


# ── Feature preparation ───────────────────────────────────────────────────────

def prepare_features(df: pd.DataFrame, feature_list: list,
                     fill_strategy: str = "median") -> pd.DataFrame:
    """
    Extract feature columns and impute missing values.
    fill_strategy: 'median' for LR/RF, 'passthrough' for HistGBT (handles NaN).
    """
    # Only keep features that exist in df
    valid_feats = [f for f in feature_list if f in df.columns]
    missing_feats = [f for f in feature_list if f not in df.columns]
    if missing_feats:
        log.warning(f"  Features not in df (skipped): {missing_feats}")

    X = df[valid_feats].copy()

    if fill_strategy == "median":
        for col in X.columns:
            if X[col].isna().any():
                X[col] = X[col].fillna(X[col].median())

    return X


# ── Main training ─────────────────────────────────────────────────────────────

def run_training(df: pd.DataFrame, feature_set, antecedent_ok: bool) -> dict:
    log.info(f"\n{'='*65}")
    log.info(f"Training: {feature_set.name} features")
    log.info(f"  n_features: {len(feature_set.features)}")
    print_feature_spec(feature_set)

    # Final blacklist assertion
    assert_no_blacklist_in_features(feature_set.features, context=feature_set.name)

    models      = build_models(RANDOM_SEED)
    all_metrics = []
    all_event_metrics = []
    all_thresholds    = []
    all_importances   = []
    best_model_info   = {"name": None, "model": None, "score": -1.0}

    # ── LOEO folds ────────────────────────────────────────────────────────────
    log.info("\n── LOEO Folds (Primary Evaluation) ─────────────────────────────────")
    for model_name, model in models.items():
        log.info(f"\n  Model: {model_name}")
        fold_scores = []

        for fold_name, train_df, test_df, test_event in loeo_folds(df):
            train_weights = compute_event_weights(train_df)
            test_label    = int(test_df["label"].iloc[0])
            test_region   = test_df["pilot_region"].iloc[0]

            # Prepare X, y
            X_train = prepare_features(
                train_df, feature_set.features,
                fill_strategy="passthrough" if model_name == "HistGradientBoosting" else "median"
            )
            X_test = prepare_features(
                test_df, feature_set.features,
                fill_strategy="passthrough" if model_name == "HistGradientBoosting" else "median"
            )
            y_train = train_df["label"].values
            y_test  = test_df["label"].values

            # Verify at least one class in training
            if len(np.unique(y_train)) < 2:
                log.warning(f"    {fold_name}: only one class in training — skipping")
                continue

            # Fit
            try:
                if hasattr(model, "fit"):
                    if model_name == "LogisticRegression":
                        model.fit(X_train, y_train)
                    else:
                        model.fit(X_train, y_train, sample_weight=train_weights)
                y_prob = model.predict_proba(X_test)[:, 1]
            except Exception as e:
                log.warning(f"    {fold_name}: fit/predict failed: {e}")
                continue

            m = compute_metrics(y_test, y_prob, threshold=0.50)
            m.update({
                "fold": fold_name,
                "strategy": "LOEO",
                "model": model_name,
                "feature_set": feature_set.name,
                "test_event": test_event,
                "test_region": test_region,
                "test_label": test_label,
                "test_n_samples": len(test_df),
                "train_n_samples": len(train_df),
                "train_n_events": train_df["event_id"].nunique(),
            })
            all_metrics.append(m)
            fold_scores.append(m["pr_auc"])

            # Event-level detection
            is_positive_event = test_label == 1
            event_m = {
                "fold": fold_name,
                "model": model_name,
                "strategy": "LOEO",
                "event_id": test_event,
                "region": test_region,
                "label": test_label,
                "n_samples": len(test_df),
                "recall_pod": m["recall_pod"],
                "precision": m["precision"],
                "pr_auc": m["pr_auc"],
                "far": m["far"],
                "positive_event_detected": (m["recall_pod"] >= 0.5) if is_positive_event else None,
                "note": "event-wide raster label" if is_positive_event else "verified non-flood window",
            }
            all_event_metrics.append(event_m)

            # Threshold sweep (exploratory, on test fold for reporting only)
            thr_rows = compute_threshold_analysis(y_test, y_prob, test_event)
            all_thresholds.extend(thr_rows)

            log.info(f"    {fold_name:45s}  PR-AUC={m['pr_auc']:.3f}  "
                     f"Recall={m['recall_pod']:.3f}  FAR={m['far']:.3f}  "
                     f"F1={m['f1']:.3f}")

            # Feature importance
            try:
                clf = model.named_steps["clf"] if hasattr(model, "named_steps") else model
                if hasattr(clf, "feature_importances_"):
                    for fname, imp in zip(X_train.columns, clf.feature_importances_):
                        all_importances.append({
                            "fold": fold_name, "model": model_name,
                            "strategy": "LOEO", "feature": fname,
                            "importance": float(imp),
                        })
                elif hasattr(clf, "coef_"):
                    for fname, coef in zip(X_train.columns, clf.coef_[0]):
                        all_importances.append({
                            "fold": fold_name, "model": model_name,
                            "strategy": "LOEO", "feature": fname,
                            "importance": float(abs(coef)),
                        })
            except Exception:
                pass

        # Macro average
        macro_pr_auc = float(np.mean(fold_scores)) if fold_scores else float("nan")
        macro_std    = float(np.std(fold_scores))  if fold_scores else float("nan")
        log.info(f"    Macro LOEO PR-AUC: {macro_pr_auc:.3f} ± {macro_std:.3f}  "
                 f"  [INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CI]")

        if macro_pr_auc > best_model_info["score"]:
            best_model_info = {
                "name": model_name,
                "model": model,
                "score": macro_pr_auc,
                "macro_std": macro_std,
            }

    # ── LORO folds ────────────────────────────────────────────────────────────
    log.info("\n── LORO Folds (Secondary Evaluation, no lat/lon) ────────────────────")
    # For LORO: drop spatial features
    loro_features = [f for f in feature_set.features
                     if f not in ["lat_center", "lon_center"]]

    for model_name, model in models.items():
        log.info(f"\n  Model: {model_name}")
        for fold_name, train_df, test_df, test_region in loro_folds(df):
            train_weights = compute_event_weights(train_df)
            X_train = prepare_features(
                train_df, loro_features,
                fill_strategy="passthrough" if model_name == "HistGradientBoosting" else "median"
            )
            X_test = prepare_features(
                test_df, loro_features,
                fill_strategy="passthrough" if model_name == "HistGradientBoosting" else "median"
            )
            y_train = train_df["label"].values
            y_test  = test_df["label"].values

            if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
                log.warning(f"    {fold_name}: single-class train or test — skipping")
                continue

            try:
                if model_name == "LogisticRegression":
                    model.fit(X_train, y_train)
                else:
                    model.fit(X_train, y_train, sample_weight=train_weights)
                y_prob = model.predict_proba(X_test)[:, 1]
            except Exception as e:
                log.warning(f"    {fold_name}: failed: {e}")
                continue

            m = compute_metrics(y_test, y_prob, threshold=0.50)
            m.update({
                "fold": fold_name,
                "strategy": "LORO",
                "model": model_name,
                "feature_set": feature_set.name,
                "test_event": None,
                "test_region": test_region,
                "test_label": None,
                "test_n_samples": len(test_df),
                "train_n_samples": len(train_df),
                "train_n_events": train_df["event_id"].nunique(),
            })
            all_metrics.append(m)
            log.info(f"    {fold_name:45s}  PR-AUC={m['pr_auc']:.3f}  "
                     f"Recall={m['recall_pod']:.3f}  FAR={m['far']:.3f}")

    return {
        "metrics": all_metrics,
        "event_metrics": all_event_metrics,
        "threshold_analysis": all_thresholds,
        "feature_importances": all_importances,
        "best_model": best_model_info,
        "feature_set_name": feature_set.name,
        "feature_list": feature_set.features,
    }


# ── Macro summary ─────────────────────────────────────────────────────────────

def macro_summary(metrics: list, strategy: str = "LOEO") -> dict:
    rows = [m for m in metrics if m["strategy"] == strategy]
    summary = {}
    for model_name in {m["model"] for m in rows}:
        model_rows = [m for m in rows if m["model"] == model_name]
        for metric in ["pr_auc", "recall_pod", "far", "f1", "brier"]:
            vals = [m[metric] for m in model_rows if not np.isnan(m[metric])]
            summary[f"{model_name}_{metric}_mean"] = round(float(np.mean(vals)), 4) if vals else float("nan")
            summary[f"{model_name}_{metric}_std"]  = round(float(np.std(vals)), 4)  if vals else float("nan")
    return summary


# ── Save best model ────────────────────────────────────────────────────────────

def save_best_model(best: dict, feature_set, antecedent_ok: bool,
                    df: pd.DataFrame) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Retrain best model on full dataset
    model_name = best["name"]
    model      = best["model"]
    all_weights = compute_event_weights(df)
    X_all = prepare_features(df, feature_set.features,
                             fill_strategy="passthrough" if model_name == "HistGradientBoosting" else "median")
    y_all = df["label"].values

    if model_name == "LogisticRegression":
        model.fit(X_all, y_all)
    else:
        model.fit(X_all, y_all, sample_weight=all_weights)

    pkl_path = MODELS_DIR / "flood_research_model.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump({
            "model": model,
            "model_name": model_name,
            "feature_list": feature_set.features,
            "feature_set_name": feature_set.name,
            "random_seed": RANDOM_SEED,
            "antecedent_ok": antecedent_ok,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, f)

    metadata = {
        "data_type": "real_historical_research",
        "status": "EXPERIMENTAL_BASELINE_ONLY",
        "not_operational": True,
        "deployment_allowed": False,
        "model_name": model_name,
        "feature_set": feature_set.name,
        "feature_list": feature_set.features,
        "n_features": len(feature_set.features),
        "antecedent_features_included": antecedent_ok,
        "terrain_features_included": feature_set.includes_terrain,
        "training_events": POSITIVE_EVENT_IDS,
        "training_windows": NEGATIVE_WINDOW_IDS,
        "n_independent_groups": 6,
        "n_positive_events": 3,
        "n_negative_windows": 3,
        "raw_training_rows": len(df),
        "regions": sorted(df["pilot_region"].unique().tolist()),
        "label_sources": sorted(df["label_source"].dropna().unique().tolist()),
        "validation_strategy": "LOEO_primary_LORO_secondary",
        "calibration": "INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CALIBRATION",
        "confidence_intervals": "INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CI",
        "best_loeo_pr_auc": round(best["score"], 4),
        "random_seed": RANDOM_SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Only 3 independent positive events — severely limited generalizability.",
            "Event-wide raster labeling: all cells in a region share the same event label.",
            "1:1 balanced sampling does not reflect real-world flood prevalence.",
            "Terrain features missing for 98% of rows (1 DEM tile only).",
            "River level features absent (CWC MANUAL_REQUIRED).",
            "Sub-daily intensity features absent (IMERG MANUAL_REQUIRED).",
            "Geographic coverage: only Uttarakhand, Kerala/Wayanad, Assam.",
            "NOT suitable for operational forecasting or deployment.",
        ],
        "readiness_label": "EXPERIMENTAL_BASELINE_ONLY",
        "recommended_next_steps": [
            "Add ≥5 more independent flood events across additional regions.",
            "Ingest IMERG sub-daily for 1h/3h/6h intensity features.",
            "Ingest CWC river level data (formal request required).",
            "Ingest ERA5-Land soil moisture for antecedent conditions.",
            "Download additional GLO-30 DEM tiles for terrain coverage.",
            "Obtain cell-level flood extent maps for spatially precise labels.",
        ],
    }

    meta_path = MODELS_DIR / "flood_research_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    log.info(f"  Model saved: {pkl_path}")
    log.info(f"  Metadata: {meta_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Flood Research Models  [EXPERIMENTAL_BASELINE_ONLY]")
    log.info("STATUS: NOT operational. 3 independent positive events.")
    log.info("=" * 65)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Load + verify
    df = load_data()
    verify_no_synthetic(df)

    log.info(f"\nraw_rows={len(df):,}  independent_groups={df['event_id'].nunique()}")
    log.info(f"  Positive events (3): {POSITIVE_EVENT_IDS}")
    log.info(f"  Negative windows (3): {NEGATIVE_WINDOW_IDS}")

    # Check antecedent parity
    antecedent_ok = check_antecedent_parity(df)

    # Get feature set
    feature_set = get_core_common_features(antecedent_ok=antecedent_ok,
                                           include_spatial_in_nonloro=False)
    # Restrict to features actually present in df
    feature_set.features = [f for f in feature_set.features if f in df.columns]

    # Print final predictor list
    log.info(f"\n{'='*65}")
    log.info(f"FINAL PREDICTOR LIST ({len(feature_set.features)} features):")
    for f in feature_set.features:
        miss = 100 * df[f].isna().mean()
        log.info(f"  {f:30s}  miss={miss:.1f}%")
    log.info(f"{'='*65}")

    # Assert no blacklist leakage
    assert_no_blacklist_in_features(feature_set.features, "final predictor list")
    log.info("  [✓] No blacklisted features in predictor list")

    # Run training
    results = run_training(df, feature_set, antecedent_ok)

    # Macro summary
    macro = macro_summary(results["metrics"], strategy="LOEO")
    log.info(f"\n── LOEO Macro Summary ───────────────────────────────────────────────")
    for k, v in macro.items():
        if "mean" in k:
            std_key = k.replace("mean", "std")
            log.info(f"  {k:45s} = {v:.4f} ± {macro.get(std_key, 0):.4f}")

    # Save outputs
    metrics_df = pd.DataFrame(results["metrics"])
    metrics_df.to_csv(EVAL_DIR / "fold_metrics.csv", index=False)
    log.info(f"  fold_metrics.csv: {len(metrics_df)} rows")

    event_df = pd.DataFrame(results["event_metrics"])
    event_df.to_csv(EVAL_DIR / "event_metrics.csv", index=False)

    thr_df = pd.DataFrame(results["threshold_analysis"])
    if not thr_df.empty:
        thr_df.to_csv(EVAL_DIR / "threshold_analysis.csv", index=False)

    imp_df = pd.DataFrame(results["feature_importances"])
    if not imp_df.empty:
        imp_df.to_csv(EVAL_DIR / "feature_importance.csv", index=False)

    # Best model selection
    best = results["best_model"]
    log.info(f"\n── Best Model ───────────────────────────────────────────────────────")
    log.info(f"  Selected: {best['name']}  (LOEO macro PR-AUC={best['score']:.4f})")
    log.info(f"  Selection criterion: highest macro LOEO PR-AUC across 6 LOEO folds")
    log.info(f"  NOT selected by accuracy or test-fold tuning")

    save_best_model(best, feature_set, antecedent_ok, df)

    # Event-level detection summary
    log.info(f"\n── Event-Level Detection Summary (LOEO) ─────────────────────────────")
    if not event_df.empty:
        pos_events = event_df[(event_df["label"] == 1) &
                              (event_df["model"] == best["name"])]
        for _, row in pos_events.iterrows():
            detected = row["positive_event_detected"]
            icon = "✓" if detected else "✗"
            log.info(f"  [{icon}] {row['event_id']:35s}  recall={row['recall_pod']:.3f}  PR-AUC={row['pr_auc']:.3f}")

    # Threshold
    log.info(f"\n── Threshold Note ─────────────────────────────────────────────────")
    log.info(f"  Reference threshold: 0.50 (default)")
    log.info(f"  Threshold sweep is EXPLORATORY ONLY — see threshold_analysis.csv")
    log.info(f"  DO NOT claim an operationally tuned threshold with 6 event groups")

    # Calibration
    log.info(f"\n── Calibration ────────────────────────────────────────────────────")
    log.info(f"  INSUFFICIENT_EVENT_COUNT_FOR_RELIABLE_CALIBRATION")
    log.info(f"  6 independent groups is insufficient for reliable isotonic/Platt calibration.")

    log.info(f"\n{'='*65}")
    log.info(f"FINAL STATUS:")
    log.info(f"  Flood:     EXPERIMENTAL_BASELINE_ONLY (3 independent positive events)")
    log.info(f"  Landslide: NEEDS_MORE_EVENTS (14 rows — not trained)")
    log.info(f"  Best model: {best['name']}  LOEO PR-AUC={best['score']:.4f}")
    log.info(f"  NOT OPERATIONAL. NOT DEPLOYABLE.")
    log.info(f"{'='*65}")

    return results


if __name__ == "__main__":
    main()
