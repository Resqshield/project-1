"""
resqshield_ml.evaluation.compare_flood_baselines
==================================================
Comparison harness for the T09 flash-flood baselines.

Compares three flood-warning approaches on the same dataset:
  1. FloodThresholdBaseline  — explainable rule-based model
  2. FloodModel('gradient_boosting') — GradientBoostingRegressor
  3. FloodModel('xgboost')           — XGBRegressor

Design constraints
------------------
- Regression metrics (RMSE, MAE, R², NSE) are always computed if y_obs
  and y_pred are available.
- Event classification metrics (POD/recall, FAR, CSI, precision, F1)
  are computed ONLY if an explicit, station-validated threshold is provided.
  Never derive a flood label from an arbitrary percentile.
- Synthetic test data may be used for pipeline smoke tests, but
  results from synthetic runs must NOT be presented as ResQShield
  operational performance.

Usage (once real CWC data is available)
-----------------------------------------
    from resqshield_ml.evaluation.compare_flood_baselines import (
        compare_flood_baselines,
    )
    report = compare_flood_baselines(
        df_train=train_df,
        df_test=test_df,
        target_col="water_level_m",
        forecast_horizon=1,
        validated_threshold_m=None,   # Set only if CWC WL/DL confirmed
    )
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from resqshield_ml.evaluation.metrics import mae, nse, r2, rmse
from resqshield_ml.features.engineer import (
    add_antecedent_precipitation_index,
    add_lag_features,
    add_rate_of_rise,
    add_rolling_features,
)
from resqshield_ml.models.flood_model import FloodModel

logger = logging.getLogger(__name__)


# ─── Event Metrics (gated behind validated threshold) ─────────────────────────

def _compute_event_metrics(
    y_pred: np.ndarray,
    y_obs: np.ndarray,
    threshold_m: float,
) -> dict[str, float]:
    """Compute binary flood event metrics.

    Only call this when the threshold is sourced from station metadata
    (CWC Warning Level or Danger Level) and has been verified.

    Parameters
    ----------
    y_pred : np.ndarray
        Predicted water levels (m).
    y_obs : np.ndarray
        Observed water levels (m).
    threshold_m : float
        Station-validated flood threshold (m).

    Returns
    -------
    dict with keys: POD, FAR, CSI, precision, F1, n_observed_events
    """
    obs_bin = (y_obs >= threshold_m).astype(int)
    pred_bin = (y_pred >= threshold_m).astype(int)

    TP = int(((pred_bin == 1) & (obs_bin == 1)).sum())
    FP = int(((pred_bin == 1) & (obs_bin == 0)).sum())
    FN = int(((pred_bin == 0) & (obs_bin == 1)).sum())
    TN = int(((pred_bin == 0) & (obs_bin == 0)).sum())

    pod = TP / max(TP + FN, 1)            # Probability of Detection = recall
    far = FP / max(TP + FP, 1)            # False Alarm Ratio
    csi = TP / max(TP + FP + FN, 1)       # Critical Success Index
    precision = TP / max(TP + FP, 1)
    f1 = (2 * TP) / max(2 * TP + FP + FN, 1)

    return {
        "POD": round(pod, 4),
        "FAR": round(far, 4),
        "CSI": round(csi, 4),
        "precision": round(precision, 4),
        "F1": round(f1, 4),
        "TP": TP,
        "FP": FP,
        "FN": FN,
        "TN": TN,
        "n_observed_events": int(obs_bin.sum()),
        "threshold_m": threshold_m,
    }


# ─── Feature Engineering for T09 ─────────────────────────────────────────────

def engineer_flood_features(
    df: pd.DataFrame,
    lag_hours: list[int] | None = None,
    rolling_windows: list[int] | None = None,
) -> pd.DataFrame:
    """Build the full T09 feature set from a raw sensor DataFrame.

    Features constructed (all causal — current/past data only):
        - rainfall_mm_hr                    (current)
        - rainfall_mm_hr_rolling_sum_{1,3,6,12,24}  (cumulative)
        - antecedent_precipitation_index    (exponential weighted sum)
        - water_level_m                     (current)
        - water_level_m_lag_{1,3,6,12,24}  (lagged)
        - water_level_m_delta_{1,3,6}       (rate of rise)

    No future rainfall or future water-level values are used as inputs.

    Parameters
    ----------
    df : pd.DataFrame
        Raw (or CWC-normalised) sensor DataFrame.
    lag_hours : list of int
        Lag steps for water-level lag features.
    rolling_windows : list of int
        Window sizes for cumulative rainfall.

    Returns
    -------
    pd.DataFrame
        Feature-engineered DataFrame (NaN rows from warmup still present).
    """
    if lag_hours is None:
        lag_hours = [1, 3, 6, 12, 24]
    if rolling_windows is None:
        rolling_windows = [1, 3, 6, 12, 24]

    # Cumulative rainfall windows
    if "rainfall_mm_hr" in df.columns:
        df = add_rolling_features(
            df,
            columns=["rainfall_mm_hr"],
            window_steps=rolling_windows,
            func="sum",
        )
        df = add_antecedent_precipitation_index(df, rainfall_col="rainfall_mm_hr")

    # Lagged water level
    if "water_level_m" in df.columns:
        df = add_lag_features(
            df, columns=["water_level_m"], lag_steps=lag_hours
        )
        df = add_rate_of_rise(
            df, level_col="water_level_m", delta_windows=[1, 3, 6]
        )

    return df


# ─── Regression Metrics ───────────────────────────────────────────────────────

def _regression_metrics(
    y_pred: np.ndarray,
    y_obs: np.ndarray,
) -> dict[str, float]:
    return {
        "RMSE": round(rmse(y_pred, y_obs), 4),
        "MAE": round(mae(y_pred, y_obs), 4),
        "R2": round(r2(y_pred, y_obs), 4),
        "NSE": round(nse(y_pred, y_obs), 4),
    }


# ─── Main Comparison Function ────────────────────────────────────────────────

def compare_flood_baselines(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    target_col: str = "water_level_m",
    forecast_horizon: int = 1,
    validated_threshold_m: float | None = None,
    gb_params: dict[str, Any] | None = None,
    xgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare FloodThresholdBaseline, GB, and XGBoost on the same data.

    ⚠️  Event metrics (POD, FAR, CSI) are only computed when
    `validated_threshold_m` is explicitly provided.  Never pass an
    arbitrary percentile as the threshold.

    Parameters
    ----------
    df_train : pd.DataFrame
        Training data (raw or feature-engineered; must include target_col).
    df_test : pd.DataFrame
        Test data (same schema as df_train).
    target_col : str
        Column to predict (default 'water_level_m').
    forecast_horizon : int
        Steps ahead to forecast (default 1 = 1 hour ahead for hourly data).
    validated_threshold_m : float or None
        A station-validated flood threshold in metres.
        Set ONLY from CWC station metadata (WL or DL).
        If None, event metrics are disabled.
    gb_params : dict, optional
        Override hyperparameters for GradientBoostingRegressor.
    xgb_params : dict, optional
        Override hyperparameters for XGBRegressor.

    Returns
    -------
    dict
        Comparison report with keys:
            'models': dict of {model_name: {RMSE, MAE, R2, NSE, ...}}
            'event_metrics_disabled': bool
            'validated_threshold_m': float or None
            'n_train': int
            'n_test': int
            'target_col': str
            'forecast_horizon_hours': int
    """
    report: dict[str, Any] = {
        "target_col": target_col,
        "forecast_horizon_hours": forecast_horizon,
        "n_train": len(df_train),
        "n_test": len(df_test),
        "event_metrics_disabled": validated_threshold_m is None,
        "validated_threshold_m": validated_threshold_m,
        "models": {},
    }

    # ── Build X/y for ML models ───────────────────────────────────────────
    # Target: future water level shifted by forecast_horizon
    if target_col not in df_train.columns:
        raise ValueError(f"Target column '{target_col}' not in training data.")

    feature_cols = [c for c in df_train.columns if c != target_col]

    y_train = df_train[target_col].shift(-forecast_horizon)
    X_train = df_train[feature_cols]

    y_test = df_test[target_col].shift(-forecast_horizon)
    X_test = df_test[feature_cols]

    # Drop NaN rows (from lag warmup + horizon shift)
    valid_train = (~X_train.isna().any(axis=1)) & (~y_train.isna())
    valid_test = (~X_test.isna().any(axis=1)) & (~y_test.isna())

    X_train, y_train = X_train[valid_train], y_train[valid_train]
    X_test, y_test = X_test[valid_test], y_test[valid_test]

    logger.info(
        "Training set: %d rows after NaN removal.  Test set: %d rows.",
        len(X_train), len(X_test),
    )

    if len(X_train) == 0 or len(X_test) == 0:
        logger.warning("Empty training or test set — metrics will be NaN.")
        report["warning"] = "Empty training or test set after NaN removal."
        return report

    y_obs = np.asarray(y_test, dtype=float)

    # ── 1. Gradient Boosting ─────────────────────────────────────────────
    _gb_params = {
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "min_samples_split": 10,
        "min_samples_leaf": 5,
        "random_state": 42,
    }
    if gb_params:
        _gb_params.update(gb_params)

    gb_model = FloodModel(kind="gradient_boosting", model_params=_gb_params)
    gb_model.fit(X_train, y_train)
    y_pred_gb = gb_model.predict(X_test)

    gb_report = _regression_metrics(y_pred_gb, y_obs)
    if validated_threshold_m is not None:
        gb_report["event_metrics"] = _compute_event_metrics(
            y_pred_gb, y_obs, validated_threshold_m,
        )
    report["models"]["gradient_boosting"] = gb_report
    logger.info("GB — RMSE: %.4f | NSE: %.4f", gb_report["RMSE"], gb_report["NSE"])

    # ── 2. XGBoost ───────────────────────────────────────────────────────
    _xgb_params = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": 42,
        "n_jobs": -1,
    }
    if xgb_params:
        _xgb_params.update(xgb_params)

    try:
        xgb_model = FloodModel(kind="xgboost", model_params=_xgb_params)
        xgb_model.fit(X_train, y_train)
        y_pred_xgb = xgb_model.predict(X_test)

        xgb_report = _regression_metrics(y_pred_xgb, y_obs)
        if validated_threshold_m is not None:
            xgb_report["event_metrics"] = _compute_event_metrics(
                y_pred_xgb, y_obs, validated_threshold_m,
            )
        report["models"]["xgboost"] = xgb_report
        logger.info(
            "XGB — RMSE: %.4f | NSE: %.4f", xgb_report["RMSE"], xgb_report["NSE"],
        )
    except Exception as exc:
        logger.warning("XGBoost failed — skipping. Error: %s", exc)
        report["models"]["xgboost"] = {"error": str(exc)}

    # ── 3. Threshold baseline (heuristic — predict risk level, not m) ────
    # The threshold baseline returns risk levels (0–4 ints), not water-level
    # metres, so regression metrics (RMSE, MAE, R², NSE) against a continuous
    # target are NOT meaningful.
    # We record the fraction of timesteps flagged at each risk level and
    # note that regression comparison requires a continuous regressor.
    report["models"]["flood_threshold_baseline"] = {
        "note": (
            "FloodThresholdBaseline outputs categorical risk levels (0–4), "
            "not continuous water-level metres. "
            "Regression metrics (RMSE, MAE, R², NSE) are not applicable. "
            "Calibrate production thresholds and use event metrics (POD/FAR/CSI) "
            "once a validated threshold is available from CWC station metadata."
        ),
        "status": "thresholds_not_calibrated",
    }

    # ── Comparison Table ─────────────────────────────────────────────────
    _log_comparison_table(report)
    return report


