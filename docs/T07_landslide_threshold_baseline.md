# T07 — LHASA v1.1-Inspired Landslide Threshold Baseline

## Purpose

This document describes the LHASA v1.1-inspired heuristic landslide
threshold model implemented in ResQShield as Task T07 (Day 2).

The model provides a simple, explainable, rule-based baseline for
landslide hazard assessment.  Every alert decision is traceable to
specific threshold breaches — no black-box ML is involved.

This baseline is intended to be the explainable reference point against
which ML models (e.g. XGBoost) are later compared.

---

## Scientific Reference

NASA's LHASA (Landslide Hazard Assessment for Situational Awareness) v1.1:

> Kirschbaum, D.B. & Stanley, T. (2018).
> "Satellite-Based Assessment of Rainfall-Triggered Landslide Hazard
> for Situational Awareness."
> *Natural Hazards*, 87(1), 77–97.
> doi:10.1007/s11069-017-2757-4

> Stanley, T. & Kirschbaum, D.B. (2017).
> "A heuristic approach to global landslide susceptibility mapping."
> *Natural Hazards*, 87(1), 145–164.

### LHASA v1.1 Design Principles

1. A **static susceptibility map** classifies terrain by landslide risk
   (slope, lithology, land cover, fault proximity).

2. **Antecedent rainfall** accumulation serves as a proxy for soil
   saturation — wetter soils require less additional rainfall to fail.

3. **Recent rainfall intensity** is the dynamic trigger.  An alert is
   issued only when a trigger fires in susceptible terrain.

**Key principle:** susceptibility alone does NOT trigger a warning;
rainfall alone in low-susceptibility terrain does NOT trigger a warning.
Both conditions must be met.

---

## ResQShield Adaptation

This module preserves LHASA v1.1's core gating principle but extends
it for ResQShield's multi-hazard sensor context:

| LHASA v1.1 Component | ResQShield Equivalent |
|---|---|
| Satellite susceptibility map | `terrain_susceptibility` (0–1 score) |
| GPM IMERG antecedent rainfall | `soil_moisture_pct` sensor reading |
| GPM IMERG recent rainfall | `rainfall_mm_hr` from local gauge |
| *(not in LHASA)* | `water_level_m_delta_1` — rate of rise (secondary trigger) |
| *(not in LHASA)* | `water_level_m` — included for explainability only |

---

## Algorithm

```
For each timestep:

  1. CLASSIFY each indicator into a severity level:
     ─ rainfall_intensity   → NONE / LOW / MODERATE / HIGH / EXTREME
     ─ antecedent_wetness   → NONE / LOW / MODERATE / HIGH
     ─ water_level_state    → NONE / MODERATE / HIGH / EXTREME
     ─ rate_of_rise         → NONE / LOW / HIGH / EXTREME
     ─ terrain_suscept.     → LOW / MODERATE / HIGH

  2. CHECK TRIGGER (dynamic indicator check):
     ─ trigger_active = True if:
         rainfall_severity    >= MODERATE, OR
         rate_of_rise_severity >= MODERATE
     ─ If NOT trigger_active → risk = NONE (stop)

  3. CHECK GATE (susceptibility gate — LHASA v1.1 core):
     ─ If terrain_susceptibility < MODERATE → risk = LOW (stop)
     ─ If terrain data is absent → gate NOT applied (conservative)

  4. COMPUTE BASE RISK from highest dynamic trigger:
     ─ base_risk = max(rainfall_severity, rate_of_rise_severity)

  5. AMPLIFY by antecedent wetness (LHASA v1.1):
     ─ If wetness_severity >= HIGH (saturated soil):
         base_risk += 1 level (capped at EXTREME)

  6. OUTPUT risk_level (0–4 integer) and per-indicator explanation
```

### Design Decisions

- **Water level is for explainability only.**  It is classified and
  reported in every assessment but does NOT affect the landslide
  combination logic.  This keeps the model true to LHASA's landslide
  focus.

- **Rate of rise is a secondary trigger.**  Rapid water-level rise can
  indicate upstream debris flow or landslide dam breach, making it
  relevant to landslide hazard assessment.

- **Missing indicators are skipped gracefully.**  If a column is absent
  from the DataFrame, the corresponding indicator is simply not
  evaluated.  At least one trigger must be present for any alert.

