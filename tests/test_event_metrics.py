"""
tests/test_event_metrics.py
============================
Unit tests for resqshield_ml.evaluation.event_metrics.

Tests are based on manually computed expected values using known
contingency tables, so results can be verified by hand.

Metric formulas (as specified in B22 requirements):
    POD = TP / (TP + FN)
    FAR = FP / (TP + FP)
    CSI = TP / (TP + FP + FN)
    precision = TP / (TP + FP)
    F1  = 2*TP / (2*TP + FP + FN)

IMPORTANT:
- Event metrics ONLY run when a threshold is explicitly provided.
- No flood threshold is invented here.
- All thresholds in these tests are given explicitly as test parameters.

Attribution (MIT License):
    ECMWFCode4Earth/ml_flood — MATEHIW, ESoWC 2019
    Authors: @lkugler, @seblehner
    URL: https://github.com/ECMWFCode4Earth/ml_flood
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from resqshield_ml.evaluation.event_metrics import (
    compute_event_metrics,
    contingency_table,
    csi,
    f1_score,
    far,
    pod,
    precision,
    recall,
)


# ─── Contingency Table Tests ──────────────────────────────────────────────────

class TestContingencyTable:
    """
    Manually constructed examples — values verified by hand.

    Example A:
        obs  = [0, 0, 1, 1, 1, 0, 1, 0]  (>=2.0 is a flood event)
        pred = [0, 1, 1, 1, 0, 0, 1, 0]  (>=2.0 is predicted flood)
        threshold = 2.0

    Working:
        obs_event  = [F, F, T, T, T, F, T, F]
        pred_event = [F, T, T, T, F, F, T, F]

        TP: pred=T & obs=T → indices 2,3,6          → TP = 3
        FP: pred=T & obs=F → index   1               → FP = 1
        FN: pred=F & obs=T → index   4               → FN = 1
        TN: pred=F & obs=F → indices 0,5,7           → TN = 3
    """

    @pytest.fixture
    def example_a(self):
        obs  = np.array([0.0, 0.0, 5.0, 4.0, 3.5, 1.0, 6.0, 0.5])
        pred = np.array([0.0, 3.0, 5.0, 4.0, 1.0, 0.5, 6.0, 0.3])
        threshold = 2.0
        return obs, pred, threshold

    def test_example_a_tp(self, example_a):
        obs, pred, thresh = example_a
        ct = contingency_table(pred, obs, thresh)
        assert ct["TP"] == 3, f"Expected TP=3, got {ct['TP']}"

    def test_example_a_fp(self, example_a):
        obs, pred, thresh = example_a
        ct = contingency_table(pred, obs, thresh)
        assert ct["FP"] == 1, f"Expected FP=1, got {ct['FP']}"

    def test_example_a_fn(self, example_a):
        obs, pred, thresh = example_a
        ct = contingency_table(pred, obs, thresh)
        assert ct["FN"] == 1, f"Expected FN=1, got {ct['FN']}"

    def test_example_a_tn(self, example_a):
        obs, pred, thresh = example_a
        ct = contingency_table(pred, obs, thresh)
        assert ct["TN"] == 3, f"Expected TN=3, got {ct['TN']}"

    def test_contingency_counts_sum_to_n(self, example_a):
        """TP+FP+TN+FN must equal total number of samples."""
        obs, pred, thresh = example_a
        ct = contingency_table(pred, obs, thresh)
        total = ct["TP"] + ct["FP"] + ct["TN"] + ct["FN"]
        assert total == len(obs), f"Contingency counts sum to {total}, expected {len(obs)}"

    def test_perfect_prediction(self):
        """Perfect model: TP=N, FP=0, FN=0, TN=0 (all events)."""
        obs  = np.array([3.0, 4.0, 5.0, 1.0])
        pred = np.array([3.0, 4.0, 5.0, 1.0])
        ct = contingency_table(pred, obs, threshold=2.5)
        assert ct["TP"] == 3
        assert ct["FP"] == 0
        assert ct["FN"] == 0
        assert ct["TN"] == 1

    def test_no_events_observed(self):
        """When no events are observed, TP=0 and FN=0."""
        obs  = np.array([0.5, 1.0, 0.2])
        pred = np.array([0.5, 3.0, 0.2])
        ct = contingency_table(pred, obs, threshold=2.0)
        assert ct["TP"] == 0
        assert ct["FN"] == 0
        assert ct["FP"] == 1
        assert ct["TN"] == 2

    def test_all_missed(self):
        """Model predicts no events but all are events: FN=N, TP=0."""
        obs  = np.array([3.0, 4.0, 5.0])
        pred = np.array([0.5, 0.5, 0.5])
        ct = contingency_table(pred, obs, threshold=2.0)
        assert ct["TP"] == 0
        assert ct["FN"] == 3
        assert ct["FP"] == 0
        assert ct["TN"] == 0


# ─── Individual Metric Tests ──────────────────────────────────────────────────

class TestPOD:
    """
    POD = TP / (TP + FN)
    Verified manually.
    """

    def test_pod_typical(self):
        # TP=3, FN=1  →  POD = 3/4 = 0.75
        result = pod(tp=3, fn=1)
        assert abs(result - 0.75) < 1e-10, f"Expected 0.75, got {result}"

    def test_pod_perfect(self):
        # TP=5, FN=0  →  POD = 1.0
        result = pod(tp=5, fn=0)
        assert result == 1.0

    def test_pod_zero(self):
        # TP=0, FN=3  →  POD = 0.0
        result = pod(tp=0, fn=3)
        assert result == 0.0

    def test_pod_no_events_returns_nan(self):
        # TP=0, FN=0  →  undefined, should return NaN
        result = pod(tp=0, fn=0)
        assert math.isnan(result), f"Expected NaN, got {result}"

    def test_pod_matches_recall(self):
        """recall() is an alias for pod()."""
        assert pod(tp=4, fn=2) == recall(tp=4, fn=2)


class TestFAR:
    """
    FAR = FP / (TP + FP)
    Verified manually.
    """

    def test_far_typical(self):
        # FP=1, TP=3  →  FAR = 1/4 = 0.25
        result = far(tp=3, fp=1)
        assert abs(result - 0.25) < 1e-10, f"Expected 0.25, got {result}"

    def test_far_zero(self):
        # FP=0, TP=5  →  FAR = 0.0
        result = far(tp=5, fp=0)
        assert result == 0.0

    def test_far_all_false_alarms(self):
        # TP=0, FP=3  →  FAR = 1.0
        result = far(tp=0, fp=3)
        assert result == 1.0

    def test_far_no_predictions_returns_nan(self):
        # TP=0, FP=0  →  undefined
        result = far(tp=0, fp=0)
        assert math.isnan(result)


class TestCSI:
    """
    CSI = TP / (TP + FP + FN)
    Verified manually.
    """

    def test_csi_typical(self):
        # TP=3, FP=1, FN=1  →  CSI = 3/5 = 0.6
        result = csi(tp=3, fp=1, fn=1)
        assert abs(result - 0.6) < 1e-10, f"Expected 0.6, got {result}"

    def test_csi_perfect(self):
        # TP=5, FP=0, FN=0  →  CSI = 1.0
        result = csi(tp=5, fp=0, fn=0)
        assert result == 1.0

    def test_csi_zero_events(self):
        # TP=0, FP=0, FN=0  →  NaN
        result = csi(tp=0, fp=0, fn=0)
        assert math.isnan(result)

    def test_csi_worst_case(self):
        # TP=0, FP=2, FN=3  →  CSI = 0.0
        result = csi(tp=0, fp=2, fn=3)
        assert result == 0.0


class TestPrecision:
    """
    precision = TP / (TP + FP)
    Verified manually.
    """

    def test_precision_typical(self):
        # TP=3, FP=1  →  precision = 3/4 = 0.75
        result = precision(tp=3, fp=1)
        assert abs(result - 0.75) < 1e-10, f"Expected 0.75, got {result}"

    def test_precision_perfect(self):
        result = precision(tp=5, fp=0)
        assert result == 1.0

    def test_precision_zero(self):
        result = precision(tp=0, fp=3)
        assert result == 0.0

    def test_precision_no_positives_returns_nan(self):
        result = precision(tp=0, fp=0)
        assert math.isnan(result)


class TestF1:
    """
    F1 = 2*TP / (2*TP + FP + FN)
    Verified manually.
    """

    def test_f1_typical(self):
        # TP=3, FP=1, FN=1  →  F1 = 6/8 = 0.75
        result = f1_score(tp=3, fp=1, fn=1)
        assert abs(result - 0.75) < 1e-10, f"Expected 0.75, got {result}"

    def test_f1_perfect(self):
        # TP=5, FP=0, FN=0  →  F1 = 1.0
        result = f1_score(tp=5, fp=0, fn=0)
        assert result == 1.0

    def test_f1_zero(self):
        # TP=0, FP=1, FN=1  →  F1 = 0/4 = 0.0
        result = f1_score(tp=0, fp=1, fn=1)
        assert result == 0.0

    def test_f1_zero_denominator_returns_nan(self):
        # TP=0, FP=0, FN=0  →  NaN
        result = f1_score(tp=0, fp=0, fn=0)
        assert math.isnan(result)

    def test_f1_formula_consistency(self):
        """F1 must equal the harmonic mean of precision and recall."""
        tp, fp, fn = 4, 2, 1
        prec = precision(tp, fp)
        rec  = recall(tp, fn)
        f1_harmonic = 2 * prec * rec / (prec + rec)
        result = f1_score(tp, fp, fn)
        assert abs(result - f1_harmonic) < 1e-10


# ─── Combined compute_event_metrics Tests ────────────────────────────────────

class TestComputeEventMetrics:
    """
    Integration-level tests using compute_event_metrics().
    All values verified by hand against the example_a scenario.

    Example A (repeated from TestContingencyTable):
        obs  = [0, 0, 5, 4, 3.5, 1, 6, 0.5]
        pred = [0, 3, 5, 4, 1.0, 0.5, 6, 0.3]
        threshold = 2.0

        TP=3, FP=1, FN=1, TN=3
        POD       = 3/4  = 0.75
        FAR       = 1/4  = 0.25
        CSI       = 3/5  = 0.60
        precision = 3/4  = 0.75
        F1        = 6/8  = 0.75
    """

    @pytest.fixture
    def result_a(self):
        obs  = np.array([0.0, 0.0, 5.0, 4.0, 3.5, 1.0, 6.0, 0.5])
        pred = np.array([0.0, 3.0, 5.0, 4.0, 1.0, 0.5, 6.0, 0.3])
        # threshold=2.0 is explicitly provided, never invented
        return compute_event_metrics(pred, obs, threshold=2.0)

    def test_tp(self, result_a):
        assert result_a["TP"] == 3

    def test_fp(self, result_a):
        assert result_a["FP"] == 1

    def test_tn(self, result_a):
        assert result_a["TN"] == 3

    def test_fn(self, result_a):
        assert result_a["FN"] == 1

    def test_pod_value(self, result_a):
        assert abs(result_a["POD"] - 0.75) < 1e-10

    def test_far_value(self, result_a):
        assert abs(result_a["FAR"] - 0.25) < 1e-10

    def test_csi_value(self, result_a):
        assert abs(result_a["CSI"] - 0.60) < 1e-10

    def test_precision_value(self, result_a):
        assert abs(result_a["precision"] - 0.75) < 1e-10

    def test_f1_value(self, result_a):
        assert abs(result_a["F1"] - 0.75) < 1e-10

    def test_recall_equals_pod(self, result_a):
        """recall key must equal POD key (they are the same metric)."""
        assert result_a["recall"] == result_a["POD"]

    def test_threshold_recorded(self, result_a):
        """The threshold used must be recorded in the output."""
        assert result_a["threshold"] == 2.0

    def test_all_keys_present(self, result_a):
        """All expected keys must be present in the result dict."""
        required_keys = {"TP", "FP", "TN", "FN", "POD", "FAR", "CSI",
                         "precision", "recall", "F1", "threshold"}
        assert required_keys.issubset(result_a.keys()), (
            f"Missing keys: {required_keys - result_a.keys()}"
        )
