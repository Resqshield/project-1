"""
Tests for resqshield_ml.models.flood_model
==========================================
Smoke tests for FloodModel — fit, predict, save, load, feature importance.
These tests use synthetic data only — no real sensor data required.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from resqshield_ml.data.loader import (
    chronological_split,
    extract_Xy,
    generate_synthetic_sensor_data,
)
from resqshield_ml.features.engineer import build_features
from resqshield_ml.models.flood_model import FloodModel, build_model_from_config


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def synthetic_data():
    """Generate synthetic sensor data once for all tests."""
    return generate_synthetic_sensor_data(n_hours=500, seed=42)


@pytest.fixture(scope="module")
def feature_cfg():
    return {
        "data": {"target_col": "water_level_m", "timestamp_col": "timestamp"},
        "features": {
            "lag_hours": [1, 3, 6],
            "rolling_sum_windows": [3, 6],
            "dynamic_sensor_cols": ["rainfall_mm_hr", "water_level_m", "soil_moisture_pct"],
            "delta_features": [{"col": "water_level_m", "windows": [1, 3]}],
            "drop_cols": [],
        },
        "split": {"train_end": "2023-01-15", "val_end": None},
        "model": {
            "kind": "gradient_boosting",  # Use GB so no xgboost required in CI
            "gradient_boosting": {
                "n_estimators": 50,
                "max_depth": 3,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "random_state": 42,
            },
        },
        "alert": {"warning_level_m": 3.5, "danger_level_m": 5.0},
        "evaluation": {
            "regression_metrics": ["RMSE", "MAE", "NSE"],
            "classification_metrics": ["precision", "recall", "f1"],
        },
        "experiment": {"name": "test_experiment"},
        "artifacts": {"model_dir": "artifacts/models", "metrics_dir": "artifacts/metrics"},
    }


@pytest.fixture(scope="module")
def X_train_test(synthetic_data, feature_cfg):
    """Feature engineering + split — computed once."""
    df_feat = build_features(synthetic_data, cfg=feature_cfg)
    train, _, test = chronological_split(
        df_feat,
        train_end="2023-01-15",
        val_end=None,
    )
    target_col = "water_level_m"
    X_train, y_train = extract_Xy(train, target_col=target_col, forecast_horizon=1)
    X_test, y_test = extract_Xy(test, target_col=target_col, forecast_horizon=1)
    return X_train, y_train, X_test, y_test


# ─── FloodModel Tests ─────────────────────────────────────────────────────────

class TestFloodModelInit:
    def test_valid_kind_gb(self):
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        assert m.kind == "gradient_boosting"
        assert not m.is_fitted_

    def test_invalid_kind_raises(self):
        with pytest.raises(ValueError, match="Unsupported model kind"):
            FloodModel("random_forest", {})

    def test_repr_unfitted(self):
        m = FloodModel("gradient_boosting", {"n_estimators": 10})
        assert "not fitted" in repr(m)


class TestFloodModelFit:
    def test_fit_completes(self, X_train_test):
        X_train, y_train, _, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        m.fit(X_train, y_train)
        assert m.is_fitted_

    def test_fit_stores_feature_names(self, X_train_test):
        X_train, y_train, _, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        m.fit(X_train, y_train)
        assert m.feature_names_ is not None
        assert len(m.feature_names_) == X_train.shape[1]

    def test_repr_fitted(self, X_train_test):
        X_train, y_train, _, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        m.fit(X_train, y_train)
        assert "fitted" in repr(m)
        assert "not fitted" not in repr(m)


class TestFloodModelPredict:
    def test_predict_shape(self, X_train_test):
        X_train, y_train, X_test, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        m.fit(X_train, y_train)
        preds = m.predict(X_test)
        assert preds.shape == (len(X_test),)

    def test_predict_nonnegative(self, X_train_test):
        """clip_negative=True (default) should prevent negative predictions."""
        X_train, y_train, X_test, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        m.fit(X_train, y_train)
        preds = m.predict(X_test, clip_negative=True)
        assert (preds >= 0).all()

    def test_predict_before_fit_raises(self, X_train_test):
        _, _, X_test, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10})
        with pytest.raises(RuntimeError, match="not fitted"):
            m.predict(X_test)


class TestFloodModelFeatureImportance:
    def test_importance_returns_dataframe(self, X_train_test):
        X_train, y_train, _, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 20, "random_state": 0})
        m.fit(X_train, y_train)
        fi = m.feature_importance(top_n=5)
        assert isinstance(fi, pd.DataFrame)
        assert "feature" in fi.columns
        assert "importance" in fi.columns
        assert len(fi) <= 5

    def test_importance_sorted_descending(self, X_train_test):
        X_train, y_train, _, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 20, "random_state": 0})
        m.fit(X_train, y_train)
        fi = m.feature_importance(top_n=10)
        assert (fi["importance"].diff().dropna() <= 0).all()


class TestFloodModelSerialization:
    def test_save_and_load(self, X_train_test):
        X_train, y_train, X_test, _ = X_train_test
        m = FloodModel("gradient_boosting", {"n_estimators": 10, "random_state": 0})
        m.fit(X_train, y_train)
        preds_before = m.predict(X_test)

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_path = m.save(tmpdir, name="test_model")
            assert saved_path.exists()
            assert saved_path.suffix == ".joblib"

            loaded = FloodModel.load(saved_path)
            assert loaded.is_fitted_
            preds_after = loaded.predict(X_test)

        np.testing.assert_allclose(preds_before, preds_after)

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            FloodModel.load("/nonexistent/path/model.joblib")


class TestBuildModelFromConfig:
    def test_builds_gb_model(self, feature_cfg):
        m = build_model_from_config(feature_cfg)
        assert isinstance(m, FloodModel)
        assert m.kind == "gradient_boosting"
