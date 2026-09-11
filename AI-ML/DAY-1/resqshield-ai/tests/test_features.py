"""
Tests for resqshield_ml.features.engineer
==========================================
Verifies the feature engineering pipeline using synthetic data.
These tests do NOT require real sensor data.
"""

import numpy as np
import pandas as pd
import pytest

from resqshield_ml.data.loader import generate_synthetic_sensor_data
from resqshield_ml.features.engineer import (
    add_antecedent_precipitation_index,
    add_lag_features,
    add_rate_of_rise,
    add_rolling_features,
    build_features,
)


@pytest.fixture
def sample_df():
    """Small synthetic sensor DataFrame for testing."""
    return generate_synthetic_sensor_data(n_hours=200, seed=0)


class TestLagFeatures:
    def test_basic_lag_created(self, sample_df):
        cols = ["rainfall_mm_hr"]
        df_out = add_lag_features(sample_df, columns=cols, lag_steps=[1, 3])
        assert "rainfall_mm_hr_lag_1" in df_out.columns
        assert "rainfall_mm_hr_lag_3" in df_out.columns

    def test_lag_1_matches_shift(self, sample_df):
        df_out = add_lag_features(sample_df, columns=["water_level_m"], lag_steps=[1])
        # lag_1 at index t should equal original at t-1
        orig = sample_df["water_level_m"]
        lagged = df_out["water_level_m_lag_1"]
        # Compare where both are not NaN (skip first row)
        valid = ~lagged.isna()
        np.testing.assert_allclose(
            lagged[valid].values,
            orig.shift(1)[valid].values,
        )

    def test_zero_lag_not_created(self, sample_df):
        df_out = add_lag_features(sample_df, columns=["rainfall_mm_hr"], lag_steps=[0, 1])
        assert "rainfall_mm_hr_lag_0" not in df_out.columns

    def test_missing_column_skipped(self, sample_df):
        """Should not raise — just log a warning."""
        df_out = add_lag_features(sample_df, columns=["nonexistent_col"], lag_steps=[1])
        assert "nonexistent_col_lag_1" not in df_out.columns

    def test_original_columns_unchanged(self, sample_df):
        orig_cols = set(sample_df.columns)
        df_out = add_lag_features(sample_df, columns=["rainfall_mm_hr"], lag_steps=[2])
        assert orig_cols.issubset(df_out.columns)


class TestRollingFeatures:
    def test_rolling_sum_created(self, sample_df):
        df_out = add_rolling_features(sample_df, columns=["rainfall_mm_hr"], window_steps=[6])
        assert "rainfall_mm_hr_rolling_sum_6" in df_out.columns

    def test_rolling_sum_nonnegative(self, sample_df):
        """Rainfall sum should be >= 0."""
        df_out = add_rolling_features(sample_df, columns=["rainfall_mm_hr"], window_steps=[6])
        assert (df_out["rainfall_mm_hr_rolling_sum_6"] >= 0).all()

    def test_invalid_func_raises(self, sample_df):
        with pytest.raises(ValueError, match="Invalid aggregation function"):
            add_rolling_features(sample_df, columns=["rainfall_mm_hr"],
                                 window_steps=[3], func="median_bad")


class TestRateOfRise:
    def test_delta_created(self, sample_df):
        df_out = add_rate_of_rise(sample_df, level_col="water_level_m", delta_windows=[1, 3])
        assert "water_level_m_delta_1" in df_out.columns
        assert "water_level_m_delta_3" in df_out.columns

    def test_delta_1_correct(self, sample_df):
        df_out = add_rate_of_rise(sample_df, level_col="water_level_m", delta_windows=[1])
        expected = sample_df["water_level_m"] - sample_df["water_level_m"].shift(1)
        pd.testing.assert_series_equal(
            df_out["water_level_m_delta_1"], expected,
            check_names=False
        )

    def test_missing_column_skipped(self, sample_df):
        df_out = add_rate_of_rise(sample_df, level_col="nonexistent_level")
        assert df_out.equals(sample_df)


class TestAntecedentPrecipitationIndex:
    def test_api_created(self, sample_df):
        df_out = add_antecedent_precipitation_index(sample_df)
        assert "antecedent_precipitation_index" in df_out.columns

    def test_api_nonnegative(self, sample_df):
        df_out = add_antecedent_precipitation_index(sample_df)
        assert (df_out["antecedent_precipitation_index"] >= 0).all()

    def test_api_monotone_increase_after_rain(self):
        """API should increase when it rains continuously."""
        idx = pd.date_range("2024-01-01", periods=10, freq="h")
        df = pd.DataFrame({"rainfall_mm_hr": [10.0] * 10}, index=idx)
        df_out = add_antecedent_precipitation_index(df, decay_factor=0.9)
        api = df_out["antecedent_precipitation_index"].values
        # Each step: api[t] = 0.9 * api[t-1] + 10  → increasing series
        assert all(api[t] > api[t - 1] for t in range(1, len(api)))


class TestBuildFeaturesPipeline:
    def test_build_features_runs(self, sample_df):
        """Smoke test: pipeline should not crash with a minimal config."""
        minimal_cfg = {
            "data": {"target_col": "water_level_m"},
            "features": {
                "lag_hours": [1, 3],
                "rolling_sum_windows": [6],
                "dynamic_sensor_cols": ["rainfall_mm_hr", "water_level_m"],
                "delta_features": [{"col": "water_level_m", "windows": [1]}],
                "drop_cols": [],
            },
        }
        df_out = build_features(sample_df, cfg=minimal_cfg)
        assert len(df_out) == len(sample_df)
        assert "rainfall_mm_hr_lag_1" in df_out.columns
        assert "antecedent_precipitation_index" in df_out.columns
        assert "water_level_m_delta_1" in df_out.columns

    def test_no_data_loss(self, sample_df):
        """Row count must not change during feature engineering."""
        minimal_cfg = {
            "data": {"target_col": "water_level_m"},
            "features": {
                "lag_hours": [1],
                "rolling_sum_windows": [3],
                "dynamic_sensor_cols": ["rainfall_mm_hr"],
                "delta_features": [],
                "drop_cols": [],
            },
        }
        df_out = build_features(sample_df, cfg=minimal_cfg)
        assert len(df_out) == len(sample_df)
