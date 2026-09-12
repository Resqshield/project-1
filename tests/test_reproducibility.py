"""
tests/test_reproducibility.py
==============================

SOFTWARE REPRODUCIBILITY TEST — ResQShield ML Pipeline

PURPOSE
-------
This test verifies that the ResQShield training pipeline is deterministic:
given the same seed and the same data, running the pipeline twice must
produce identical predictions, metrics, and model parameters.

THIS IS A SOFTWARE QUALITY TEST, NOT A MODEL PERFORMANCE BENCHMARK.

Results here say nothing about real-world flood forecasting performance.
The synthetic data used here is NOT real sensor data.

METHOD
------
1. Generate synthetic sensor data with a fixed seed (seed=42).
2. Run the full feature-engineering + train + predict pipeline twice.
3. Assert:
   - Predictions are identical.
   - Metrics are numerically equivalent.
   - Model parameters are identical.
   - Feature names are identical.
   - A non-empty chronological test set is produced.

SYNTHETIC DATA RATIONALE
------------------------
The resqshield_ml.data.loader.generate_synthetic_sensor_data() function
is used here only for software testing and reproducibility checks.

Synthetic results must never be presented as real ResQShield model
performance.

UPSTREAM REFERENCE
------------------
ECMWFCode4Earth/ml_flood
MATEHIW — ECMWF ESoWC 2019
Authors: @lkugler, @seblehner
License: MIT
https://github.com/ECMWFCode4Earth/ml_flood
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from resqshield_ml.data.loader import (
    chronological_split,
    extract_Xy,
    generate_synthetic_sensor_data,
)
from resqshield_ml.evaluation.metrics import evaluate
from resqshield_ml.features.engineer import build_features
from resqshield_ml.models.flood_model import FloodModel


# =============================================================================
# Shared configuration
# =============================================================================

_SEED = 42

_CFG = {
    "experiment": {
        "name": "reproducibility_test",
        "seed": _SEED,
    },
    "data": {
        "target_col": "water_level_m",
        "timestamp_col": "timestamp",
    },
    "features": {
        "lag_hours": [1, 3, 6],
        "rolling_sum_windows": [3, 6],
        "dynamic_sensor_cols": [
            "rainfall_mm_hr",
            "water_level_m",
            "soil_moisture_pct",
            "upstream_rainfall_mm_hr",
        ],
        "delta_features": [
            {
                "col": "water_level_m",
                "windows": [1, 3],
            }
        ],
        "drop_cols": [],
    },
    "split": {
        # Synthetic fixture covers the full year 2023.
        # June 30 therefore leaves substantial data for both
        # training and chronological testing.
        "train_end": "2023-06-30",
        "val_end": None,
    },
    "model": {
        "kind": "gradient_boosting",
        "gradient_boosting": {
            "n_estimators": 100,
            "max_depth": 4,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "min_samples_split": 10,
            "min_samples_leaf": 5,
            "random_state": _SEED,
        },
    },
    "alert": {
        "warning_level_m": 3.5,
        "danger_level_m": 5.0,
    },
    "evaluation": {
        "regression_metrics": [
            "RMSE",
            "MAE",
            "NSE",
            "R2",
        ],
        # No event-threshold metrics are tested here.
        # Those are covered separately in test_event_metrics.py.
        "classification_metrics": [],
    },
}


# =============================================================================
# Helpers
# =============================================================================

def _set_seed(seed: int) -> None:
    """Reset global randomness before each pipeline run."""
    random.seed(seed)
    np.random.seed(seed)


def _run_pipeline(
    cfg: dict,
) -> tuple[np.ndarray, dict, FloodModel]:
    """
    Run the deterministic synthetic pipeline once.

    Returns
    -------
    tuple
        predictions, metric dictionary, fitted FloodModel
    """
    _set_seed(_SEED)

    # -------------------------------------------------------------------------
    # 1. Generate deterministic synthetic test data
    # -------------------------------------------------------------------------
    # A full year is intentionally used.
    #
    # The previous 2000-hour fixture ended before the configured
    # 2023-06-30 split date, causing the chronological test set
    # to contain zero rows.
    df_raw = generate_synthetic_sensor_data(
        n_hours=24 * 365,
        seed=_SEED,
    )

    assert len(df_raw) > 0, (
        "Synthetic reproducibility fixture unexpectedly produced zero rows."
    )

    # -------------------------------------------------------------------------
    # 2. Feature engineering
    # -------------------------------------------------------------------------
    df_feat = build_features(
        df_raw,
        cfg=cfg,
    )

    assert len(df_feat) > 0, (
        "Feature engineering removed every row from the "
        "synthetic reproducibility fixture."
    )

    # -------------------------------------------------------------------------
    # 3. Chronological split
    # -------------------------------------------------------------------------
    split_cfg = cfg["split"]

    train_df, _, test_df = chronological_split(
        df_feat,
        train_end=split_cfg["train_end"],
        val_end=split_cfg.get("val_end"),
    )

    # Clear sanity checks prevent a long downstream sklearn traceback.
    assert len(train_df) >= 100, (
        "Reproducibility fixture produced too few training rows: "
        f"{len(train_df)}"
    )

    assert len(test_df) >= 100, (
        "Reproducibility fixture produced too few test rows: "
        f"{len(test_df)}. "
        "Check the synthetic timestamp range against split.train_end."
    )

    # -------------------------------------------------------------------------
    # 4. Extract model features / target
    # -------------------------------------------------------------------------
    target_col = cfg["data"]["target_col"]

    X_train, y_train = extract_Xy(
        train_df,
        target_col=target_col,
    )

    X_test, y_test = extract_Xy(
        test_df,
        target_col=target_col,
    )

    assert len(X_train) == len(y_train)
    assert len(X_test) == len(y_test)

    assert len(X_train) >= 100, (
        f"Too few extracted training samples: {len(X_train)}"
    )

    assert len(X_test) >= 100, (
        f"Too few extracted test samples: {len(X_test)}"
    )

    # -------------------------------------------------------------------------
    # 5. Build and train model
    # -------------------------------------------------------------------------
    model_kind = cfg["model"]["kind"]

    model_params = dict(
        cfg["model"][model_kind]
    )

    model = FloodModel(
        kind=model_kind,
        model_params=model_params,
    )

    model.fit(
        X_train,
        y_train,
    )

    # -------------------------------------------------------------------------
    # 6. Predict
    # -------------------------------------------------------------------------
    y_pred = model.predict(
        X_test,
    )

    assert len(y_pred) == len(y_test), (
        "Prediction count does not match test target count."
    )

    # -------------------------------------------------------------------------
    # 7. Evaluate
    # -------------------------------------------------------------------------
    metrics = evaluate(
        y_pred,
        y_test.values,
        cfg=cfg,
        split_name="test",
    )

    return y_pred, metrics, model


# =============================================================================
# Shared reproducibility fixture
# =============================================================================

@pytest.fixture(scope="module")
def two_runs():
    """
    Execute the exact same deterministic pipeline twice.

    Synthetic data is used only for software reproducibility testing.
    """
    run1_preds, run1_metrics, run1_model = _run_pipeline(_CFG)

    run2_preds, run2_metrics, run2_model = _run_pipeline(_CFG)

    return (
        (
            run1_preds,
            run1_metrics,
            run1_model,
        ),
        (
            run2_preds,
            run2_metrics,
            run2_model,
        ),
    )


# =============================================================================
# Reproducibility tests
# =============================================================================

class TestGradientBoostingReproducibility:
    """
    SOFTWARE REPRODUCIBILITY TEST

    Verifies that GradientBoostingRegressor produces deterministic
    results when the same data, configuration, and random seed are used.

    This is not an evaluation of real flood-prediction performance.
    """

    def test_predictions_are_identical(self, two_runs):
        """Predictions must be bit-for-bit identical."""
        (p1, _, _), (p2, _, _) = two_runs

        np.testing.assert_array_equal(
            p1,
            p2,
            err_msg=(
                "SOFTWARE REPRODUCIBILITY FAILURE: "
                "predictions differ between two runs "
                "using the same data and seed."
            ),
        )

    def test_rmse_numerically_equivalent(self, two_runs):
        """RMSE must match across both runs."""
        (_, m1, _), (_, m2, _) = two_runs

        assert "RMSE" in m1, "RMSE missing from run-1 metrics."
        assert "RMSE" in m2, "RMSE missing from run-2 metrics."

        np.testing.assert_allclose(
            m1["RMSE"],
            m2["RMSE"],
            rtol=1e-10,
            atol=1e-12,
            err_msg="RMSE differs between identical runs.",
        )

    def test_mae_numerically_equivalent(self, two_runs):
        """MAE must match across both runs."""
        (_, m1, _), (_, m2, _) = two_runs

        assert "MAE" in m1, "MAE missing from run-1 metrics."
        assert "MAE" in m2, "MAE missing from run-2 metrics."

        np.testing.assert_allclose(
            m1["MAE"],
            m2["MAE"],
            rtol=1e-10,
            atol=1e-12,
            err_msg="MAE differs between identical runs.",
        )

    def test_nse_numerically_equivalent(self, two_runs):
        """NSE must match across both runs."""
        (_, m1, _), (_, m2, _) = two_runs

        assert "NSE" in m1, "NSE missing from run-1 metrics."
        assert "NSE" in m2, "NSE missing from run-2 metrics."

        np.testing.assert_allclose(
            m1["NSE"],
            m2["NSE"],
            rtol=1e-10,
            atol=1e-12,
            err_msg="NSE differs between identical runs.",
        )

    def test_r2_numerically_equivalent(self, two_runs):
        """R² must match across both runs."""
        (_, m1, _), (_, m2, _) = two_runs

        assert "R2" in m1, "R2 missing from run-1 metrics."
        assert "R2" in m2, "R2 missing from run-2 metrics."

        np.testing.assert_allclose(
            m1["R2"],
            m2["R2"],
            rtol=1e-10,
            atol=1e-12,
            err_msg="R2 differs between identical runs.",
        )

    def test_model_params_identical(self, two_runs):
        """Configured model parameters must be identical."""
        (_, _, model1), (_, _, model2) = two_runs

        assert model1.model_params == model2.model_params, (
            "Model parameters differ between identical runs.\n"
            f"Run 1: {model1.model_params}\n"
            f"Run 2: {model2.model_params}"
        )

    def test_model_kind_identical(self, two_runs):
        """Model type must be identical across runs."""
        (_, _, model1), (_, _, model2) = two_runs

        assert model1.kind == model2.kind

    def test_feature_names_identical(self, two_runs):
        """Feature names and ordering must be identical."""
        (_, _, model1), (_, _, model2) = two_runs

        assert model1.feature_names_ == model2.feature_names_, (
            "Feature names differ between runs. "
            "Feature generation or ordering may be non-deterministic."
        )

    def test_prediction_count_positive(self, two_runs):
        """Pipeline must generate actual predictions."""
        (predictions, _, _), _ = two_runs

        assert len(predictions) > 0, (
            "Pipeline produced zero predictions."
        )

    def test_predictions_nonnegative(self, two_runs):
        """
        Water-level predictions must be non-negative.

        FloodModel currently clips negative water-level predictions.
        """
        (predictions, _, _), _ = two_runs

        assert np.all(predictions >= 0.0), (
            "Predictions contain negative water-level values."
        )