def _log_comparison_table(report: dict[str, Any]) -> None:
    """Log a formatted comparison table to the logger."""
    header = f"{'Model':<30} {'RMSE':>8} {'MAE':>8} {'R2':>8} {'NSE':>8}"
    logger.info("=" * len(header))
    logger.info("T09 Flash-Flood Baseline Comparison")
    logger.info("=" * len(header))
    logger.info(header)
    logger.info("-" * len(header))
    for model_name, metrics in report["models"].items():
        if "RMSE" in metrics:
            logger.info(
                "%-30s %8.4f %8.4f %8.4f %8.4f",
                model_name,
                metrics["RMSE"],
                metrics["MAE"],
                metrics["R2"],
                metrics["NSE"],
            )
        else:
            note = metrics.get("note", metrics.get("error", "N/A"))[:50]
            logger.info("%-30s %s", model_name, note)
    if report.get("event_metrics_disabled"):
        logger.info("")
        logger.info(
            "NOTE: Event metrics (POD/FAR/CSI) disabled — "
            "no validated CWC station threshold provided."
        )
    logger.info("=" * len(header))


# ─── Report Formatting ────────────────────────────────────────────────────────

def format_comparison_report(report: dict[str, Any]) -> str:
    """Format the comparison report as a human-readable string."""
    lines = [
        "=" * 60,
        "T09 Flash-Flood Baseline Comparison Report",
        "=" * 60,
        f"Target column      : {report.get('target_col')}",
        f"Forecast horizon   : {report.get('forecast_horizon_hours')} hour(s)",
        f"Training samples   : {report.get('n_train')}",
        f"Test samples       : {report.get('n_test')}",
        f"Validated threshold: {report.get('validated_threshold_m')} m",
        f"Event metrics      : {'disabled' if report.get('event_metrics_disabled') else 'enabled'}",
        "",
        f"{'Model':<30} {'RMSE':>8} {'MAE':>8} {'R2':>8} {'NSE':>8}",
        "-" * 60,
    ]
    for model_name, metrics in report.get("models", {}).items():
        if "RMSE" in metrics:
            lines.append(
                f"{model_name:<30} "
                f"{metrics['RMSE']:>8.4f} "
                f"{metrics['MAE']:>8.4f} "
                f"{metrics['R2']:>8.4f} "
                f"{metrics['NSE']:>8.4f}"
            )
            if "event_metrics" in metrics:
                em = metrics["event_metrics"]
                lines.append(
                    f"  ↳ POD={em.get('POD', 'N/A'):.3f}  "
                    f"FAR={em.get('FAR', 'N/A'):.3f}  "
                    f"CSI={em.get('CSI', 'N/A'):.3f}  "
                    f"F1={em.get('F1', 'N/A'):.3f}"
                )
        else:
            note = metrics.get("note", metrics.get("error", "N/A"))
            lines.append(f"{model_name:<30} — {note[:30]}...")
    lines.append("=" * 60)
    return "\n".join(lines)
