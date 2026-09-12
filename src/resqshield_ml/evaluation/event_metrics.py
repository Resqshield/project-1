"""
resqshield_ml.evaluation.event_metrics
========================================
Hydrometeorological event / contingency-table metrics for ResQShield.

These metrics are used to evaluate flood-event detection skill from a
regressor output that is thresholded against an explicitly configured
water-level threshold.

Formulas
--------
    POD (Probability of Detection / Recall):
        POD = TP / (TP + FN)

    FAR (False Alarm Ratio):
        FAR = FP / (TP + FP)

    CSI (Critical Success Index / Threat Score):
        CSI = TP / (TP + FP + FN)

    Precision:
        precision = TP / (TP + FP)

    F1:
        F1 = 2 * TP / (2*TP + FP + FN)

IMPORTANT: Event metrics are only computed when a threshold is
explicitly provided by the caller (from alert config, or a test).
No threshold is invented here.

Attribution (MIT License):
    ECMWFCode4Earth/ml_flood :: python/misc/verification.py
    Authors: @lkugler, @seblehner — ESoWC 2019, MATEHIW Project
    URL: https://github.com/ECMWFCode4Earth/ml_flood
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ─── Contingency Table ────────────────────────────────────────────────────────

def contingency_table(
    y_pred: np.ndarray,
    y_obs: np.ndarray,
    threshold: float,
) -> dict[str, int]:
    """Compute TP, FP, TN, FN for a given threshold.

    Parameters
    ----------
    y_pred : array-like
        Continuous model predictions (e.g. predicted water level in m).
    y_obs : array-like
        Continuous observations (e.g. observed water level in m).
    threshold : float
        Alert threshold. Values >= threshold are treated as flood events.

    Returns
    -------
    dict with keys 'TP', 'FP', 'TN', 'FN' as int.
    """
    y_pred = np.asarray(y_pred, dtype=float)
    y_obs = np.asarray(y_obs, dtype=float)

    pred_event = y_pred >= threshold
    obs_event = y_obs >= threshold

    tp = int(np.sum(pred_event & obs_event))
    fp = int(np.sum(pred_event & ~obs_event))
    tn = int(np.sum(~pred_event & ~obs_event))
    fn = int(np.sum(~pred_event & obs_event))

    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn}


# ─── Individual Metrics ───────────────────────────────────────────────────────

def pod(tp: int, fn: int) -> float:
    """Probability of Detection (Recall).

    POD = TP / (TP + FN)
    Returns NaN if TP + FN == 0 (no observed events).
    """
    denom = tp + fn
    if denom == 0:
        logger.warning("POD: no observed events (TP+FN=0). Returning NaN.")
        return float("nan")
    return float(tp / denom)


def far(tp: int, fp: int) -> float:
    """False Alarm Ratio.

    FAR = FP / (TP + FP)
    Returns NaN if TP + FP == 0 (no predicted events).
    """
    denom = tp + fp
    if denom == 0:
        logger.warning("FAR: no predicted events (TP+FP=0). Returning NaN.")
        return float("nan")
    return float(fp / denom)


def csi(tp: int, fp: int, fn: int) -> float:
    """Critical Success Index (Threat Score).

    CSI = TP / (TP + FP + FN)
    Returns NaN if TP + FP + FN == 0.
    """
    denom = tp + fp + fn
    if denom == 0:
        logger.warning("CSI: denominator is zero. Returning NaN.")
        return float("nan")
    return float(tp / denom)


def precision(tp: int, fp: int) -> float:
    """Precision.

    precision = TP / (TP + FP)
    Returns NaN if TP + FP == 0.
    """
    denom = tp + fp
    if denom == 0:
        logger.warning("Precision: no predicted positives (TP+FP=0). Returning NaN.")
        return float("nan")
    return float(tp / denom)


def recall(tp: int, fn: int) -> float:
    """Recall (alias for POD).

    recall = TP / (TP + FN)
    """
    return pod(tp, fn)


def f1_score(tp: int, fp: int, fn: int) -> float:
    """F1 Score.

    F1 = 2*TP / (2*TP + FP + FN)
    Returns NaN if denominator is zero.
    """
    denom = 2 * tp + fp + fn
    if denom == 0:
        logger.warning("F1: denominator is zero. Returning NaN.")
        return float("nan")
    return float(2 * tp / denom)


# ─── Combined Event Metrics ───────────────────────────────────────────────────

def compute_event_metrics(
    y_pred: np.ndarray,
    y_obs: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    """Compute all event metrics for a given threshold.

    IMPORTANT: Only call this when threshold is explicitly configured.
    Do NOT invent a threshold.

    Parameters
    ----------
    y_pred : array-like
        Continuous model predictions.
    y_obs : array-like
        Continuous observations.
    threshold : float
        Alert threshold (must be explicitly provided — never guessed).

    Returns
    -------
    dict
        All event metrics: TP, FP, TN, FN, POD, FAR, CSI,
        precision, recall, F1, threshold.
    """
    ct = contingency_table(y_pred, y_obs, threshold)
    tp, fp, tn, fn = ct["TP"], ct["FP"], ct["TN"], ct["FN"]

    _pod = pod(tp, fn)
    _far = far(tp, fp)
    _csi = csi(tp, fp, fn)
    _prec = precision(tp, fp)
    _rec = recall(tp, fn)
    _f1 = f1_score(tp, fp, fn)

    logger.info(
        "Event metrics @ threshold=%.3f | TP=%d FP=%d TN=%d FN=%d | "
        "POD=%.3f FAR=%.3f CSI=%.3f F1=%.3f",
        threshold, tp, fp, tn, fn, _pod, _far, _csi, _f1,
    )

    return {
        "threshold": threshold,
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "POD": _pod,
        "recall": _rec,   # alias for POD
        "FAR": _far,
        "CSI": _csi,
        "precision": _prec,
        "F1": _f1,
    }