- **Missing terrain data → conservative.**  When the terrain
  susceptibility column is absent, the susceptibility gate is not
  applied.  This means the model may produce more alerts (false alarms)
  but will not miss events.

---

## Severity Levels

| Value | Level | Meaning |
|---|---|---|
| 0 | NONE | No alert |
| 1 | LOW | Low concern (trigger fired but susceptibility is low) |
| 2 | MODERATE | Moderate hazard — monitor actively |
| 3 | HIGH | High hazard — prepare for response |
| 4 | EXTREME | Extreme hazard — immediate action required |

---

## Input Columns

| Column | Required | Description |
|---|---|---|
| `rainfall_mm_hr` | Recommended | Instantaneous rainfall intensity |
| `soil_moisture_pct` | Optional | Volumetric soil moisture (%) |
| `water_level_m` | Optional | Water level (for explainability only) |
| `water_level_m_delta_1` | Optional | 1-hour water-level change (m/hr) |
| `terrain_susceptibility` | Optional | Static terrain susceptibility (0–1) |

Missing columns are handled gracefully — the corresponding indicator
is simply not evaluated.

---

## Threshold Calibration

**All thresholds must be calibrated per deployment region.**

The production config (`configs/landslide_threshold.yaml`) ships with
ALL threshold values set to `null`.  The model raises
`ThresholdsNotCalibratedError` if any threshold is null.

### Calibration Sources (Region-Specific)

| Threshold Group | Calibration Source |
|---|---|
| Rainfall intensity | IMD district-level rainfall statistics, local AWS records |
| Soil moisture | In-situ sensor calibration, SMAP/SMOS satellite validation |
| Water level | CWC gauge warning/danger levels per station |
| Rate of rise | Catchment response time analysis |
| Terrain susceptibility | GSI/NDMA susceptibility mapping, slope/lithology/land-cover analysis |

---

## Usage

```python
from resqshield_ml.baselines.landslide_threshold import (
    LandslideThresholdBaseline,
    Severity,
)

# Thresholds must come from region-specific calibration.
# The values below are EXAMPLES ONLY — do NOT use for operations.
thresholds = {
    "rainfall_intensity":      {"light": ..., "moderate": ..., "heavy": ..., "extreme": ...},
    "antecedent_wetness":      {"moist": ..., "wet": ..., "saturated": ...},
    "water_level":             {"elevated": ..., "high": ..., "critical": ...},
    "rate_of_rise":            {"warning": ..., "critical": ...},
    "terrain_susceptibility":  {"moderate": ..., "high": ...},
}
model = LandslideThresholdBaseline(thresholds=thresholds)

# ── Predict risk levels ──────────────────────────────────────
risk_levels = model.predict(df)            # numpy array of ints (0–4)

# ── Predict with full explainability ─────────────────────────
assessments = model.predict_explained(df)  # list of RiskAssessment

for a in assessments:
    print(f"Risk: {a.risk_level.name}, Trigger: {a.trigger_active}")
    for name, reason in a.explanation.items():
        print(f"  {name}: {reason}")
```

---

## Limitations

1. **Not a predictive model.**  This is a nowcast — it assesses current
   conditions, not future risk.  It does not forecast.

2. **Threshold-dependent.**  All output quality depends on threshold
   calibration.  Miscalibrated thresholds will produce poor alerts.

3. **No spatial awareness.**  The model processes one station at a time.
   It does not consider spatial patterns or upstream/downstream
   relationships between stations.

4. **No learning.**  Unlike LHASA v2 (XGBoost-based), this model does
   not learn from historical events.  Its performance ceiling is
   determined by the threshold design and calibration.

5. **Terrain susceptibility is optional.**  When absent, the
   susceptibility gate is not applied (conservative — more false alarms
   possible).  Operational deployments should always provide terrain
   data.

---

## Files

| File | Purpose |
|---|---|
| `src/resqshield_ml/baselines/landslide_threshold.py` | Model implementation |
| `configs/landslide_threshold.yaml` | Production config (all thresholds null) |
| `tests/test_landslide_threshold.py` | Automated tests |
| `docs/T07_landslide_threshold_baseline.md` | This document |
