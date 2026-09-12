"""
resqshield_ml.baselines.flood_threshold
=========================================
Flash-flood explainable threshold baseline for ResQShield (T09).

Design philosophy
-----------------
This baseline mirrors the LHASA v1.1 design used by T07 but is adapted
for flash-flood early warning rather than landslide assessment.

The flash-flood heuristic works by checking a set of configurable
conditions — cumulative rainfall thresholds, current water-level state,
rapid water-level rise, and antecedent wetness — then combining the
results into an overall risk level.

Unlike the landslide baseline, flash-flood risk does NOT require terrain
susceptibility as a gate.  Rainfall + water level alone can trigger a
warning.

The model returns:
    - risk_level   : Severity (0–4)
    - triggered_rules : list of condition names that fired
    - missing_inputs  : list of input columns that were absent
    - explanation     : dict of {condition_name: reason_string}

All production threshold values must be null.  Region-specific calibration
is required.  For CWC-monitored stations, Warning Level (WL) and Danger
Level (DL) from the AFF portal provide the starting point for water-level
thresholds.  Rainfall thresholds must be derived from local IMD records.

References
----------
  CWC AFF Portal threshold definitions:
    Warning Level (WL)  — river enters "Above Normal" flood situation
    Danger Level (DL)   — flooding begins in low-lying areas
    Highest Flood Level — all-time historical maximum (HFL)
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Severity Levels ─────────────────────────────────────────────────────────

class Severity(enum.IntEnum):
    """Risk severity levels (0–4).  Higher = greater hazard."""

    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    EXTREME = 4


# ─── Condition Names ──────────────────────────────────────────────────────────

class ConditionName(str, enum.Enum):
    """Canonical names for threshold conditions."""

    RAINFALL_1H = "cumulative_rainfall_1h"
    RAINFALL_3H = "cumulative_rainfall_3h"
    RAINFALL_6H = "cumulative_rainfall_6h"
    RAINFALL_12H = "cumulative_rainfall_12h"
    RAINFALL_24H = "cumulative_rainfall_24h"
    ANTECEDENT = "antecedent_wetness"
    WATER_LEVEL = "water_level_state"
    RATE_OF_RISE = "rate_of_rise"


# ─── Errors ───────────────────────────────────────────────────────────────────

class FloodThresholdsNotCalibratedError(Exception):
    """Raised when any production threshold value is null (uncalibrated).

    All thresholds must be set to region-specific calibrated values
    before operational use.  See configs/flood_threshold.yaml.
    """


# ─── Result Structures ────────────────────────────────────────────────────────

@dataclass
class ConditionResult:
    """Result for a single evaluated condition."""

    name: str
    fired: bool          # True if the condition triggered
    severity: Severity
    value: float | None
    threshold_used: float | None
    reason: str


@dataclass
class FloodAssessment:
    """Complete flash-flood risk assessment for one timestep.

    Attributes
    ----------
    risk_level : Severity
        Overall risk (0–4).
    triggered_rules : list of str
        Names of conditions that fired (severity >= MODERATE).
    missing_inputs : list of str
        Column names that were absent from the input row.
    explanation : dict of str → str
        Human-readable per-condition reason strings.
    conditions : list of ConditionResult
        Full detail for each evaluated condition.
    """

    risk_level: Severity
    triggered_rules: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    conditions: list[ConditionResult] = field(default_factory=list)

    @property
    def explanation(self) -> dict[str, str]:
        """Human-readable explanation keyed by condition name."""
        return {c.name: c.reason for c in self.conditions}


# ─── Null Threshold Detection ─────────────────────────────────────────────────

def _find_null_thresholds(d: dict, prefix: str = "") -> list[str]:
    """Recursively find keys with None values."""
    nulls: list[str] = []
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            nulls.extend(_find_null_thresholds(value, full_key))
        elif value is None:
            nulls.append(full_key)
    return nulls


# ─── Individual Condition Evaluators ─────────────────────────────────────────
# Each function evaluates a single condition and returns a ConditionResult.

def _eval_rainfall_accumulation(
    value: float,
    name: str,
    thresholds: dict[str, float],
) -> ConditionResult:
    """Evaluate a cumulative rainfall condition (e.g. 1h, 3h, 6h)."""
    high_t = thresholds.get("high")
    moderate_t = thresholds.get("moderate")
    low_t = thresholds.get("low")

    if high_t is not None and value >= high_t:
        sev = Severity.HIGH
        reason = f"High rainfall accumulation ({value:.1f} mm >= {high_t} mm)"
        fired = True
    elif moderate_t is not None and value >= moderate_t:
        sev = Severity.MODERATE
        reason = f"Moderate rainfall accumulation ({value:.1f} mm >= {moderate_t} mm)"
        fired = True
    elif low_t is not None and value >= low_t:
        sev = Severity.LOW
        reason = f"Low rainfall accumulation ({value:.1f} mm >= {low_t} mm)"
        fired = False  # LOW is watch, not trigger
    else:
        sev = Severity.NONE
        reason = f"Rainfall within normal range ({value:.1f} mm)"
        fired = False

    return ConditionResult(
        name=name,
        fired=fired,
        severity=sev,
        value=value,
        threshold_used=high_t or moderate_t,
        reason=reason,
    )


def _eval_antecedent_wetness(
    value: float,
    thresholds: dict[str, float],
) -> ConditionResult:
    """Evaluate antecedent wetness (API or soil moisture %)."""
    high_t = thresholds.get("high")
    moderate_t = thresholds.get("moderate")

    if high_t is not None and value >= high_t:
        sev = Severity.HIGH
        reason = f"High antecedent wetness ({value:.1f} >= {high_t})"
        fired = True
    elif moderate_t is not None and value >= moderate_t:
        sev = Severity.MODERATE
        reason = f"Moderate antecedent wetness ({value:.1f} >= {moderate_t})"
        fired = True
    else:
        sev = Severity.NONE
        reason = f"Normal antecedent wetness ({value:.1f})"
        fired = False

    return ConditionResult(
        name=ConditionName.ANTECEDENT.value,
        fired=fired,
        severity=sev,
        value=value,
        threshold_used=high_t or moderate_t,
        reason=reason,
    )


def _eval_water_level(
    value: float,
    thresholds: dict[str, float],
) -> ConditionResult:
    """Evaluate current water level state.

    CWC threshold semantics:
        danger_level_m  → HIGH (river begins flooding low-lying areas)
        warning_level_m → MODERATE (above normal situation)
    """
    danger_t = thresholds.get("danger_level_m")
    warning_t = thresholds.get("warning_level_m")
    hfl_t = thresholds.get("hfl_m")

    if hfl_t is not None and value >= hfl_t:
        sev = Severity.EXTREME
        reason = (
            f"At/above Highest Flood Level ({value:.2f} m >= HFL {hfl_t:.2f} m)"
        )
        fired = True
    elif danger_t is not None and value >= danger_t:
        sev = Severity.HIGH
        reason = (
            f"Above Danger Level ({value:.2f} m >= DL {danger_t:.2f} m) — "
            "flooding likely"
        )
        fired = True
    elif warning_t is not None and value >= warning_t:
        sev = Severity.MODERATE
        reason = (
            f"Above Warning Level ({value:.2f} m >= WL {warning_t:.2f} m) — "
            "above normal situation"
        )
        fired = True
    else:
        sev = Severity.NONE
        reason = f"Water level normal ({value:.2f} m)"
        fired = False

    return ConditionResult(
        name=ConditionName.WATER_LEVEL.value,
        fired=fired,
        severity=sev,
        value=value,
        threshold_used=danger_t or warning_t,
        reason=reason,
    )


def _eval_rate_of_rise(
    value: float,
    thresholds: dict[str, float],
) -> ConditionResult:
    """Evaluate water-level rate of rise (m/hr)."""
    critical_t = thresholds.get("critical_m_per_hr")
    warning_t = thresholds.get("warning_m_per_hr")

    if critical_t is not None and value >= critical_t:
        sev = Severity.EXTREME
        reason = (
            f"Critical rate of rise ({value:.3f} m/hr >= {critical_t} m/hr) — "
            "rapid flash-flood conditions"
        )
        fired = True
    elif warning_t is not None and value >= warning_t:
        sev = Severity.HIGH
        reason = (
            f"Warning rate of rise ({value:.3f} m/hr >= {warning_t} m/hr)"
        )
        fired = True
    elif value > 0:
        sev = Severity.LOW
        reason = f"Rising slowly ({value:.3f} m/hr, below warning)"
        fired = False
    else:
        sev = Severity.NONE
        reason = f"Stable or falling ({value:.3f} m/hr)"
        fired = False

    return ConditionResult(
        name=ConditionName.RATE_OF_RISE.value,
        fired=fired,
        severity=sev,
        value=value,
        threshold_used=critical_t or warning_t,
        reason=reason,
    )


# ─── Main Model Class ─────────────────────────────────────────────────────────

class FloodThresholdBaseline:
    """Flash-flood explainable threshold baseline for ResQShield (T09).

    This is a rule-based model with no trainable parameters.  All alert
    decisions are fully explainable via triggered_rules and explanation.

    Combination logic
    -----------------
    Any condition at MODERATE severity or above constitutes a trigger.
    The overall risk level is the maximum severity across all triggered
    conditions.

    Antecedent wetness at HIGH severity amplifies any triggered condition
    by +1 level (capped at EXTREME) — wetter soils produce faster runoff
    and a lower effective rainfall threshold.

    Parameters
    ----------
    thresholds : dict
        Nested threshold configuration from flood_threshold.yaml.
        All leaf values must be non-null floats.

    Raises
    ------
    FloodThresholdsNotCalibratedError
        If any threshold value is None.
    """

    # Expected DataFrame column names
    COL_RAINFALL = "rainfall_mm_hr"
    COL_RAIN_1H = "rainfall_mm_hr_rolling_sum_1"
    COL_RAIN_3H = "rainfall_mm_hr_rolling_sum_3"
    COL_RAIN_6H = "rainfall_mm_hr_rolling_sum_6"
    COL_RAIN_12H = "rainfall_mm_hr_rolling_sum_12"
    COL_RAIN_24H = "rainfall_mm_hr_rolling_sum_24"
    COL_API = "antecedent_precipitation_index"
    COL_WATER_LEVEL = "water_level_m"
    COL_RATE_OF_RISE = "water_level_m_delta_1"

    # Minimum severity to count a condition as a trigger
    _TRIGGER_MIN_SEVERITY = Severity.MODERATE

    def __init__(self, thresholds: dict[str, Any]) -> None:
        nulls = _find_null_thresholds(thresholds)
        if nulls:
            raise FloodThresholdsNotCalibratedError(
                "The following flood thresholds are not calibrated (null):\n"
                + "\n".join(f"  - {k}" for k in sorted(nulls))
                + "\n\nRegion-specific calibration is required before use.\n"
                "For CWC-monitored stations, use Warning Level and Danger Level "
                "from aff.india-water.gov.in after verifying the station-specific values.\n"
                "Set all values in configs/flood_threshold.yaml."
            )
        self.thresholds = thresholds

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "FloodThresholdBaseline":
        """Instantiate from a full flood_threshold.yaml config dict.

        Raises
        ------
        FloodThresholdsNotCalibratedError
            If thresholds section is missing or contains nulls.
        """
        thresholds = cfg.get("thresholds", {})
        if not thresholds:
            raise FloodThresholdsNotCalibratedError(
                "No 'thresholds' section in config. "
                "Region-specific calibration is required."
            )
        return cls(thresholds=thresholds)

    # ── scikit-learn–compatible interface ──────────────────────────────────

    def fit(self, X: Any = None, y: Any = None) -> "FloodThresholdBaseline":
        """No-op.  Rule-based model has no trainable parameters."""
        logger.info(
            "FloodThresholdBaseline.fit() called — "
            "no-op for rule-based model."
        )
        return self

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict flash-flood risk levels (0–4) for each row.

        Parameters
        ----------
        df : pd.DataFrame
            Feature-engineered sensor data.  Missing columns are handled
            gracefully — missing inputs are recorded in the assessment.

        Returns
        -------
        np.ndarray of int
            Risk levels (0=NONE … 4=EXTREME).
        """
        return np.array(
            [int(a.risk_level) for a in self._assess_all(df)], dtype=int,
        )

    def predict_explained(self, df: pd.DataFrame) -> list[FloodAssessment]:
        """Predict with full explainability.

        Returns
        -------
        list of FloodAssessment
            One per row.  Each contains risk_level, triggered_rules,
            missing_inputs, and explanation.
        """
        return self._assess_all(df)

    # ── Internal Assessment Logic ─────────────────────────────────────────

    def _assess_all(self, df: pd.DataFrame) -> list[FloodAssessment]:
        return [self._assess_row(row) for _, row in df.iterrows()]

    def _assess_row(self, row: pd.Series) -> FloodAssessment:
        """Evaluate all conditions for a single timestep."""
        conditions: list[ConditionResult] = []
        missing_inputs: list[str] = []

        thr = self.thresholds

        # Helper — fetch value or mark missing
        def get_val(col: str) -> float | None:
            if col not in row.index or pd.isna(row[col]):
                missing_inputs.append(col)
                return None
            return float(row[col])

        # ── 1. Rainfall accumulation conditions ──────────────────────────
        rain_windows = [
            (self.COL_RAIN_1H,  ConditionName.RAINFALL_1H.value,  "rainfall_1h"),
            (self.COL_RAIN_3H,  ConditionName.RAINFALL_3H.value,  "rainfall_3h"),
            (self.COL_RAIN_6H,  ConditionName.RAINFALL_6H.value,  "rainfall_6h"),
            (self.COL_RAIN_12H, ConditionName.RAINFALL_12H.value, "rainfall_12h"),
            (self.COL_RAIN_24H, ConditionName.RAINFALL_24H.value, "rainfall_24h"),
        ]
        for col, cname, thr_key in rain_windows:
            v = get_val(col)
            if v is not None and thr_key in thr:
                conditions.append(
                    _eval_rainfall_accumulation(v, cname, thr[thr_key])
                )

        # Fallback: use current rainfall if rolling sums absent
        if not any(c.name.startswith("cumulative_rainfall") for c in conditions):
            v = get_val(self.COL_RAINFALL)
            if v is not None and "rainfall_intensity" in thr:
                # Use 1h threshold for intensity as rough proxy
                conditions.append(
                    _eval_rainfall_accumulation(
                        v,
                        ConditionName.RAINFALL_1H.value,
                        thr["rainfall_intensity"],
                    )
                )

        # ── 2. Antecedent wetness (API) ──────────────────────────────────
        v = get_val(self.COL_API)
        if v is not None and "antecedent_wetness" in thr:
            conditions.append(
                _eval_antecedent_wetness(v, thr["antecedent_wetness"])
            )

        # ── 3. Water level ────────────────────────────────────────────────
        v = get_val(self.COL_WATER_LEVEL)
        if v is not None and "water_level" in thr:
            conditions.append(
                _eval_water_level(v, thr["water_level"])
            )

        # ── 4. Rate of rise ───────────────────────────────────────────────
        v = get_val(self.COL_RATE_OF_RISE)
        if v is not None and "rate_of_rise" in thr:
            conditions.append(
                _eval_rate_of_rise(v, thr["rate_of_rise"])
            )

        # ── 5. Combine ────────────────────────────────────────────────────
        risk_level, triggered = self._combine(conditions)

        return FloodAssessment(
            risk_level=risk_level,
            triggered_rules=triggered,
            missing_inputs=sorted(set(missing_inputs)),
            conditions=conditions,
        )

    def _combine(
        self,
        conditions: list[ConditionResult],
    ) -> tuple[Severity, list[str]]:
        """Combine condition results into overall risk.

        Logic
        -----
        1. No conditions → NONE.
        2. Find all conditions at >= MODERATE → these are the triggers.
        3. If no triggers → NONE.
        4. Base risk = maximum severity across triggered conditions.
        5. Antecedent wetness at HIGH amplifies by +1 (capped at EXTREME).
        6. Water level at HIGH/EXTREME independently contributes to final
           risk (direct danger, not only an amplifier).
        """
        if not conditions:
            return Severity.NONE, []

        # Identify triggers
        triggered = [c for c in conditions if c.severity >= self._TRIGGER_MIN_SEVERITY]
        triggered_names = [c.name for c in triggered]

        if not triggered:
            return Severity.NONE, []

        # Base risk = max severity of triggers
        base_risk = max(c.severity for c in triggered)

        # Antecedent wetness amplification
        antecedent = next(
            (c for c in conditions if c.name == ConditionName.ANTECEDENT.value),
            None,
        )
        if antecedent and antecedent.severity >= Severity.HIGH:
            if base_risk < Severity.EXTREME:
                base_risk = Severity(base_risk + 1)

        return Severity(min(int(base_risk), int(Severity.EXTREME))), triggered_names

    def __repr__(self) -> str:
        wl = self.thresholds.get("water_level", {})
        return (
            f"FloodThresholdBaseline("
            f"WL={wl.get('warning_level_m')} m, "
            f"DL={wl.get('danger_level_m')} m)"
        )
