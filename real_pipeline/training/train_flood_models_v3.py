# -*- coding: utf-8 -*-
"""
real_pipeline/training/train_flood_models_v3.py
================================================
Flood research baseline training v3 -- uses flood_training_v3.parquet
(10 positive events, 8 regions, CHIRPS v2).

STATUS:  EXPERIMENTAL_BASELINE_ONLY
         NOT deployment-ready.
         All labels are regional (B/C) -- no observed inundation geometry.

KEY DIFFERENCES FROM v2:
  - Uses flood_training_v3.parquet (10 events, 8 regions, mapped to villages) vs v2
  - Region column is 'region' (not 'pilot_region')
  - Rain features excluded if class-conditional missingness delta > 5%
    (Assam 2017 lacks CHIRPS -> delta ~20% -> rain excluded from primary model)
  - LOEO folds = 18 (10 pos + 8 neg event groups)
  - LORO folds = 8 (one per region)

Outputs:
  models_real/flood_v3_research_model.pkl
  models_real/flood_v3_research_metadata.json
  data_real/evaluation_v3/fold_metrics.csv
  data_real/evaluation_v3/event_metrics.csv
  data_real/evaluation_v3/threshold_analysis.csv
  data_real/evaluation_v3/feature_importance.csv
  data_real/evaluation_v3/model_card_flood_v3.md
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
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

FEAT_DIR   = PROJECT_ROOT / "data_real" / "features"
EVAL_DIR   = PROJECT_ROOT / "data_real" / "evaluation_v3"
MODELS_DIR = PROJECT_ROOT / "models_real"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_flood_v3")

RANDOM_SEED = 42
ANTECEDENT_LEAK_THRESHOLD = 0.05   # max allowed missingness delta

POSITIVE_EVENT_IDS = [
    "IND_FLOOD_2013_UK_001",
    "IND_FLOOD_2017_AS_001",
    "IND_FLOOD_2017_BR_001",
    "IND_FLOOD_2018_KL_001",
    "IND_FLOOD_2018_OD_001",
    "IND_FLOOD_2019_BR_001",
    "IND_FLOOD_2020_OD_001",
    "IND_FLOOD_2021_MH_001",
    "IND_FLOOD_2022_AS_001",
    "IND_FLOOD_2023_HP_001",
]
NEGATIVE_WINDOW_IDS = [
    "NEG_AS_2022_DRY_WINTER",
    "NEG_BR_2017_RABI",
    "NEG_HP_PREMONSOON",
    "NEG_KL_2019_PREMONSOON",
    "NEG_MH_KOLHAPUR_DRY",
    "NEG_OD_COASTAL_DRY",
    "NEG_OD_MAHANADI_DRY",
    "NEG_UK_2013_PREMONSOON",
]

RAIN_FEATURES = [
    "rain_event_sum_mm", "rain_event_max_mm", "rain_event_mean_mm",
    "rain_event_p90_mm", "n_days_valid_chirps", "chirps_coverage_pct",
    "ant_3d_mm", "n_days_ant_3d",
    "ant_7d_mm", "n_days_ant_7d",
    "ant_14d_mm", "n_days_ant_14d",
]

SPATIAL_FEATURES = ["lat_center", "lon_center"]
TERRAIN_FEATURES = ["elev_mean_m", "slope_mean_deg", "pct_slope_gt_30"]
HYDRO_FEATURES = ["distance_to_stream_m", "flow_accumulation_skm"]

BLACKLIST = {
    "label", "event_id", "region", "cell_id",
    "window_start", "window_end", "window_type",
    "label_source", "label_type", "label_spatial_precision",
    "label_temporal_precision", "label_quality",
    "label_quality_class", "label_quality_class_note",
    "rain_source", "terrain_available", "terrain_source",
    "data_type",
}


def load_data() -> pd.DataFrame:
    path = FEAT_DIR / "flood_training_v3.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Flood v3 matrix missing: {path}")
    df = pd.read_parquet(str(path))
    log.info(f"Loaded: {len(df):,} rows, {len(df.columns)} cols")
    log.info(f"  event_groups={df['event_id'].nunique()}")
    log.info(f"  positive_events={df[df['label']==1]['event_id'].nunique()}")
    log.info(f"  negative_windows={df[df['label']==0]['event_id'].nunique()}")
    log.info(f"  regions={sorted(df['region'].unique().tolist())}")
    return df


def verify_no_synthetic(df: pd.DataFrame) -> None:
    expected = "REAL_DATA_NOT_SYNTHETIC"
    if not (df["data_type"] == expected).all():
        bad = df[df["data_type"] != expected]["data_type"].value_counts()
        raise ValueError(f"SYNTHETIC DATA DETECTED: {bad.to_dict()}")
    log.info("  [OK] No synthetic data detected")


def check_rain_parity(df: pd.DataFrame) -> bool:
    log.info("\nRain feature class-conditional missingness:")
    any_fail = False
    for col in RAIN_FEATURES:
        if col not in df.columns:
            continue
        miss_pos = df[df["label"] == 1][col].isna().mean()
        miss_neg = df[df["label"] == 0][col].isna().mean()
        delta    = abs(miss_pos - miss_neg)
        ok       = delta <= ANTECEDENT_LEAK_THRESHOLD
        icon     = "OK" if ok else "FAIL"
        log.info(f"  [{icon}] {col:25s}  pos={miss_pos*100:5.1f}%  "
                 f"neg={miss_neg*100:5.1f}%  delta={delta*100:5.1f}%")
        if not ok:
            any_fail = True
    if any_fail:
        log.warning("  -> Rain features EXCLUDED (class-correlated missingness > 5%)")
        log.warning("     Root cause: Assam 2017 event has no CHIRPS. Download CHIRPS 2017-06/07.")
    else:
        log.info("  -> Rain features INCLUDED (parity verified)")
    return not any_fail


def check_terrain_parity(df: pd.DataFrame) -> bool:
    if "elev_mean_m" not in df.columns:
        return False
    miss_pos = df[df["label"] == 1]["elev_mean_m"].isna().mean()
    miss_neg = df[df["label"] == 0]["elev_mean_m"].isna().mean()
    delta    = abs(miss_pos - miss_neg)
    ok       = delta <= ANTECEDENT_LEAK_THRESHOLD and miss_pos < 0.99
    log.info(f"\nTerrain parity: pos={miss_pos*100:.1f}%  neg={miss_neg*100:.1f}%  "
             f"delta={delta*100:.1f}%  -> {'OK' if ok else 'EXCLUDED'}")
    return ok


def select_features(df: pd.DataFrame, rain_ok: bool, terrain_ok: bool) -> list:
    feats = []
    for f in SPATIAL_FEATURES:
        if f in df.columns:
            feats.append(f)
    if rain_ok:
        for f in RAIN_FEATURES:
            if f in df.columns:
                feats.append(f)
        log.info("  Rain features: INCLUDED")
    else:
        log.info("  Rain features: EXCLUDED (parity violation)")
    if terrain_ok:
        for f in TERRAIN_FEATURES:
            if f in df.columns and df[f].isna().mean() < 0.99:
                feats.append(f)
        log.info("  Terrain features: INCLUDED")
    else:
        log.info("  Terrain features: EXCLUDED")
        
    for f in HYDRO_FEATURES:
        if f in df.columns:
            feats.append(f)
    log.info("  Hydro features: INCLUDED")
    blocked = [f for f in feats if f in BLACKLIST]
    assert not blocked, f"BLACKLISTED features in predictor list: {blocked}"
    log.info(f"\nFinal feature list ({len(feats)} features):")
    for f in feats:
        miss = df[f].isna().mean() * 100
        log.info(f"  {f:30s}  miss={miss:.1f}%")
    return feats


def compute_event_weights(df: pd.DataFrame) -> np.ndarray:
    group_sizes = df.groupby("event_id")["cell_id"].transform("count")
    weights = 1.0 / group_sizes.values
    weights = weights / weights.mean()
    return weights


def loeo_folds(df: pd.DataFrame):
    for test_event in sorted(df["event_id"].unique()):
        train_df = df[df["event_id"] != test_event].copy()
        test_df  = df[df["event_id"] == test_event].copy()
        assert len(set(train_df["event_id"]) & {test_event}) == 0
        yield f"loeo_{test_event}", train_df, test_df, test_event


def loro_folds(df: pd.DataFrame):
    for test_region in sorted(df["region"].unique()):
        train_df = df[df["region"] != test_region].copy()
        test_df  = df[df["region"] == test_region].copy()
        if len(np.unique(train_df["label"])) < 2:
            log.warning(f"  LORO {test_region}: only one class in train -- skipping")
            continue
        yield f"loro_{test_region}", train_df, test_df, test_region


def build_models(random_state: int = 42) -> dict:
    return {
        "LogisticRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf",    LogisticRegression(
                C=0.1, max_iter=1000, class_weight="balanced",
                solver="lbfgs", random_state=random_state,
            )),
        ]),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=20,
            class_weight="balanced", random_state=random_state, n_jobs=1,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=300, max_depth=5, l2_regularization=0.5,
            random_state=random_state,
        ),
    }


def compute_metrics(y_true, y_prob, threshold: float = 0.50) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    far       = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1        = 2*precision*recall / (precision+recall) if (precision+recall) > 0 else 0.0
    try:    pr_auc  = float(average_precision_score(y_true, y_prob))
    except: pr_auc  = float("nan")
    try:    roc_auc = float(roc_auc_score(y_true, y_prob))
    except: roc_auc = float("nan")
    try:    brier   = float(brier_score_loss(y_true, y_prob))
    except: brier   = float("nan")
    return {
        "pr_auc": round(pr_auc, 4), "roc_auc": round(roc_auc, 4),
        "recall_pod": round(recall, 4), "precision": round(precision, 4),
        "f1": round(f1, 4), "far": round(far, 4),
        "brier": round(brier, 4),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "support_positive": int(y_true.sum()),
        "support_negative": int((1-y_true).sum()),
        "threshold": threshold,
    }


def prepare_features(df: pd.DataFrame, feature_list: list,
                     fill_strategy: str = "median") -> pd.DataFrame:
    valid = [f for f in feature_list if f in df.columns]
    X = df[valid].copy()
    if fill_strategy == "median":
        for col in X.columns:
            if X[col].isna().any():
                val = X[col].median()
                if pd.isna(val):
                    val = 0
                X[col] = X[col].fillna(val)
    return X


def run_loeo(df: pd.DataFrame, feature_list: list, models: dict) -> dict:
    all_metrics       = []
    all_event_metrics = []
    all_thresholds    = []
    all_importances   = []
    best_model_info   = {"name": None, "model": None, "score": -1.0}

    log.info("\n" + "="*65)
    log.info("LOEO FOLDS (Primary Evaluation)")
    log.info("="*65)

    for model_name, model in models.items():
        log.info(f"\n  Model: {model_name}")
        fold_scores = []

        for fold_name, train_df, test_df, test_event in loeo_folds(df):
            train_weights = compute_event_weights(train_df)
            test_label    = int(test_df["label"].iloc[0])
            test_region   = test_df["region"].iloc[0]

            fill = "passthrough" if model_name == "HistGradientBoosting" else "median"
            X_train = prepare_features(train_df, feature_list, fill)
            X_test  = prepare_features(test_df,  feature_list, fill)
            y_train = train_df["label"].values
            y_test  = test_df["label"].values

            if len(np.unique(y_train)) < 2:
                log.warning(f"    {fold_name}: only one class in train -- skipping")
                continue

            try:
                if model_name == "LogisticRegression":
                    model.fit(X_train, y_train)
                else:
                    model.fit(X_train, y_train, sample_weight=train_weights)
                y_prob = model.predict_proba(X_test)[:, 1]
            except Exception as e:
                log.warning(f"    {fold_name}: fit/predict failed: {e}")
                continue

            m = compute_metrics(y_test, y_prob)
            m.update({
                "fold": fold_name, "strategy": "LOEO", "model": model_name,
                "test_event": test_event, "test_region": test_region,
                "test_label": test_label,
                "test_n_samples": len(test_df),
                "train_n_samples": len(train_df),
                "train_n_events": train_df["event_id"].nunique(),
                "positive_event_detected": bool(test_label == 1 and m["recall_pod"] > 0.5),
            })
            all_metrics.append(m)
            fold_scores.append(m["pr_auc"])

            all_event_metrics.append({
                "event_id": test_event, "region": test_region,
                "label": test_label, "model": model_name,
                "pr_auc": m["pr_auc"], "recall_pod": m["recall_pod"],
                "precision": m["precision"], "f1": m["f1"],
                "far": m["far"], "brier": m["brier"],
                "positive_event_detected": m.get("positive_event_detected", False),
                "n_samples": len(test_df),
            })

            if test_label == 1:
                for t in np.arange(0.1, 0.95, 0.05):
                    tm = compute_metrics(y_test, y_prob, threshold=t)
                    all_thresholds.append({
                        "event_id": test_event, "model": model_name,
                        "threshold": round(float(t), 2),
                        "recall_pod": tm["recall_pod"],
                        "precision": tm["precision"],
                        "far": tm["far"], "f1": tm["f1"],
                        "note": "EXPLORATORY_ONLY",
                    })

            clf = model.named_steps["clf"] if hasattr(model, "named_steps") else model
            if hasattr(clf, "feature_importances_"):
                for fname, imp in zip(feature_list, clf.feature_importances_):
                    all_importances.append({
                        "model": model_name, "fold": fold_name,
                        "feature": fname, "importance": round(float(imp), 6),
                    })
            elif hasattr(clf, "coef_"):
                for fname, coef in zip(feature_list, clf.coef_[0]):
                    all_importances.append({
                        "model": model_name, "fold": fold_name,
                        "feature": fname, "importance": round(float(abs(coef)), 6),
                    })

            log.info(f"    {fold_name:50s}  PR-AUC={m['pr_auc']:.4f}  "
                     f"Recall={m['recall_pod']:.3f}  label={test_label}  n={len(test_df):,}")

        macro_pr = float(np.nanmean(fold_scores)) if fold_scores else 0.0
        log.info(f"  Macro LOEO PR-AUC ({model_name}): {macro_pr:.4f}")
        if macro_pr > best_model_info["score"]:
            best_model_info = {"name": model_name, "model": model, "score": macro_pr}

    return {
        "metrics": all_metrics,
        "event_metrics": all_event_metrics,
        "threshold_analysis": all_thresholds,
        "feature_importances": all_importances,
        "best_model": best_model_info,
    }


def run_loro(df: pd.DataFrame, feature_list: list, best_model_name: str,
             models: dict) -> list:
    log.info("\n" + "="*65)
    log.info("LORO FOLDS (Secondary Evaluation)")
    log.info("="*65)
    results = []
    model = models[best_model_name]
    for fold_name, train_df, test_df, test_region in loro_folds(df):
        train_weights = compute_event_weights(train_df)
        fill = "passthrough" if best_model_name == "HistGradientBoosting" else "median"
        X_train = prepare_features(train_df, feature_list, fill)
        X_test  = prepare_features(test_df,  feature_list, fill)
        y_train = train_df["label"].values
        y_test  = test_df["label"].values
        try:
            if best_model_name == "LogisticRegression":
                model.fit(X_train, y_train)
            else:
                model.fit(X_train, y_train, sample_weight=train_weights)
            y_prob = model.predict_proba(X_test)[:, 1]
            m = compute_metrics(y_test, y_prob)
            m.update({
                "fold": fold_name, "strategy": "LORO",
                "model": best_model_name, "test_region": test_region,
                "test_n_samples": len(test_df),
                "train_n_samples": len(train_df),
            })
            results.append(m)
            log.info(f"  {fold_name:45s}  PR-AUC={m['pr_auc']:.4f}  "
                     f"Recall={m['recall_pod']:.3f}  n={len(test_df):,}")
        except Exception as e:
            log.warning(f"  {fold_name}: failed: {e}")
    return results


def macro_summary(metrics: list, strategy: str, model_name: str = None) -> dict:
    df_m = pd.DataFrame(metrics)
    if model_name:
        df_m = df_m[df_m["model"] == model_name]
    df_m = df_m[df_m["strategy"] == strategy]
    out = {}
    for col in ["pr_auc", "roc_auc", "recall_pod", "precision", "f1", "far", "brier"]:
        if col in df_m.columns:
            out[f"{col}_mean"] = round(float(df_m[col].mean()), 4)
            out[f"{col}_std"]  = round(float(df_m[col].std()),  4)
    return out


def save_best_model(best: dict, feature_list: list, df: pd.DataFrame,
                    rain_ok: bool, loeo_results: dict, loro_results: list):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    pkl_path = MODELS_DIR / "flood_v3_research_model.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump({
            "model": best["model"],
            "features": feature_list,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, f)

    loeo_macro = macro_summary(loeo_results["metrics"], "LOEO", best["name"])
    loro_macro = macro_summary(loro_results, "LORO", best["name"])

    metadata = {
        "schema_version": "v3",
        "data_type": "real_historical_research",
        "status": "EXPERIMENTAL_BASELINE_ONLY",
        "not_operational": True,
        "deployment_allowed": False,
        "model_name": best["name"],
        "feature_list": feature_list,
        "n_features": len(feature_list),
        "rain_features_included": rain_ok,
        "rain_exclusion_reason": (
            None if rain_ok else
            "Class-correlated CHIRPS missingness (delta ~20%). "
            "Assam 2017 event lacks CHIRPS. Fix: download CHIRPS 2017-06/07 Assam bbox."
        ),
        "training_positive_events": POSITIVE_EVENT_IDS,
        "training_negative_windows": NEGATIVE_WINDOW_IDS,
        "n_positive_events": len(POSITIVE_EVENT_IDS),
        "n_negative_windows": len(NEGATIVE_WINDOW_IDS),
        "n_event_groups": int(df["event_id"].nunique()),
        "raw_training_rows": len(df),
        "regions": sorted(df["region"].unique().tolist()),
        "label_quality": {
            "class_A_count": 0,
            "class_B_count": 7,
            "class_C_count": 3,
            "note": "No cell-level observed inundation. All labels are B or C (regional).",
        },
        "validation_strategy": "LOEO_primary_LORO_secondary",
        "loeo_folds": int(df["event_id"].nunique()),
        "loro_folds": int(df["region"].nunique()),
        "loeo_macro": loeo_macro,
        "loro_macro": loro_macro,
        "best_loeo_pr_auc": round(best["score"], 4),
        "calibration": "INSUFFICIENT_EVENT_COUNT",
        "confidence_intervals": "INSUFFICIENT_EVENT_COUNT",
        "random_seed": RANDOM_SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "readiness_label": "EXPERIMENTAL_BASELINE_ONLY",
        "limitations": [
            "All labels are B or C precision (regional, not cell-level truth).",
            "Rain features excluded -- Assam 2017 has no CHIRPS (delta ~20%).",
            "Terrain features missing for ~99% of rows.",
            "Only lat/lon used -- model captures geography, not physics.",
            "10 independent positive events -- limited generalizability.",
            "4 of 8 regions have zero CHIRPS (Odisha x2, Maharashtra, Himachal).",
            "NOT suitable for operational forecasting or deployment.",
        ],
        "recommended_next_steps": [
            "Download CHIRPS 2017-06/07 for Assam to restore rain feature parity.",
            "Obtain CHIRPS for Odisha, Maharashtra, Himachal Pradesh regions.",
            "Add >= 5 more independent flood events for better generalization.",
            "Ingest IMERG sub-daily for intensity features.",
            "Obtain cell-level flood extent maps (class A labels).",
            "Download GLO-30 DEM tiles for terrain coverage.",
        ],
    }

    meta_path = MODELS_DIR / "flood_v3_research_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    log.info(f"  Model saved: {pkl_path}")
    log.info(f"  Metadata:    {meta_path}")


def write_model_card(feature_list: list, rain_ok: bool, loeo_results: dict,
                     loro_results: list, best: dict, df: pd.DataFrame):
    loeo_macro = macro_summary(loeo_results["metrics"], "LOEO", best["name"])
    loro_macro = macro_summary(loro_results, "LORO", best["name"])

    lines = [
        "# ResQ Shield -- Flood Research Model v3  [EXPERIMENTAL_BASELINE_ONLY]",
        "",
        "> **NOT OPERATIONAL. NOT DEPLOYABLE.**",
        "> All labels are regional (B/C). High metrics CANNOT be interpreted as cell-level skill.",
        "",
        "## Model summary",
        f"- **Best model**: {best['name']}",
        f"- **LOEO macro PR-AUC**: {best['score']:.4f}",
        f"- **Features ({len(feature_list)})**: {', '.join(feature_list)}",
        f"- **Rain features included**: {rain_ok}",
        f"- **Training rows**: {len(df):,}",
        f"- **Positive events**: {len(POSITIVE_EVENT_IDS)}",
        f"- **Negative windows**: {len(NEGATIVE_WINDOW_IDS)}",
        f"- **Regions**: {', '.join(sorted(df['region'].unique()))}",
        "",
        "## LOEO macro metrics (primary)",
        "| Metric | Mean | Std |",
        "|--------|------|-----|",
    ]
    for metric in ["pr_auc", "roc_auc", "recall_pod", "precision", "f1", "far", "brier"]:
        mk, sk = f"{metric}_mean", f"{metric}_std"
        if mk in loeo_macro:
            lines.append(f"| {metric} | {loeo_macro[mk]:.4f} | {loeo_macro.get(sk, 0):.4f} |")

    lines += [
        "",
        "## LORO macro metrics (secondary)",
        "| Metric | Mean | Std |",
        "|--------|------|-----|",
    ]
    for metric in ["pr_auc", "recall_pod", "precision", "f1", "far"]:
        mk, sk = f"{metric}_mean", f"{metric}_std"
        if mk in loro_macro:
            lines.append(f"| {metric} | {loro_macro[mk]:.4f} | {loro_macro.get(sk, 0):.4f} |")

    lines += [
        "",
        "## Per-event LOEO results (positive events only)",
        "| Event | Region | PR-AUC | Recall | Precision | Detected |",
        "|-------|--------|--------|--------|-----------|----------|",
    ]
    em_df  = pd.DataFrame(loeo_results["event_metrics"])
    pos_em = em_df[(em_df["label"] == 1) & (em_df["model"] == best["name"])]
    for _, row in pos_em.iterrows():
        detected = "YES" if row.get("positive_event_detected") else "NO"
        lines.append(
            f"| {row['event_id']} | {row['region']} | {row['pr_auc']:.4f} | "
            f"{row['recall_pod']:.3f} | {row['precision']:.3f} | {detected} |"
        )

    lines += [
        "",
        "## Status flags",
        "- `EXPERIMENTAL_BASELINE_ONLY`",
        "- `NOT_OPERATIONAL`",
        "- `LABEL_PRECISION: REGIONAL_B_C`",
        f"- `RAIN_FEATURES: {'INCLUDED' if rain_ok else 'EXCLUDED_PARITY_VIOLATION'}`",
        "- `TERRAIN_FEATURES: EXCLUDED_99PCT_MISSING`",
    ]

    card_path = EVAL_DIR / "model_card_flood_v3.md"
    card_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"  Model card: {card_path}")


def main():
    log.info("="*65)
    log.info("ResQ Shield -- Flood Research Models v3  [EXPERIMENTAL_BASELINE_ONLY]")
    log.info("Matrix: flood_training_v3.parquet  (10 events, 8 regions)")
    log.info("="*65)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data()
    verify_no_synthetic(df)

    rain_ok    = check_rain_parity(df)
    terrain_ok = check_terrain_parity(df)

    feature_list = select_features(df, rain_ok, terrain_ok)
    if not feature_list:
        log.error("No valid features! Aborting.")
        return

    models = build_models(RANDOM_SEED)
    loeo_results = run_loeo(df, feature_list, models)

    best = loeo_results["best_model"]
    log.info(f"\nBest model: {best['name']}  LOEO macro PR-AUC={best['score']:.4f}")

    models_loro = build_models(RANDOM_SEED)
    loro_results = run_loro(df, feature_list, best["name"], models_loro)

    loeo_macro = macro_summary(loeo_results["metrics"], "LOEO", best["name"])
    loro_macro = macro_summary(loro_results, "LORO", best["name"])

    log.info("\n-- LOEO Macro Summary (best model) --")
    for k, v in loeo_macro.items():
        if "mean" in k:
            sk = k.replace("mean", "std")
            log.info(f"  {k:40s} = {v:.4f} +/- {loeo_macro.get(sk, 0):.4f}")

    log.info("\n-- LORO Macro Summary (best model) --")
    for k, v in loro_macro.items():
        if "mean" in k:
            sk = k.replace("mean", "std")
            log.info(f"  {k:40s} = {v:.4f} +/- {loro_macro.get(sk, 0):.4f}")

    log.info("\n-- Event-Level Detection Summary (LOEO, positive events) --")
    em_df  = pd.DataFrame(loeo_results["event_metrics"])
    pos_em = em_df[(em_df["label"] == 1) & (em_df["model"] == best["name"])]
    for _, row in pos_em.iterrows():
        icon = "DETECTED" if row.get("positive_event_detected", False) else "MISSED  "
        log.info(f"  [{icon}] {row['event_id']:40s}  recall={row['recall_pod']:.3f}  "
                 f"PR-AUC={row['pr_auc']:.4f}")

    all_metrics_df = pd.DataFrame(loeo_results["metrics"] + loro_results)
    all_metrics_df.to_csv(EVAL_DIR / "fold_metrics.csv", index=False)
    em_df.to_csv(EVAL_DIR / "event_metrics.csv", index=False)

    thr_df = pd.DataFrame(loeo_results["threshold_analysis"])
    if not thr_df.empty:
        thr_df.to_csv(EVAL_DIR / "threshold_analysis.csv", index=False)

    imp_df = pd.DataFrame(loeo_results["feature_importances"])
    if not imp_df.empty:
        imp_df.to_csv(EVAL_DIR / "feature_importance.csv", index=False)

    save_best_model(best, feature_list, df, rain_ok, loeo_results, loro_results)
    write_model_card(feature_list, rain_ok, loeo_results, loro_results, best, df)

    n_pos    = df[df["label"] == 1]["event_id"].nunique()
    n_reg    = df["region"].nunique()
    gate_pass = n_pos >= 10 and n_reg >= 5

    log.info("\n" + "="*65)
    log.info("GATE H DECISION")
    log.info(f"  positive_events: {n_pos} (need >=10): {'PASS' if n_pos>=10 else 'FAIL'}")
    log.info(f"  regions:         {n_reg} (need >=5):  {'PASS' if n_reg>=5 else 'FAIL'}")
    log.info(f"  rain_parity:     {'FAIL -- excluded' if not rain_ok else 'PASS'}")
    log.info(f"  label_precision: REGIONAL (B/C) -- status=EXPERIMENTAL")
    log.info(f"  GATE_H: {'PASS' if gate_pass else 'PARTIAL'} (EXPERIMENTAL_BASELINE_ONLY)")
    log.info("="*65)
    log.info("FINAL STATUS: EXPERIMENTAL_BASELINE_ONLY -- NOT_OPERATIONAL")
    log.info(f"  Best model: {best['name']}  LOEO macro PR-AUC={best['score']:.4f}")
    log.info("="*65)


if __name__ == "__main__":
    main()
