"""
resqshield_ml.baselines.landslide_threshold
=============================================
LHASA v1.1-inspired heuristic landslide threshold baseline for ResQShield.

Scientific reference
--------------------
    Kirschbaum, D.B. & Stanley, T. (2018).
    "Satellite-Based Assessment of Rainfall-Triggered Landslide Hazard
    for Situational Awareness."
    Natural Hazards, 87(1), 77–97. doi:10.1007/s11069-017-2757-4

    Stanley, T. & Kirschbaum, D.B. (2017).
    "A heuristic approach to global landslide susceptibility mapping."
    Natural Hazards, 87(1), 145–164.

LHASA v1.1 overview
--------------------
    NASA's LHASA (Landslide Hazard Assessment for Situational Awareness)
    v1.1 is a rule-based heuristic that issues landslide nowcasts by
    combining:

      1. A static landslide susceptibility map (terrain, slope, lithology)
      2. Antecedent rainfall accumulation (proxy for soil saturation)
      3. Recent rainfall intensity (the dynamic trigger)

    A nowcast alert is raised only when BOTH conditions hold:
      - The location has moderate-to-high susceptibility, AND
      - A rainfall trigger condition is met given antecedent wetness.

    Static susceptibility alone never triggers a warning.
    Rainfall alone in low-susceptibility terrain never triggers a warning.

ResQShield adaptation
---------------------
    This module preserves LHASA v1.1's core design principle — static
    susceptibility gates the alert, dynamic triggers activate it — but
    extends the indicator set for ResQShield's multi-hazard context:

      - Soil moisture sensor readings replace satellite-derived proxy
      - Water-level rate-of-rise is a secondary dynamic trigger
      - Water-level state is included for explainability
      - All threshold values must be calibrated per-region before use

    The production config (configs/landslide_threshold.yaml) ships with
    all thresholds set to null.  The model cannot be instantiated from
    an uncalibrated config — it raises ThresholdsNotCalibratedError.
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
    """Risk severity levels for indicators and overall assessment.

    Ordinal scale where higher values indicate greater hazard.
    """

    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    EXTREME = 4


# ─── Indicator Names ─────────────────────────────────────────────────────────

class IndicatorName(str, enum.Enum):
    """Canonical names for heuristic indicators."""

    RAINFALL = "rainfall_intensity"
    ANTECEDENT_WETNESS = "antecedent_wetness"
    WATER_LEVEL = "water_level_state"
    RATE_OF_RISE = "rate_of_rise"
    TERRAIN = "terrain_susceptibility"


# ─── Errors ───────────────────────────────────────────────────────────────────

class ThresholdsNotCalibratedError(Exception):
    """Raised when threshold config contains null (uncalibrated) values.

    All thresholds must be calibrated per deployment region before the
    model can be used.  See configs/landslide_threshold.yaml.
    """


# ─── Result Data Structures ──────────────────────────────────────────────────

@dataclass
class IndicatorResult:
    """Classification result for a single indicator at one timestep."""

    name: str
    severity: Severity
    value: float | None
    reason: str


@dataclass
class RiskAssessment:
    """Complete risk assessment for a single timestep.

    Attributes
    ----------
    risk_level : Severity
        Overall risk severity (0–4).
    indicators : list of IndicatorResult
        Per-indicator classification results.
    trigger_active : bool
        Whether at least one dynamic trigger was at MODERATE severity
        or above.
    """

    risk_level: Severity
    indicators: list[IndicatorResult] = field(default_factory=list)
    trigger_active: bool = False

    @property
    def explanation(self) -> dict[str, str]:
        """Human-readable explanation keyed by indicator name."""
        return {ind.name: ind.reason for ind in self.indicators}


# ─── Threshold Classifiers ───────────────────────────────────────────────────
# Each function classifies a single indicator value against calibrated
# thresholds and returns a (Severity, reason_string) tuple.

def _classify_rainfall(
    value: float, thresholds: dict[str, float],
) -> tuple[Severity, str]:
    """Classify rainfall intensity into severity categories."""
    if value >= thresholds["extreme"]:
        return Severity.EXTREME, (
            f"Extreme ({value:.1f} mm/hr >= {thresholds['extreme']} mm/hr)"
        )
    if value >= thresholds["heavy"]:
        return Severity.HIGH, (
            f"Heavy ({value:.1f} mm/hr >= {thresholds['heavy']} mm/hr)"
        )
    if value >= thresholds["moderate"]:
        return Severity.MODERATE, (
            f"Moderate ({value:.1f} mm/hr >= {thresholds['moderate']} mm/hr)"
        )
    if value >= thresholds["light"]:
        return Severity.LOW, (
            f"Light ({value:.1f} mm/hr >= {thresholds['light']} mm/hr)"
        )
    return Severity.NONE, (
        f"None ({value:.1f} mm/hr < {thresholds['light']} mm/hr)"
    )


def _classify_antecedent_wetness(
    value: float, thresholds: dict[str, float],
) -> tuple[Severity, str]:
    """Classify soil moisture / antecedent wetness."""
    if value >= thresholds["saturated"]:
        return Severity.HIGH, (
            f"Saturated ({value:.1f}% >= {thresholds['saturated']}%)"
        )
    if value >= thresholds["wet"]:
        return Severity.MODERATE, (
            f"Wet ({value:.1f}% >= {thresholds['wet']}%)"
        )
    if value >= thresholds["moist"]:
        return Severity.LOW, (
            f"Moist ({value:.1f}% >= {thresholds['moist']}%)"
        )
    return Severity.NONE, (
        f"Dry ({value:.1f}% < {thresholds['moist']}%)"
    )


def _classify_water_level(
    value: float, thresholds: dict[str, float],
) -> tuple[Severity, str]:
    """Classify water level state."""
    if value >= thresholds["critical"]:
        return Severity.EXTREME, (
            f"Critical ({value:.2f} m >= {thresholds['critical']} m)"
        )
    if value >= thresholds["high"]:
        return Severity.HIGH, (
            f"High ({value:.2f} m >= {thresholds['high']} m)"
        )
    if value >= thresholds["elevated"]:
        return Severity.MODERATE, (
            f"Elevated ({value:.2f} m >= {thresholds['elevated']} m)"
        )
    return Severity.NONE, (
        f"Normal ({value:.2f} m < {thresholds['elevated']} m)"
    )


def _classify_rate_of_rise(
    value: float, thresholds: dict[str, float],
) -> tuple[Severity, str]:
    """Classify water-level rate of rise (Δlevel / Δtime)."""
    if value >= thresholds["critical"]:
        return Severity.EXTREME, (
            f"Critical rise ({value:.3f} m/hr >= {thresholds['critical']} m/hr)"
        )
    if value >= thresholds["warning"]:
        return Severity.HIGH, (
            f"Warning rise ({value:.3f} m/hr >= {thresholds['warning']} m/hr)"
        )
    if value > 0:
        return Severity.LOW, (
            f"Rising ({value:.3f} m/hr, below warning)"
        )
    return Severity.NONE, (
        f"Stable or falling ({value:.3f} m/hr)"
    )


def _classify_terrain(
    value: float, thresholds: dict[str, float],
) -> tuple[Severity, str]:
    """Classify terrain susceptibility score (0–1 scale)."""
    if value >= thresholds["high"]:
        return Severity.HIGH, (
            f"High susceptibility ({value:.2f} >= {thresholds['high']})"
        )
    if value >= thresholds["moderate"]:
        return Severity.MODERATE, (
            f"Moderate susceptibility ({value:.2f} >= {thresholds['moderate']})"
        )
    return Severity.LOW, (
        f"Low susceptibility ({value:.2f} < {thresholds['moderate']})"
    )


# ─── Null Threshold Detection ────────────────────────────────────────────────

def _find_null_thresholds(d: dict, prefix: str = "") -> list[str]:
    """Recursively find keys whose values are None."""
    nulls: list[str] = []
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            nulls.extend(_find_null_thresholds(value, full_key))
        elif value is None:
            nulls.append(full_key)
    return nulls


# ─── Main Model Class ────────────────────────────────────────────────────────

class LandslideThresholdBaseline:
    """LHASA v1.1-inspired heuristic landslide threshold model.

    This is a rule-based model with no trainable parameters.  All alert
    decisions are fully explainable — each assessment reports which
    indicators fired, at what severity, and why.

    The model requires calibrated thresholds for the deployment region.
    Attempting to instantiate with null thresholds raises
    :class:`ThresholdsNotCalibratedError`.

    Parameters
    ----------
    thresholds : dict
        Nested threshold configuration with keys:
        ``rainfall_intensity``, ``antecedent_wetness``, ``water_level``,
        ``rate_of_rise``, ``terrain_susceptibility``.
        All leaf values must be non-null floats.

    Raises
    ------
    ThresholdsNotCalibratedError
        If any threshold value is None.

    See Also
    --------
    docs/T07_landslide_threshold_baseline.md : Full algorithm documentation.

    References
    ----------
    .. [1] Kirschbaum & Stanley (2018), Natural Hazards 87(1), 77–97.
    .. [2] Stanley & Kirschbaum (2017), Natural Hazards 87(1), 145–164.
    """

    # Expected DataFrame column names
    COL_RAINFALL: str = "rainfall_mm_hr"
    COL_SOIL_MOISTURE: str = "soil_moisture_pct"
    COL_WATER_LEVEL: str = "water_level_m"
    COL_RATE_OF_RISE: str = "water_level_m_delta_1"
    COL_TERRAIN: str = "terrain_susceptibility"

    # Dynamic indicators that serve as triggers
    _TRIGGER_NAMES = {IndicatorName.RAINFALL, IndicatorName.RATE_OF_RISE}

    # Minimum severity for a dynamic indicator to count as an active trigger
    _TRIGGER_MIN_SEVERITY = Severity.MODERATE

    def __init__(self, thresholds: dict[str, Any]) -> None:
        nulls = _find_null_thresholds(thresholds)
        if nulls:
            raise ThresholdsNotCalibratedError(
                "The following thresholds are not calibrated (null):\n"
                + "\n".join(f"  - {k}" for k in sorted(nulls))
                + "\n\nRegion-specific calibration is required before use.\n"
                "Set all threshold values in configs/landslide_threshold.yaml."
            )
        self.thresholds = thresholds

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "LandslideThresholdBaseline":
        """Create a model from a full YAML config dict.

        Parameters
        ----------
        cfg : dict
            Parsed YAML config (e.g. from configs/landslide_threshold.yaml).

        Returns
        -------
        LandslideThresholdBaseline

        Raises
        ------
        ThresholdsNotCalibratedError
            If the ``thresholds`` section is missing or contains nulls.
        """
        thresholds = cfg.get("thresholds", {})
        if not thresholds:
            raise ThresholdsNotCalibratedError(
                "No 'thresholds' section found in config.\n"
                "Region-specific calibration is required before use."
            )
        return cls(thresholds=thresholds)

    # ── Scikit-learn compatible interface ──────────────────────────────────

    def fit(
        self, X: Any = None, y: Any = None,
    ) -> "LandslideThresholdBaseline":
        """No-op.  Heuristic models have no trainable parameters.

        Provided for API compatibility with scikit-learn and the
        ResQShield ML pipeline.
        """
        logger.info(
            "LandslideThresholdBaseline.fit() called — "
            "no-op for heuristic model."
        )
        return self

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict risk levels for each row in the DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Sensor data (raw or feature-engineered).  Expected columns
            are defined by ``COL_*`` class attributes.  Missing columns
            are handled gracefully — the corresponding indicator is
            skipped.

        Returns
        -------
        np.ndarray of int
            Risk levels (0=NONE, 1=LOW, 2=MODERATE, 3=HIGH, 4=EXTREME).
        """
        assessments = self._assess_all(df)
        return np.array(
            [int(a.risk_level) for a in assessments], dtype=int,
        )

    def predict_explained(
        self, df: pd.DataFrame,
    ) -> list[RiskAssessment]:
        """Predict risk levels with full explainability.

        Parameters
        ----------
        df : pd.DataFrame
            Sensor data (same format as :meth:`predict`).

        Returns
        -------
        list of RiskAssessment
            One assessment per row, each containing:

            - ``risk_level``: overall :class:`Severity`
            - ``indicators``: per-indicator detail
            - ``trigger_active``: whether a dynamic trigger was active
            - ``explanation``: dict of {indicator_name: reason_string}
        """
        return self._assess_all(df)

    # ── Internal Assessment Logic ─────────────────────────────────────────

    def _assess_all(self, df: pd.DataFrame) -> list[RiskAssessment]:
        """Assess risk for every row in the DataFrame."""
        return [self._assess_row(row) for _, row in df.iterrows()]

    def _assess_row(self, row: pd.Series) -> RiskAssessment:
        """Assess risk for a single timestep.

        Each indicator is classified independently, then the results
        are combined via the LHASA v1.1-inspired decision logic.
        """
        indicators: list[IndicatorResult] = []
        trigger_active = False
        terrain_sev: Severity | None = None

        # 1. Rainfall intensity
        if (
            self.COL_RAINFALL in row.index
            and pd.notna(row[self.COL_RAINFALL])
        ):
            sev, reason = _classify_rainfall(
                float(row[self.COL_RAINFALL]),
                self.thresholds["rainfall_intensity"],
            )
            indicators.append(IndicatorResult(
                name=IndicatorName.RAINFALL.value,
                severity=sev,
                value=float(row[self.COL_RAINFALL]),
                reason=reason,
            ))
            if sev >= self._TRIGGER_MIN_SEVERITY:
                trigger_active = True

        # 2. Antecedent wetness (soil moisture)
        if (
            self.COL_SOIL_MOISTURE in row.index
            and pd.notna(row[self.COL_SOIL_MOISTURE])
        ):
            sev, reason = _classify_antecedent_wetness(
                float(row[self.COL_SOIL_MOISTURE]),
                self.thresholds["antecedent_wetness"],
            )
            indicators.append(IndicatorResult(
                name=IndicatorName.ANTECEDENT_WETNESS.value,
                severity=sev,
                value=float(row[self.COL_SOIL_MOISTURE]),
                reason=reason,
            ))

        # 3. Water level state (for explainability — does not affect
        #    the landslide combination logic per LHASA v1.1 design)
        if (
            self.COL_WATER_LEVEL in row.index
            and pd.notna(row[self.COL_WATER_LEVEL])
        ):
            sev, reason = _classify_water_level(
                float(row[self.COL_WATER_LEVEL]),
                self.thresholds["water_level"],
            )
            indicators.append(IndicatorResult(
                name=IndicatorName.WATER_LEVEL.value,
                severity=sev,
                value=float(row[self.COL_WATER_LEVEL]),
                reason=reason,
            ))

        # 4. Rate of rise (Δwater_level over 1 timestep)
        if (
            self.COL_RATE_OF_RISE in row.index
            and pd.notna(row[self.COL_RATE_OF_RISE])
        ):
            sev, reason = _classify_rate_of_rise(
                float(row[self.COL_RATE_OF_RISE]),
                self.thresholds["rate_of_rise"],
            )
            indicators.append(IndicatorResult(
                name=IndicatorName.RATE_OF_RISE.value,
                severity=sev,
                value=float(row[self.COL_RATE_OF_RISE]),
                reason=reason,
            ))
            if sev >= self._TRIGGER_MIN_SEVERITY:
                trigger_active = True

        # 5. Terrain susceptibility (static)
        if (
            self.COL_TERRAIN in row.index
            and pd.notna(row[self.COL_TERRAIN])
        ):
            sev, reason = _classify_terrain(
                float(row[self.COL_TERRAIN]),
                self.thresholds["terrain_susceptibility"],
            )
            indicators.append(IndicatorResult(
                name=IndicatorName.TERRAIN.value,
                severity=sev,
                value=float(row[self.COL_TERRAIN]),
                reason=reason,
            ))
            terrain_sev = sev

        # 6. Combine via LHASA v1.1-inspired decision logic
        risk_level = self._combine(indicators, trigger_active, terrain_sev)

        return RiskAssessment(
            risk_level=risk_level,
            indicators=indicators,
            trigger_active=trigger_active,
        )

    def _combine(
        self,
        indicators: list[IndicatorResult],
        trigger_active: bool,
        terrain_sev: Severity | None,
    ) -> Severity:
        """Combine indicator severities into overall risk level.

        LHASA v1.1-inspired decision logic
        ------------------------------------
        1. If no dynamic trigger (rainfall or rate-of-rise) is active
           at MODERATE severity or above, the risk is NONE.  Static
           conditions alone never trigger an alert.

        2. If terrain susceptibility is below MODERATE (the gate), the
           risk is capped at LOW — even if dynamic triggers fire.

        3. When both conditions are met (susceptible terrain + active
           trigger), the base risk equals the highest trigger severity.

        4. Antecedent wetness amplifies the risk: if soil is at HIGH
           saturation (saturated), the risk increases by one level
           (capped at EXTREME).

        Water level state is classified and included in the per-row
        explanation but does NOT participate in the landslide
        combination logic.

        Parameters
        ----------
        indicators : list of IndicatorResult
            Classified indicator results for this timestep.
        trigger_active : bool
            Whether at least one dynamic trigger is at MODERATE+.
        terrain_sev : Severity or None
            Terrain susceptibility severity, or None if not available.
            When None, the susceptibility gate is not applied
            (conservative default).
        """
        if not indicators:
            return Severity.NONE

        # Build severity lookup
        sev_by_name = {ind.name: ind.severity for ind in indicators}

        rainfall_sev = sev_by_name.get(
            IndicatorName.RAINFALL.value, Severity.NONE,
        )
        ror_sev = sev_by_name.get(
            IndicatorName.RATE_OF_RISE.value, Severity.NONE,
        )
        wetness_sev = sev_by_name.get(
            IndicatorName.ANTECEDENT_WETNESS.value, Severity.NONE,
        )
        # water_level_state is intentionally excluded from the
        # combination — it is present for explainability only.

        # ── Step 1: Trigger check ────────────────────────────────────
        # No meaningful dynamic trigger → no alert.
        if not trigger_active:
            return Severity.NONE

        # ── Step 2: Susceptibility gate (LHASA v1.1 core) ───────────
        # If terrain data is available and susceptibility is below
        # MODERATE, cap the risk at LOW.
        if terrain_sev is not None and terrain_sev < Severity.MODERATE:
            return Severity.LOW

        # ── Step 3: Base risk from highest dynamic trigger ───────────
        base_risk = max(rainfall_sev, ror_sev)

        # ── Step 4: Antecedent wetness amplification ─────────────────
        # LHASA v1.1 principle: wet antecedent conditions lower the
        # rainfall threshold needed for a given alert level.
        # Approximated as: saturated soil → +1 severity level.
        if wetness_sev >= Severity.HIGH and base_risk < Severity.EXTREME:
            base_risk = Severity(base_risk + 1)

        return Severity(min(int(base_risk), int(Severity.EXTREME)))

    # ── String Representation ─────────────────────────────────────────

    def __repr__(self) -> str:
        rf = self.thresholds.get("rainfall_intensity", {})
        return (
            f"LandslideThresholdBaseline("
            f"rainfall_thresholds="
            f"[{rf.get('light')}/{rf.get('moderate')}/"
            f"{rf.get('heavy')}/{rf.get('extreme')} mm/hr])"
        )
