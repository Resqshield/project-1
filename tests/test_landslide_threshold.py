"""
Tests for resqshield_ml.baselines.landslide_threshold (T07).

LHASA v1.1-inspired heuristic landslide threshold baseline.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from resqshield_ml.baselines.landslide_threshold import (
    IndicatorName,
    LandslideThresholdBaseline,
    RiskAssessment,
    Severity,
    ThresholdsNotCalibratedError,
)


# ══════════════════════════════════════════════════════════════════════════════
# SOFTWARE TEST THRESHOLDS — NOT OPERATIONAL THRESHOLDS
#
# These numeric values are used ONLY for automated testing of the
# heuristic model's software logic (threshold classification, combination
# rules, explainability output).
#
# They are NOT calibrated to any real-world region, climate zone, soil
# type, or catchment and MUST NOT be used for operational deployment or
# decision-making.
#
# Region-specific calibration using local meteorological, geological,
# and hydrological data is required before any operational use.
# ══════════════════════════════════════════════════════════════════════════════
TEST_THRESHOLDS = {
    "rainfall_intensity": {
        "light": 2.5,       # mm/hr — SOFTWARE TEST VALUE ONLY
        "moderate": 7.5,    # mm/hr — SOFTWARE TEST VALUE ONLY
        "heavy": 15.0,      # mm/hr — SOFTWARE TEST VALUE ONLY
        "extreme": 30.0,    # mm/hr — SOFTWARE TEST VALUE ONLY
    },
    "antecedent_wetness": {
        "moist": 30.0,      # % soil moisture — SOFTWARE TEST VALUE ONLY
        "wet": 50.0,        # % soil moisture — SOFTWARE TEST VALUE ONLY
        "saturated": 70.0,  # % soil moisture — SOFTWARE TEST VALUE ONLY
    },
    "water_level": {
        "elevated": 3.0,    # metres — SOFTWARE TEST VALUE ONLY
        "high": 5.0,        # metres — SOFTWARE TEST VALUE ONLY
        "critical": 7.0,    # metres — SOFTWARE TEST VALUE ONLY
    },
    "rate_of_rise": {
        "warning": 0.2,     # m/hr — SOFTWARE TEST VALUE ONLY
        "critical": 0.5,    # m/hr — SOFTWARE TEST VALUE ONLY
    },
    "terrain_susceptibility": {
        "moderate": 0.4,    # score 0–1 — SOFTWARE TEST VALUE ONLY
        "high": 0.7,        # score 0–1 — SOFTWARE TEST VALUE ONLY
    },
}


@pytest.fixture
def model():
    """LandslideThresholdBaseline with test thresholds."""
    return LandslideThresholdBaseline(thresholds=TEST_THRESHOLDS)


def _row(**kwargs) -> pd.DataFrame:
    """Create a single-row DataFrame from keyword arguments."""
    return pd.DataFrame([kwargs])


# ─── Calibration Validation ──────────────────────────────────────────────────

class TestCalibrationValidation:
    """Verify that uncalibrated (null) configs are rejected."""

    def test_all_null_raises(self):
        """Model creation fails when all thresholds are null."""
        uncalibrated = {
            "rainfall_intensity": {
                "light": None, "moderate": None,
                "heavy": None, "extreme": None,
            },
            "antecedent_wetness": {
                "moist": None, "wet": None, "saturated": None,
            },
            "water_level": {
                "elevated": None, "high": None, "critical": None,
            },
            "rate_of_rise": {"warning": None, "critical": None},
            "terrain_susceptibility": {"moderate": None, "high": None},
        }
        with pytest.raises(
            ThresholdsNotCalibratedError, match="not calibrated",
        ):
            LandslideThresholdBaseline(thresholds=uncalibrated)

    def test_one_null_raises(self):
        """Even a single null threshold should raise."""
        t = copy.deepcopy(TEST_THRESHOLDS)
        t["rainfall_intensity"]["heavy"] = None
        with pytest.raises(ThresholdsNotCalibratedError):
            LandslideThresholdBaseline(thresholds=t)

    def test_from_config_null_raises(self):
        """from_config should also raise on null thresholds."""
        t = copy.deepcopy(TEST_THRESHOLDS)
        t["rate_of_rise"]["critical"] = None
        with pytest.raises(ThresholdsNotCalibratedError):
            LandslideThresholdBaseline.from_config({"thresholds": t})

    def test_from_config_missing_thresholds_raises(self):
        """from_config should raise when thresholds section is absent."""
        with pytest.raises(ThresholdsNotCalibratedError):
            LandslideThresholdBaseline.from_config({})

    def test_calibrated_thresholds_succeeds(self):
        """Fully calibrated thresholds should create the model."""
        model = LandslideThresholdBaseline(thresholds=TEST_THRESHOLDS)
        assert model is not None

    def test_from_config_calibrated_succeeds(self):
        """from_config with calibrated thresholds should succeed."""
        model = LandslideThresholdBaseline.from_config(
            {"thresholds": TEST_THRESHOLDS},
        )
        assert model is not None


# ─── Production Config Validation ────────────────────────────────────────────

class TestProductionConfig:
    """Verify the production YAML correctly has null thresholds."""

    def test_production_config_raises_uncalibrated(self):
        """configs/landslide_threshold.yaml must have all-null thresholds."""
        from resqshield_ml.utils.config import load_config

        cfg = load_config("configs/landslide_threshold.yaml")
        with pytest.raises(ThresholdsNotCalibratedError):
            LandslideThresholdBaseline.from_config(cfg)


# ─── fit() No-Op ─────────────────────────────────────────────────────────────

class TestFit:
    """Heuristic model has no trainable parameters."""

    def test_fit_returns_self(self, model):
        assert model.fit() is model

    def test_fit_with_data_is_noop(self, model):
        df = _row(rainfall_mm_hr=10.0)
        assert model.fit(X=df, y=pd.Series([1])) is model


# ─── LHASA Core Principle: Susceptibility Gates, Trigger Activates ───────────

class TestLHASAGatePrinciple:
    """LHASA v1.1 core: no trigger → no alert; low susceptibility → capped."""

    def test_no_trigger_returns_none(self, model):
        """No dynamic trigger → NONE, regardless of susceptibility."""
        df = _row(
            rainfall_mm_hr=1.0,             # below LIGHT (2.5)
            soil_moisture_pct=80.0,         # saturated — but irrelevant
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.9,     # HIGH susceptibility
        )
        assert model.predict(df)[0] == Severity.NONE

    def test_trigger_low_susceptibility_returns_low(self, model):
        """Trigger active but terrain is LOW → capped at LOW."""
        df = _row(
            rainfall_mm_hr=20.0,            # HEAVY → trigger active
            soil_moisture_pct=10.0,
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.2,     # LOW susceptibility
        )
        assert model.predict(df)[0] == Severity.LOW

    def test_trigger_high_susceptibility_alerts(self, model):
        """Trigger active + HIGH susceptibility → risk from trigger."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE → trigger active
            soil_moisture_pct=20.0,
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.8,     # HIGH
        )
        assert model.predict(df)[0] == Severity.MODERATE

    def test_missing_terrain_is_conservative(self, model):
        """When terrain data absent, susceptibility gate NOT applied."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE trigger
            soil_moisture_pct=20.0,
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            # No terrain_susceptibility column
        )
        # Gate not applied → risk based on trigger level
        assert model.predict(df)[0] == Severity.MODERATE

    def test_terrain_at_moderate_boundary_opens_gate(self, model):
        """Terrain exactly at moderate threshold → gate opens."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE trigger
            terrain_susceptibility=0.4,     # exactly at moderate boundary
        )
        assert model.predict(df)[0] == Severity.MODERATE

    def test_terrain_below_moderate_boundary_closes_gate(self, model):
        """Terrain just below moderate threshold → gate closed."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE trigger
            terrain_susceptibility=0.39,    # just below moderate
        )
        assert model.predict(df)[0] == Severity.LOW


# ─── Rainfall Classification ─────────────────────────────────────────────────

class TestRainfallClassification:
    """Individual rainfall severity levels via predict_explained."""

    def _rainfall_severity(self, model, mm_hr, terrain=0.8):
        df = _row(rainfall_mm_hr=mm_hr, terrain_susceptibility=terrain)
        assessed = model.predict_explained(df)
        return next(
            i.severity for i in assessed[0].indicators
            if i.name == IndicatorName.RAINFALL.value
        )

    def test_none(self, model):
        assert self._rainfall_severity(model, 0.5) == Severity.NONE

    def test_light(self, model):
        assert self._rainfall_severity(model, 3.0) == Severity.LOW

    def test_moderate(self, model):
        assert self._rainfall_severity(model, 10.0) == Severity.MODERATE

    def test_heavy(self, model):
        assert self._rainfall_severity(model, 20.0) == Severity.HIGH

    def test_extreme(self, model):
        assert self._rainfall_severity(model, 50.0) == Severity.EXTREME

    def test_boundary_at_threshold(self, model):
        """Value exactly at a threshold → classified at that level."""
        assert self._rainfall_severity(model, 7.5) == Severity.MODERATE


# ─── Antecedent Wetness Amplification ────────────────────────────────────────

class TestAntecedentAmplification:
    """LHASA v1.1: saturated soil amplifies the risk by one level."""

    def test_saturated_soil_amplifies_risk(self, model):
        """Saturated soil (HIGH wetness) → risk +1 level."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE trigger
            soil_moisture_pct=80.0,         # SATURATED (>= 70)
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.8,
        )
        # MODERATE + saturated amplification → HIGH
        assert model.predict(df)[0] == Severity.HIGH

    def test_dry_soil_no_amplification(self, model):
        """Dry soil does not amplify."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE
            soil_moisture_pct=15.0,         # DRY (< 30)
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.8,
        )
        assert model.predict(df)[0] == Severity.MODERATE

    def test_wet_soil_no_amplification(self, model):
        """WET (MODERATE) does not amplify — only SATURATED (HIGH)."""
        df = _row(
            rainfall_mm_hr=10.0,
            soil_moisture_pct=55.0,         # WET (MODERATE)
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.8,
        )
        assert model.predict(df)[0] == Severity.MODERATE

    def test_saturated_extreme_rainfall_capped(self, model):
        """Amplification cannot exceed EXTREME."""
        df = _row(
            rainfall_mm_hr=50.0,            # EXTREME
            soil_moisture_pct=80.0,         # SATURATED
            water_level_m=1.0,
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.8,
        )
        # EXTREME + saturated → still EXTREME (capped)
        assert model.predict(df)[0] == Severity.EXTREME


# ─── Rate of Rise as Trigger ─────────────────────────────────────────────────

class TestRateOfRise:
    """Rate-of-rise is a secondary dynamic trigger."""

    def test_critical_rate_triggers_extreme(self, model):
        """Rate above critical threshold → EXTREME."""
        df = _row(
            rainfall_mm_hr=0.0,
            soil_moisture_pct=20.0,
            water_level_m=2.0,
            water_level_m_delta_1=0.6,      # EXTREME (>= 0.5)
            terrain_susceptibility=0.8,
        )
        assert model.predict(df)[0] == Severity.EXTREME

    def test_warning_rate_triggers_high(self, model):
        """Rate above warning threshold → HIGH."""
        df = _row(
            rainfall_mm_hr=0.0,
            soil_moisture_pct=20.0,
            water_level_m=2.0,
            water_level_m_delta_1=0.3,      # HIGH (>= 0.2)
            terrain_susceptibility=0.8,
        )
        assert model.predict(df)[0] == Severity.HIGH

    def test_slow_rise_not_a_trigger(self, model):
        """Slow positive rise (below warning) → no trigger → NONE."""
        df = _row(
            rainfall_mm_hr=0.0,
            soil_moisture_pct=20.0,
            water_level_m=2.0,
            water_level_m_delta_1=0.05,     # LOW (> 0 but < 0.2)
            terrain_susceptibility=0.8,
        )
        assert model.predict(df)[0] == Severity.NONE


# ─── Water Level Explainability Design ───────────────────────────────────────

class TestWaterLevelDesign:
    """Water level is for explainability only — it does not affect
    the landslide combination logic per LHASA v1.1 design."""

    def test_water_level_does_not_override_risk(self, model):
        """Extreme water level should NOT raise landslide risk."""
        df = _row(
            rainfall_mm_hr=10.0,            # MODERATE trigger
            soil_moisture_pct=20.0,         # DRY
            water_level_m=8.0,              # EXTREME water level
            water_level_m_delta_1=0.0,
            terrain_susceptibility=0.8,
        )
        # Risk should be MODERATE (from rainfall), not EXTREME
        assert model.predict(df)[0] == Severity.MODERATE

    def test_water_level_appears_in_explanation(self, model):
        """Water level should still appear in the explanation dict."""
        df = _row(
            rainfall_mm_hr=10.0,
            water_level_m=6.0,              # HIGH
            terrain_susceptibility=0.8,
        )
        assessments = model.predict_explained(df)
        explanation = assessments[0].explanation
        assert IndicatorName.WATER_LEVEL.value in explanation
        assert "High" in explanation[IndicatorName.WATER_LEVEL.value]


# ─── Explainability ──────────────────────────────────────────────────────────

class TestExplainability:
    """Verify the explanation interface."""

    def test_explanation_dict_has_all_indicator_keys(self, model):
        """All five indicators present → all five keys in explanation."""
        df = _row(
            rainfall_mm_hr=10.0,
            soil_moisture_pct=55.0,
            water_level_m=2.0,
            water_level_m_delta_1=0.1,
            terrain_susceptibility=0.8,
        )
        assessments = model.predict_explained(df)
        explanation = assessments[0].explanation
        assert IndicatorName.RAINFALL.value in explanation
        assert IndicatorName.ANTECEDENT_WETNESS.value in explanation
        assert IndicatorName.WATER_LEVEL.value in explanation
        assert IndicatorName.RATE_OF_RISE.value in explanation
        assert IndicatorName.TERRAIN.value in explanation

    def test_reasons_are_human_readable_strings(self, model):
        """Every indicator reason should be a non-empty string."""
        df = _row(rainfall_mm_hr=10.0, terrain_susceptibility=0.8)
        assessments = model.predict_explained(df)
        for ind in assessments[0].indicators:
            assert isinstance(ind.reason, str)
            assert len(ind.reason) > 0

    def test_trigger_active_flag_true(self, model):
        """Trigger flag should be True when a trigger fires."""
        df = _row(rainfall_mm_hr=10.0, terrain_susceptibility=0.8)
        a = model.predict_explained(df)
        assert a[0].trigger_active is True

    def test_trigger_active_flag_false(self, model):
        """Trigger flag should be False when no trigger fires."""
        df = _row(rainfall_mm_hr=1.0, terrain_susceptibility=0.8)
        a = model.predict_explained(df)
        assert a[0].trigger_active is False

    def test_risk_assessment_type(self, model):
        """predict_explained returns list of RiskAssessment."""
        df = _row(rainfall_mm_hr=20.0, terrain_susceptibility=0.8)
        assessments = model.predict_explained(df)
        assert isinstance(assessments[0], RiskAssessment)
        assert isinstance(assessments[0].risk_level, Severity)


# ─── Edge Cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_dataframe(self, model):
        """Empty DataFrame → empty array."""
        df = pd.DataFrame(
            columns=["rainfall_mm_hr", "terrain_susceptibility"],
        )
        preds = model.predict(df)
        assert len(preds) == 0

    def test_missing_all_expected_columns(self, model):
        """DataFrame with no recognised columns → NONE."""
        df = pd.DataFrame({"unrelated_col": [42.0]})
        preds = model.predict(df)
        assert preds[0] == Severity.NONE

    def test_nan_values_skipped(self, model):
        """NaN in a sensor column → that indicator is skipped."""
        df = _row(
            rainfall_mm_hr=float("nan"),
            soil_moisture_pct=80.0,
            terrain_susceptibility=0.8,
        )
        # NaN rainfall → no trigger → NONE
        preds = model.predict(df)
        assert preds[0] == Severity.NONE

    def test_multiple_rows_batch(self, model):
        """Batch prediction across multiple rows."""
        df = pd.DataFrame([
            {
                "rainfall_mm_hr": 0.0,
                "terrain_susceptibility": 0.8,
            },
            {
                "rainfall_mm_hr": 10.0,
                "terrain_susceptibility": 0.8,
            },
            {
                "rainfall_mm_hr": 50.0,
                "terrain_susceptibility": 0.8,
            },
        ])
        preds = model.predict(df)
        assert len(preds) == 3
        assert preds[0] == Severity.NONE       # no trigger
        assert preds[1] == Severity.MODERATE   # moderate rainfall
        assert preds[2] == Severity.EXTREME    # extreme rainfall

    def test_synthetic_terrain_susceptibility(self, model):
        """terrain_susceptibility column is accepted.

        NOTE: In tests, this value is a purely synthetic placeholder.
        Real deployments require terrain susceptibility from
        geotechnical or susceptibility-mapping analysis.
        """
        # SYNTHETIC TEST VALUE — NOT FROM REAL TERRAIN DATA
        synthetic_terrain_score = 0.75
        df = _row(
            rainfall_mm_hr=10.0,
            terrain_susceptibility=synthetic_terrain_score,
        )
        preds = model.predict(df)
        assert preds[0] == Severity.MODERATE


# ─── repr ─────────────────────────────────────────────────────────────────────

class TestRepr:

    def test_repr_is_informative(self, model):
        r = repr(model)
        assert "LandslideThresholdBaseline" in r
        assert "mm/hr" in r
