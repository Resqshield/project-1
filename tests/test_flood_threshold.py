"""
Tests for resqshield_ml.baselines.flood_threshold (T09).

Flash-flood explainable threshold baseline.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from resqshield_ml.baselines.flood_threshold import (
    ConditionName,
    FloodAssessment,
    FloodThresholdBaseline,
    FloodThresholdsNotCalibratedError,
    Severity,
)


# ══════════════════════════════════════════════════════════════════════════════
# SOFTWARE TEST THRESHOLDS — NOT OPERATIONAL THRESHOLDS
#
# The numeric values below are used ONLY for automated testing of the
# flash-flood threshold model's software logic.
#
# They are NOT calibrated to any real-world CWC station, catchment,
# rainfall climatology, or hydrological study.
#
# For operational deployment, all thresholds must be calibrated using:
#   - CWC Warning Level (WL) and Danger Level (DL) for the specific station
#     from aff.india-water.gov.in (verified per-station)
#   - Rainfall thresholds from IMD district-level statistics
#   - Rate-of-rise thresholds from catchment response time analysis
#
# Setting configs/flood_threshold.yaml values from these test numbers
# is STRICTLY PROHIBITED.
# ══════════════════════════════════════════════════════════════════════════════

TEST_THRESHOLDS = {
    "rainfall_1h": {
        "low": 10.0,        # mm — SOFTWARE TEST VALUE ONLY
        "moderate": 25.0,   # mm — SOFTWARE TEST VALUE ONLY
        "high": 50.0,       # mm — SOFTWARE TEST VALUE ONLY
    },
    "rainfall_3h": {
        "low": 20.0,        # mm — SOFTWARE TEST VALUE ONLY
        "moderate": 50.0,   # mm — SOFTWARE TEST VALUE ONLY
        "high": 100.0,      # mm — SOFTWARE TEST VALUE ONLY
    },
    "rainfall_6h": {
        "low": 30.0,        # mm — SOFTWARE TEST VALUE ONLY
        "moderate": 75.0,   # mm — SOFTWARE TEST VALUE ONLY
        "high": 150.0,      # mm — SOFTWARE TEST VALUE ONLY
    },
    "rainfall_12h": {
        "low": 50.0,        # mm — SOFTWARE TEST VALUE ONLY
        "moderate": 100.0,  # mm — SOFTWARE TEST VALUE ONLY
        "high": 200.0,      # mm — SOFTWARE TEST VALUE ONLY
    },
    "rainfall_24h": {
        "low": 75.0,        # mm — SOFTWARE TEST VALUE ONLY
        "moderate": 150.0,  # mm — SOFTWARE TEST VALUE ONLY
        "high": 300.0,      # mm — SOFTWARE TEST VALUE ONLY
    },
    "antecedent_wetness": {
        "moderate": 40.0,   # API — SOFTWARE TEST VALUE ONLY
        "high": 80.0,       # API — SOFTWARE TEST VALUE ONLY
    },
    "water_level": {
        "warning_level_m": 5.0,    # m — SOFTWARE TEST VALUE ONLY
        "danger_level_m": 7.0,     # m — SOFTWARE TEST VALUE ONLY
        "hfl_m": 10.0,             # m — SOFTWARE TEST VALUE ONLY
    },
    "rate_of_rise": {
        "warning_m_per_hr": 0.3,   # m/hr — SOFTWARE TEST VALUE ONLY
        "critical_m_per_hr": 0.8,  # m/hr — SOFTWARE TEST VALUE ONLY
    },
}


@pytest.fixture
def model():
    """FloodThresholdBaseline with test thresholds."""
    return FloodThresholdBaseline(thresholds=TEST_THRESHOLDS)


def _row(**kwargs) -> pd.DataFrame:
    """Create a single-row DataFrame from keyword arguments."""
    return pd.DataFrame([kwargs])


# ─── Calibration Validation ──────────────────────────────────────────────────

class TestCalibrationValidation:
    """Verify null thresholds are rejected."""

    def test_all_null_raises(self):
        nulls = {k: {sub: None for sub in v} for k, v in TEST_THRESHOLDS.items()}
        with pytest.raises(FloodThresholdsNotCalibratedError, match="not calibrated"):
            FloodThresholdBaseline(thresholds=nulls)

    def test_one_null_raises(self):
        t = copy.deepcopy(TEST_THRESHOLDS)
        t["water_level"]["danger_level_m"] = None
        with pytest.raises(FloodThresholdsNotCalibratedError):
            FloodThresholdBaseline(thresholds=t)

    def test_from_config_null_raises(self):
        t = copy.deepcopy(TEST_THRESHOLDS)
        t["rate_of_rise"]["critical_m_per_hr"] = None
        with pytest.raises(FloodThresholdsNotCalibratedError):
            FloodThresholdBaseline.from_config({"thresholds": t})

    def test_from_config_missing_section_raises(self):
        with pytest.raises(FloodThresholdsNotCalibratedError):
            FloodThresholdBaseline.from_config({})

    def test_calibrated_succeeds(self):
        model = FloodThresholdBaseline(thresholds=TEST_THRESHOLDS)
        assert model is not None

    def test_calibrated_from_config_succeeds(self):
        model = FloodThresholdBaseline.from_config({"thresholds": TEST_THRESHOLDS})
        assert model is not None


# ─── Production Config Validation ────────────────────────────────────────────

class TestProductionConfig:
    """configs/flood_threshold.yaml must have all-null thresholds."""

    def test_production_config_raises_uncalibrated(self):
        from resqshield_ml.utils.config import load_config
        cfg = load_config("configs/flood_threshold.yaml")
        with pytest.raises(FloodThresholdsNotCalibratedError):
            FloodThresholdBaseline.from_config(cfg)


# ─── fit() No-Op ─────────────────────────────────────────────────────────────

class TestFit:

    def test_fit_returns_self(self, model):
        assert model.fit() is model

    def test_fit_with_xy_returns_self(self, model):
        df = _row(rainfall_mm_hr=10.0)
        assert model.fit(X=df, y=pd.Series([1])) is model


# ─── Rainfall Accumulation Conditions ────────────────────────────────────────

class TestRainfallConditions:
    """Test cumulative rainfall trigger logic."""

    def test_high_rainfall_1h_triggers(self, model):
        """1h rainfall above high threshold triggers HIGH."""
        df = _row(rainfall_mm_hr_rolling_sum_1=60.0)  # > 50
        assessments = model.predict_explained(df)
        cond = next(
            c for c in assessments[0].conditions
            if c.name == ConditionName.RAINFALL_1H.value
        )
        assert cond.severity == Severity.HIGH
        assert cond.fired is True

    def test_moderate_rainfall_1h_triggers(self, model):
        """1h rainfall at moderate threshold → MODERATE, triggered."""
        df = _row(rainfall_mm_hr_rolling_sum_1=30.0)  # >= 25
        assessments = model.predict_explained(df)
        cond = next(
            c for c in assessments[0].conditions
            if c.name == ConditionName.RAINFALL_1H.value
        )
        assert cond.severity == Severity.MODERATE
        assert cond.fired is True

    def test_low_rainfall_1h_not_triggered(self, model):
        """1h rainfall at LOW severity does not trigger (watch only)."""
        df = _row(rainfall_mm_hr_rolling_sum_1=12.0)  # >= 10 but < 25
        assessments = model.predict_explained(df)
        cond = next(
            c for c in assessments[0].conditions
            if c.name == ConditionName.RAINFALL_1H.value
        )
        assert cond.severity == Severity.LOW
        assert cond.fired is False
        assert assessments[0].risk_level == Severity.NONE

    def test_no_rainfall_no_trigger(self, model):
        df = _row(rainfall_mm_hr_rolling_sum_1=0.0)
        preds = model.predict(df)
        assert preds[0] == Severity.NONE

    def test_rainfall_6h_moderate_triggers(self, model):
        """6h cumulative rainfall at moderate → MODERATE risk."""
        df = _row(rainfall_mm_hr_rolling_sum_6=80.0)  # >= 75
        assessments = model.predict_explained(df)
        assert assessments[0].risk_level == Severity.MODERATE

    def test_rainfall_24h_high_triggers(self, model):
        """24h cumulative rainfall above high → HIGH risk."""
        df = _row(rainfall_mm_hr_rolling_sum_24=320.0)  # >= 300
        assessments = model.predict_explained(df)
        assert assessments[0].risk_level >= Severity.HIGH


# ─── Water Level Conditions ───────────────────────────────────────────────────

class TestWaterLevelConditions:
    """Test water level state conditions."""

    def test_above_danger_level_triggers_high(self, model):
        """Water level above DL triggers HIGH."""
        df = _row(water_level_m=8.0)  # >= 7.0 (danger)
        preds = model.predict(df)
        assert preds[0] == Severity.HIGH

    def test_above_warning_level_triggers_moderate(self, model):
        """Water level above WL triggers MODERATE."""
        df = _row(water_level_m=5.5)  # >= 5.0 (warning), < 7.0 (danger)
        preds = model.predict(df)
        assert preds[0] == Severity.MODERATE

    def test_at_hfl_triggers_extreme(self, model):
        """Water at/above HFL triggers EXTREME."""
        df = _row(water_level_m=10.0)  # >= 10.0 (HFL)
        preds = model.predict(df)
        assert preds[0] == Severity.EXTREME

    def test_below_warning_no_trigger(self, model):
        """Water level below WL → no trigger."""
        df = _row(water_level_m=4.9)  # < 5.0
        preds = model.predict(df)
        assert preds[0] == Severity.NONE


# ─── Rate of Rise Conditions ──────────────────────────────────────────────────

class TestRateOfRise:

    def test_critical_rate_triggers_extreme(self, model):
        """Rate >= critical triggers EXTREME."""
        df = _row(water_level_m_delta_1=1.0)  # >= 0.8
        preds = model.predict(df)
        assert preds[0] == Severity.EXTREME

    def test_warning_rate_triggers_high(self, model):
        """Rate >= warning triggers HIGH."""
        df = _row(water_level_m_delta_1=0.5)  # >= 0.3
        preds = model.predict(df)
        assert preds[0] == Severity.HIGH

    def test_slow_rise_no_trigger(self, model):
        """Rate below warning → LOW (watch) but no trigger."""
        df = _row(water_level_m_delta_1=0.1)
        preds = model.predict(df)
        assert preds[0] == Severity.NONE

    def test_falling_no_trigger(self, model):
        """Negative rate → NONE."""
        df = _row(water_level_m_delta_1=-0.5)
        preds = model.predict(df)
        assert preds[0] == Severity.NONE


# ─── Antecedent Wetness Amplification ────────────────────────────────────────

class TestAntecedentAmplification:

    def test_high_api_triggers_and_amplifies(self, model):
        """HIGH antecedent wetness (>=HIGH threshold) is a trigger itself AND
        causes amplification.  Combined with MODERATE rainfall, the base_risk is
        max(MODERATE, HIGH) = HIGH, then +1 amplification → EXTREME.
        """
        df = _row(
            rainfall_mm_hr_rolling_sum_1=30.0,  # MODERATE trigger
            antecedent_precipitation_index=90.0,  # HIGH trigger (>=80) + amplifier
        )
        preds = model.predict(df)
        # HIGH antecedent is a trigger → base_risk = max(MODERATE, HIGH) = HIGH
        # HIGH antecedent also amplifies → HIGH + 1 = EXTREME
        assert preds[0] == Severity.EXTREME

    def test_moderate_api_triggers_no_amplification(self, model):
        """MODERATE antecedent wetness is a trigger but does NOT amplify.
        Amplification requires severity >= HIGH.
        """
        df = _row(
            rainfall_mm_hr_rolling_sum_1=30.0,  # MODERATE trigger
            antecedent_precipitation_index=50.0,  # MODERATE trigger (>=40, <80)
        )
        preds = model.predict(df)
        # Both rainfall and antecedent contribute MODERATE
        # No amplification (antecedent is MODERATE, not HIGH)
        # base_risk = max(MODERATE, MODERATE) = MODERATE
        assert preds[0] == Severity.MODERATE

    def test_high_api_alone_is_trigger(self, model):
        """HIGH antecedent wetness alone (no rainfall) triggers HIGH."""
        df = _row(
            antecedent_precipitation_index=90.0,  # HIGH trigger + amplifier
        )
        preds = model.predict(df)
        # base_risk = HIGH (antecedent), amplified + 1 = EXTREME
        assert preds[0] == Severity.EXTREME

    def test_extreme_capped_at_extreme(self, model):
        """EXTREME + saturated → still EXTREME (cap)."""
        df = _row(
            rainfall_mm_hr_rolling_sum_1=60.0,  # HIGH
            antecedent_precipitation_index=90.0,  # HIGH
        )
        preds = model.predict(df)
        assert preds[0] == Severity.EXTREME


# ─── Triggered Rules and Missing Inputs ──────────────────────────────────────

class TestTriggeredRulesAndMissingInputs:

    def test_triggered_rules_populated(self, model):
        """Triggered conditions should appear in triggered_rules."""
        df = _row(rainfall_mm_hr_rolling_sum_1=60.0)
        assessments = model.predict_explained(df)
        assert len(assessments[0].triggered_rules) > 0
        assert ConditionName.RAINFALL_1H.value in assessments[0].triggered_rules

    def test_no_trigger_empty_triggered_rules(self, model):
        """No condition triggered → empty triggered_rules."""
        df = _row(rainfall_mm_hr_rolling_sum_1=5.0)
        assessments = model.predict_explained(df)
        assert len(assessments[0].triggered_rules) == 0

    def test_missing_inputs_recorded(self, model):
        """Absent input columns appear in missing_inputs."""
        df = _row(rainfall_mm_hr_rolling_sum_1=30.0)
        assessments = model.predict_explained(df)
        # water_level_m column absent → should be in missing_inputs
        assert "water_level_m" in assessments[0].missing_inputs

    def test_all_inputs_no_missing(self, model):
        """Full input row → no missing inputs."""
        df = _row(
            rainfall_mm_hr=5.0,
            rainfall_mm_hr_rolling_sum_1=5.0,
            rainfall_mm_hr_rolling_sum_3=10.0,
            rainfall_mm_hr_rolling_sum_6=15.0,
            rainfall_mm_hr_rolling_sum_12=25.0,
            rainfall_mm_hr_rolling_sum_24=40.0,
            antecedent_precipitation_index=30.0,
            water_level_m=3.0,
            water_level_m_delta_1=0.05,
        )
        assessments = model.predict_explained(df)
        assert len(assessments[0].missing_inputs) == 0


# ─── Explainability Interface ─────────────────────────────────────────────────

class TestExplainability:

    def test_explanation_keys_are_condition_names(self, model):
        df = _row(
            rainfall_mm_hr_rolling_sum_1=30.0,
            water_level_m=5.5,
        )
        a = model.predict_explained(df)[0]
        for key in a.explanation:
            assert isinstance(key, str)
            assert len(key) > 0

    def test_reasons_are_non_empty_strings(self, model):
        df = _row(rainfall_mm_hr_rolling_sum_6=80.0, water_level_m=6.0)
        a = model.predict_explained(df)[0]
        for cond in a.conditions:
            assert isinstance(cond.reason, str)
            assert len(cond.reason) > 0

    def test_assessment_type(self, model):
        df = _row(rainfall_mm_hr_rolling_sum_1=30.0)
        a = model.predict_explained(df)[0]
        assert isinstance(a, FloodAssessment)
        assert isinstance(a.risk_level, Severity)


# ─── Edge Cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_dataframe(self, model):
        df = pd.DataFrame(columns=["rainfall_mm_hr_rolling_sum_1"])
        preds = model.predict(df)
        assert len(preds) == 0

    def test_all_nan_inputs(self, model):
        df = _row(
            rainfall_mm_hr_rolling_sum_1=float("nan"),
            water_level_m=float("nan"),
        )
        preds = model.predict(df)
        assert preds[0] == Severity.NONE

    def test_unrecognised_columns_ignored(self, model):
        df = _row(unrelated_col=42.0)
        preds = model.predict(df)
        assert preds[0] == Severity.NONE

    def test_multiple_rows_batch(self, model):
        df = pd.DataFrame([
            {"rainfall_mm_hr_rolling_sum_1": 0.0},     # NONE
            {"rainfall_mm_hr_rolling_sum_1": 30.0},    # MODERATE
            {"rainfall_mm_hr_rolling_sum_1": 60.0},    # HIGH
        ])
        preds = model.predict(df)
        assert len(preds) == 3
        assert preds[0] == Severity.NONE
        assert preds[1] == Severity.MODERATE
        assert preds[2] == Severity.HIGH

    def test_combined_rainfall_and_water_level(self, model):
        """Multiple simultaneous conditions — risk = max of all."""
        df = _row(
            rainfall_mm_hr_rolling_sum_1=30.0,  # MODERATE
            water_level_m=8.0,                   # HIGH (above DL)
        )
        preds = model.predict(df)
        assert preds[0] == Severity.HIGH


# ─── repr ─────────────────────────────────────────────────────────────────────

class TestRepr:

    def test_repr_is_informative(self, model):
        r = repr(model)
        assert "FloodThresholdBaseline" in r


# ─── Comparison Harness Smoke Test ────────────────────────────────────────────

class TestComparisonHarnessSmoke:
    """Smoke test of the compare_flood_baselines harness.

    Uses SYNTHETIC DATA for pipeline validation only.
    Metrics from this test MUST NOT be presented as operational performance.
    """

    @pytest.fixture
    def synthetic_data(self):
        """Generate minimal synthetic train/test split.

        SYNTHETIC TEST DATA — NOT REAL CWC DATA.
        """
        from resqshield_ml.data.loader import generate_synthetic_sensor_data
        from resqshield_ml.evaluation.compare_flood_baselines import (
            engineer_flood_features,
        )

        df = generate_synthetic_sensor_data(n_hours=500, seed=42)
        df = engineer_flood_features(df)
        split = int(0.8 * len(df))
        return df.iloc[:split], df.iloc[split:]

    def test_comparison_returns_dict(self, synthetic_data):
        from resqshield_ml.evaluation.compare_flood_baselines import (
            compare_flood_baselines,
        )
        train_df, test_df = synthetic_data
        report = compare_flood_baselines(
            df_train=train_df,
            df_test=test_df,
            target_col="water_level_m",
            forecast_horizon=1,
            validated_threshold_m=None,   # Event metrics disabled
        )
        assert isinstance(report, dict)
        assert "models" in report

    def test_gb_and_xgb_in_report(self, synthetic_data):
        from resqshield_ml.evaluation.compare_flood_baselines import (
            compare_flood_baselines,
        )
        train_df, test_df = synthetic_data
        report = compare_flood_baselines(
            df_train=train_df,
            df_test=test_df,
            forecast_horizon=1,
            validated_threshold_m=None,
        )
        assert "gradient_boosting" in report["models"]
        assert "xgboost" in report["models"]

    def test_event_metrics_disabled_flag(self, synthetic_data):
        from resqshield_ml.evaluation.compare_flood_baselines import (
            compare_flood_baselines,
        )
        train_df, test_df = synthetic_data
        report = compare_flood_baselines(
            df_train=train_df, df_test=test_df, validated_threshold_m=None,
        )
        assert report["event_metrics_disabled"] is True

    def test_regression_metrics_present(self, synthetic_data):
        from resqshield_ml.evaluation.compare_flood_baselines import (
            compare_flood_baselines,
        )
        train_df, test_df = synthetic_data
        report = compare_flood_baselines(
            df_train=train_df, df_test=test_df, validated_threshold_m=None,
        )
        gb = report["models"]["gradient_boosting"]
        for metric in ["RMSE", "MAE", "R2", "NSE"]:
            assert metric in gb, f"Missing metric: {metric}"

    def test_format_report_returns_string(self, synthetic_data):
        from resqshield_ml.evaluation.compare_flood_baselines import (
            compare_flood_baselines,
            format_comparison_report,
        )
        train_df, test_df = synthetic_data
        report = compare_flood_baselines(
            df_train=train_df, df_test=test_df, validated_threshold_m=None,
        )
        s = format_comparison_report(report)
        assert isinstance(s, str)
        assert "RMSE" in s

    def test_event_metrics_enabled_when_threshold_provided(self, synthetic_data):
        """When validated_threshold_m is set, event metrics appear in output.

        NOTE: threshold value here is a SOFTWARE TEST VALUE ONLY.
        Not calibrated to any real station.
        """
        from resqshield_ml.evaluation.compare_flood_baselines import (
            compare_flood_baselines,
        )
        train_df, test_df = synthetic_data
        # SOFTWARE TEST THRESHOLD — NOT OPERATIONAL
        report = compare_flood_baselines(
            df_train=train_df,
            df_test=test_df,
            validated_threshold_m=3.0,  # SOFTWARE TEST THRESHOLD — NOT OPERATIONAL
        )
        assert report["event_metrics_disabled"] is False
        gb = report["models"]["gradient_boosting"]
        assert "event_metrics" in gb
        for key in ["POD", "FAR", "CSI", "F1"]:
            assert key in gb["event_metrics"]
