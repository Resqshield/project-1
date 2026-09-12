"""
resqshield_ml.evaluation.metrics
==================================
Evaluation metrics for the ResQShield flood prediction pipeline.

NSE, RMSE, and ME are adapted from (MIT License):
    ECMWFCode4Earth/ml_flood :: python/misc/verification.py
    Authors: @lkugler, @seblehner — ESoWC 2019, MATEHIW Project

Additional metrics (MAE, R2, precision, recall, F1, ROC-AUC) added by
the ResQShield team to support early-warning threshold evaluation.

Attribution preserved per MIT License requirement.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


# ─── Hydrological Metrics (adapted from ml_flood/verification.py) ─────────────
# Original implementations: float-based numpy arrays
# ResQShield adaptation: also accepts pandas Series

def rmse(pred: np.ndarray | pd.Series, obs: np.ndarray | pd.Series) -> float:
    """Root Mean Squared Error.

    Adapted from ECMWFCode4Earth/ml_flood::verification.py (MIT License).
    Original: float(np.sqrt(np.nanmean((pred - obs)**2)))
    """
    pred = np.asarray(pred, dtype=float)
    obs = np.asarray(obs, dtype=float)
    return float(np.sqrt(np.nanmean((pred - obs) ** 2)))


def mae(pred: np.ndarray | pd.Series, obs: np.ndarray | pd.Series) -> float:
    """Mean Absolute Error."""
    pred = np.asarray(pred, dtype=float)
    obs = np.asarray(obs, dtype=float)
    return float(np.nanmean(np.abs(pred - obs)))


def mean_error(pred: np.ndarray | pd.Series, obs: np.ndarray | pd.Series) -> float:
    """Mean Error (bias).

    Adapted from ECMWFCode4Earth/ml_flood::verification.py (MIT License).
    Original: float(np.nanmean(pred - obs))
    """
    pred = np.asarray(pred, dtype=float)
    obs = np.asarray(obs, dtype=float)
    return float(np.nanmean(pred - obs))


def nse(pred: np.ndarray | pd.Series, obs: np.ndarray | pd.Series) -> float:
    """Nash-Sutcliffe Efficiency (NSE).

    NSE = 1 indicates a perfect model.
    NSE = 0 means the model is no better than predicting the mean.
    NSE < 0 means the model is worse than predicting the mean.

    Adapted from ECMWFCode4Earth/ml_flood::verification.py (MIT License).
    Original:
        difference = pred - obs
        squarediff = np.dot(difference, difference)
        obs_dis_anom = obs - np.nanmean(obs)
        return float(1 - squarediff / np.dot(obs_dis_anom, obs_dis_anom))
    """
    pred = np.asarray(pred, dtype=float)
    obs = np.asarray(obs, dtype=float)

    # Remove NaN pairs
    valid = ~(np.isnan(pred) | np.isnan(obs))
    pred, obs = pred[valid], obs[valid]

    if len(pred) == 0:
        logger.warning("NSE: no valid samples after NaN removal.")
        return float("nan")

    numerator = np.sum((pred - obs) ** 2)
    denominator = np.sum((obs - np.mean(obs)) ** 2)

    if denominator == 0:
        logger.warning("NSE: denominator is zero (obs has zero variance). Returning NaN.")
        return float("nan")

    return float(1.0 - numerator / denominator)


def r2(pred: np.ndarray | pd.Series, obs: np.ndarray | pd.Series) -> float:
    """Coefficient of determination (R²)."""
    return float(r2_score(
        np.asarray(obs, dtype=float),
        np.asarray(pred, dtype=float)
    ))


# ─── Classification / Alert Metrics ───────────────────────────────────────────
# Applied when regression output is thresholded into flood/no-flood events

def compute_alert_metrics(
    y_pred_continuous: np.ndarray | pd.Series,
    y_obs_continuous: np.ndarray | pd.Series,
    threshold: float,
) -> dict[str, float]:
    """Compute binary classification metrics for flood alerts.

    Converts continuous predictions and observations to binary
    (flood / no-flood) using a water-level threshold, then computes
    precision, recall, F1, and ROC-AUC.

    Parameters
    ----------
    y_pred_continuous : array-like
        Predicted water levels (m).
    y_obs_continuous : array-like
        Observed water levels (m).
    threshold : float
        Alert threshold in metres (e.g. warning_level_m from config).

    Returns
    -------
    dict
        Dictionary with precision, recall, f1, roc_auc, and confusion matrix
        components (TP, FP, FN, TN).
    """
    y_pred_c = np.asarray(y_pred_continuous, dtype=float)
    y_obs_c = np.asarray(y_obs_continuous, dtype=float)

    y_pred_bin = (y_pred_c >= threshold).astype(int)
    y_obs_bin = (y_obs_c >= threshold).astype(int)

    n_flood_obs = int(y_obs_bin.sum())
    if n_flood_obs == 0:
        logger.warning(
            "No flood events in observations at threshold=%.2f m. "
            "Classification metrics will be trivial.", threshold
        )

    results: dict[str, float] = {
        "precision": float(precision_score(y_obs_bin, y_pred_bin, zero_division=0)),
        "recall": float(recall_score(y_obs_bin, y_pred_bin, zero_division=0)),
        "f1": float(f1_score(y_obs_bin, y_pred_bin, zero_division=0)),
        "n_flood_events_observed": n_flood_obs,
        "threshold_m": threshold,
    }

    # ROC-AUC requires probability scores — we use normalised continuous values
    try:
        y_score = (y_pred_c - y_pred_c.min()) / (y_pred_c.max() - y_pred_c.min() + 1e-8)
        results["roc_auc"] = float(roc_auc_score(y_obs_bin, y_score))
    except ValueError:
        results["roc_auc"] = float("nan")

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_obs_bin, y_pred_bin, labels=[0, 1]).ravel()
    results.update({"TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn)})

    return results


# ─── Full Evaluation Suite ────────────────────────────────────────────────────

def evaluate(
    y_pred: np.ndarray | pd.Series,
    y_obs: np.ndarray | pd.Series,
    cfg: dict[str, Any],
    split_name: str = "test",
) -> dict[str, Any]:
    """Run the complete ResQShield evaluation suite.

    Parameters
    ----------
    y_pred : array-like
        Model predictions (continuous water level in m).
    y_obs : array-like
        Ground truth observations.
    cfg : dict
        Full experiment config.
    split_name : str
        Label for this evaluation split (e.g. 'val', 'test').

    Returns
    -------
    dict
        All computed metrics as a flat dictionary.
    """
    eval_cfg = cfg.get("evaluation", {})
    alert_cfg = cfg.get("alert", {})

    results: dict[str, Any] = {
        "experiment": cfg.get("experiment", {}).get("name", "unnamed"),
        "split": split_name,
        "n_samples": len(y_pred),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Regression metrics
    metric_map = {"RMSE": rmse, "MAE": mae, "NSE": nse, "ME": mean_error, "R2": r2}
    for metric_name in eval_cfg.get("regression_metrics", list(metric_map.keys())):
        fn = metric_map.get(metric_name)
        if fn:
            results[metric_name] = fn(y_pred, y_obs)
            logger.info("%s [%s]: %.4f", metric_name, split_name, results[metric_name])

    # Classification / alert metrics per threshold
    if eval_cfg.get("classification_metrics"):
        for level_key, threshold in [
            ("warning_level_m", alert_cfg.get("warning_level_m", 3.5)),
            ("danger_level_m", alert_cfg.get("danger_level_m", 5.0)),
        ]:
            prefix = level_key.replace("_m", "")
            alert_results = compute_alert_metrics(y_pred, y_obs, threshold=threshold)
            for k, v in alert_results.items():
                results[f"{prefix}_{k}"] = v
            logger.info(
                "[%s] Alert @ %.1fm — Precision: %.3f | Recall: %.3f | F1: %.3f",
                split_name, threshold,
                alert_results.get("precision", float("nan")),
                alert_results.get("recall", float("nan")),
                alert_results.get("f1", float("nan")),
            )

    return results


# ─── Artifact Saving ──────────────────────────────────────────────────────────

def save_metrics(metrics: dict[str, Any], output_dir: str | Path, filename: str) -> Path:
    """Save evaluation metrics to a JSON file.

    Parameters
    ----------
    metrics : dict
        Metrics dictionary from evaluate().
    output_dir : str or Path
        Directory to write to (e.g., 'artifacts/metrics/').
    filename : str
        Output filename (e.g., 'test_metrics.json').

    Returns
    -------
    Path
        Path to the written JSON file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)

    logger.info("Metrics saved to: %s", out_path)
    return out_path


def save_predictions(
    y_pred: np.ndarray | pd.Series,
    y_obs: np.ndarray | pd.Series,
    index: pd.DatetimeIndex | None,
    output_dir: str | Path,
    filename: str = "predictions.csv",
) -> Path:
    """Save predictions vs observations to a CSV file.

    Parameters
    ----------
    y_pred : array-like
        Predicted values.
    y_obs : array-like
        Observed values.
    index : DatetimeIndex or None
        Timestamps for the predictions.
    output_dir : str or Path
        Directory to write to.
    filename : str
        Output filename.

    Returns
    -------
    Path
        Path to the written CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename

    df = pd.DataFrame({"predicted": np.asarray(y_pred), "observed": np.asarray(y_obs)})
    if index is not None:
        df.index = index

    df.to_csv(out_path)
    logger.info("Predictions saved to: %s", out_path)
    return out_path
