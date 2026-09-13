# T50 — Existing Indian / Operational EWS Comparison

## Status
DONE

## Objective

Compare ResQShield against strong existing Indian and regional early-warning systems without
claiming that established technologies such as AI, IoT, LoRa, rainfall thresholds or sensor
networks are themselves novel.

T50 acceptance condition:

- At least three strong Indian/existing comparators.
- Exact difference from ResQShield stated for every comparator.
- Existing systems are treated as baselines/integration sources, not dismissed.
- Claimed ResQShield improvements remain validation targets rather than unsupported superiority claims.

---

## 1. Comparison Principles

1. Compare systems only on capabilities supported by published/official evidence.
2. "Different" does not automatically mean "better".
3. Existing operational systems are stronger evidence than a prototype feature.
4. Do not compare a monitoring feature against another system's prediction capability.
5. Do not claim AI, IoT, LoRa, rainfall thresholds, dashboards or physics+ML as novelty.
6. ResQShield should augment authoritative regional systems rather than replace them.
7. Any claimed improvement must later be demonstrated through measurable evaluation.

---

## 2. Competitor / Baseline Matrix

| Comparator | Evidence / Maturity | Established Strength | Scope / Primary Function | Exact ResQShield Difference | What ResQShield Must NOT Claim |
|---|---|---|---|---|---|
| Amrita-LEWS | Long-running Indian site-specific IoT LEWS; Munnar and Sikkim deployments | Multi-parameter real-time landslide sensing including rainfall, moisture/pore-pressure, tilt/movement and other geophysical observations; field warning experience | Site-focused landslide monitoring and early warning | ResQShield is designed as a multi-hazard integration-and-action layer: combine authoritative forecasts + local observations, quantify observation confidence, connect flood/landslide cascade risk, calculate usable evacuation time, and dynamically update route/shelter decisions | Do not claim India lacks operational IoT landslide EWS; do not claim IoT/LoRa or adding soil sensors is novel; do not claim superior landslide warning skill without comparative field validation |
| LANDSLIP India | Indian regional LEWS prototype/pilot evaluated in Darjeeling and Nilgiris; rainfall-threshold methodology published | Terrain-specific/frequentist rainfall thresholds, regional rainfall-induced landslide forecasting, uncertainty-aware threshold development | Regional rainfall-induced landslide warning | ResQShield adds local dynamic observations and source-health/confidence to a threshold baseline, then links the hazard estimate to multi-hazard/cascade reasoning and local road/shelter action | Do not claim rainfall thresholds are novel; do not claim LANDSLIP is only monitoring; do not claim ResQShield beats the threshold baseline before event-based comparison |
| South Asia FFGS | Operational regional flash-flood guidance system led by IMD | Large-scale operational flash-flood guidance/forecasting, watershed/city-level products, regional institutional workflow and meaningful forecast lead time | Regional flash-flood guidance for South Asia | ResQShield consumes/augments regional guidance with hyperlocal field evidence and converts it into confidence-aware village/catchment action: local roads, shelters, evacuation margin and fallback last-mile warning | Do not replace or disparage IMD/FFGS; do not claim ResQShield has stronger regional forecasting skill without evidence; local sensing complements rather than substitutes authoritative forecasts |
| GSI National Landslide Forecasting Centre / Bhusanket | Official Indian landslide forecasting ecosystem | Regional landslide forecasting, inventories/hazard information, forecast bulletins and communication to administrators/community | National/regional landslide forecasting and dissemination | ResQShield's intended role is downstream/local integration: combine official forecast information with local sensing, infrastructure state, observation confidence and evacuation/shelter decisions | Do not claim India has no landslide forecasting; do not present ResQShield as replacement for GSI/NLFC |

---

## 3. Comparator-by-Comparator Interpretation

### 3.1 Amrita-LEWS

What already exists:
- Real Indian field deployments.
- Long-duration landslide monitoring.
- Multi-parameter geological/hydrological sensing.
- Wireless/IoT monitoring architecture.
- Warning experience with government stakeholders.

Therefore these are NOT ResQShield novelty claims:
- IoT landslide sensing
- LoRa/wireless sensing as a concept
- soil-moisture/pore-pressure monitoring
- multi-sensor landslide warning
- cloud/edge connected monitoring

ResQShield's intended measurable extension:
- observation-confidence / source-health scoring
- graceful degradation during simultaneous data/network failures
- flood + landslide + cascade integration
- usable evacuation margin rather than hazard score alone
- live road/shelter action layer
- cross-region transfer/evaluation

Required evidence before claiming improvement:
- failure-injection performance
- external-region validation
- missed-event and false-alarm comparison
- warning latency
- action correctness

---

### 3.2 LANDSLIP

What already exists:
- Indian regional landslide-warning work.
- Darjeeling and Nilgiris pilots.
- rainfall-trigger thresholds.
- threshold uncertainty.
- regional warning methodology.

Therefore these are NOT ResQShield novelty claims:
- rainfall thresholds
- antecedent-rainfall thresholds
- graded rainfall warning
- regional rainfall-induced landslide forecasting

LANDSLIP should be implemented/reproduced conceptually as a HARD BASELINE.

ResQShield's intended measurable extension:
- dynamic wetness/local sensor state in addition to rainfall
- observation freshness/quality/confidence
- multiple source fallback
- multi-hazard/cascade context
- action-oriented routing/shelter decision support

Required evidence before claiming improvement:
- LANDSLIP-style threshold baseline tested on the same event split
- recall/POD
- false alarm ratio
- CSI/F1 where valid
- calibration where probabilistic
- lead time
- performance under missing/degraded observations

---

### 3.3 South Asia FFGS

What already exists:
- Operational regional flash-flood guidance.
- IMD as South Asia regional centre.
- Multi-country institutional workflow.
- meaningful forecast/guidance lead times.
- watershed/city-level flash-flood products.

Therefore ResQShield must NOT say:
- "IMD only gives rainfall"
- "India has no flash-flood guidance"
- "regional systems cannot forecast flash floods"

ResQShield's intended role:
- ingest authoritative regional guidance as one trusted evidence source
- combine it with strategically deployed local observations
- expose source age and confidence
- translate hazard guidance into village-level operational decisions
- estimate usable evacuation time
- update road/shelter choices
- maintain a local fallback warning path during connectivity degradation

This is an integration/action claim, not a claim that ResQShield replaces FFGS.

---

### 3.4 GSI NLFC / Bhusanket

What already exists:
- official Indian landslide forecasting infrastructure
- regional LEWS roadmap
- forecast bulletins
- landslide inventories/hazard information
- administrator/community communication goals

Therefore ResQShield must NOT say:
- "India has no landslide forecasting"
- "GSI only makes static maps"

ResQShield's intended role:
- consume official landslide guidance where available
- add hyperlocal observation evidence
- track observation confidence
- integrate roads, shelters and local impact
- preserve a clear distinction between official forecast and ResQShield local decision support

---

## 4. Honest Novelty / Difference Statement

### Existing capabilities

The following are established and are NOT claimed as novelty:

- AI/ML hazard modelling
- IoT sensor networks
- LoRa/wireless telemetry
- rainfall thresholds
- soil-moisture/pore-pressure sensing
- physics + ML hybrid models
- GIS dashboards
- susceptibility mapping
- public warning channels

### ResQShield target contribution

ResQShield's primary contribution is the integration of established capabilities into a
hyperlocal multi-hazard operational decision loop focused on:

1. Observation confidence and source health.
2. Graceful degradation under sensor/network/source failures.
3. Transfer/generalization beyond one valley or one event.
4. Flood-landslide/cascade reasoning.
5. Explicit uncertainty rather than one unexplained risk number.
6. Usable evacuation margin.
7. Dynamic road, route and shelter state.
8. Last-mile action even when connectivity degrades.
9. Post-event validation and learning.

These are target improvements and must be validated experimentally.

---

## 5. Strongest Competitor Lessons

### Lesson from Amrita-LEWS
Long-running Indian field deployment already exists.

ResQShield must beat neither history nor hardware by assertion.
It must demonstrate added reliability, integration and action value.

### Lesson from LANDSLIP
Simple rainfall-threshold methods are legitimate strong baselines.

Any complex model must outperform them on meaningful warning metrics.

### Lesson from South Asia FFGS
Authoritative regional flash-flood capability already exists.

ResQShield should use it as upstream intelligence and specialize in hyperlocal integration/action.

### Lesson from GSI NLFC
Indian official landslide forecasting is expanding.

ResQShield should remain interoperable and complementary.

---

## 6. Required Benchmark Metrics

Future ResQShield evaluation against applicable baselines should report:

- Recall / Probability of Detection
- False Alarm Ratio
- CSI/F1 where meaningful
- Calibration / Brier score for probabilistic outputs where possible
- Lead time by hazard/sensor class
- Alert latency
- External-region performance drop
- Observation-confidence calibration
- Performance under source/sensor/network failures
- Action correctness
- Evacuation margin

Do not compare systems using a metric that the source did not report.

---

## 7. Judge-Safe Positioning

### Do say

"Strong Indian and regional systems already provide landslide monitoring, regional
landslide forecasting and flash-flood guidance. ResQShield is designed to augment these
systems with hyperlocal observation-confidence, multi-hazard integration and an
action-oriented evacuation decision loop."

### Do not say

"India has no landslide early warning."

"Existing government systems are inaccurate."

"IMD only predicts rainfall."

"We are the first to use IoT/LoRa/AI for landslide warning."

"Our model is better than existing systems."

---

## 8. Evidence Classes

| Comparator | Evidence Class |
|---|---|
| Amrita-LEWS | Published + long-running institutional field deployment |
| LANDSLIP | Published regional methodology + government pilot/evaluation |
| South Asia FFGS | Operational WMO/IMD regional system |
| GSI NLFC / Bhusanket | Official Government of India forecasting infrastructure |

---

## 9. Source Register

Internal ResQShield evidence:
- ResQShield Master Checklist — T50 / S100 / S123 / S65
- SIH 26192 Deep Review Master — mature-baseline and novelty audit
- Final Combined Solution — augment-not-replace positioning

External evidence:
- Amrita Vishwa Vidyapeetham — Landslide Early Warning System project material
- Springer — Landslide Early Warning Systems: Requirements and Solutions for Disaster Risk Reduction—India
- Government of India Press Information Bureau — Early Warning System for Landslides, 2 Dec 2021
- Springer — Challenges in Defining Frequentist Rainfall Thresholds to Be Implemented in a Landslide Early Warning System in India
- World Meteorological Organization — South Asia Flash Flood Guidance System
- Geological Survey of India — National Landslide Forecasting Centre / Bhusanket

---

## 10. T50 Acceptance Checklist

- [x] Amrita-LEWS included.
- [x] LANDSLIP included.
- [x] Strong operational flash-flood baseline included.
- [x] Current Indian official landslide forecasting ecosystem included.
- [x] At least three strong comparators are present.
- [x] Exact ResQShield difference is stated for each comparator.
- [x] Existing systems are not disparaged.
- [x] AI/IoT/LoRa are not claimed as novelty.
- [x] Rainfall thresholds are treated as a baseline, not novelty.
- [x] Regional authoritative forecasts are treated as integration inputs.
- [x] Proposed improvements are explicitly described as requiring validation.
- [x] Monitoring/detection/prediction/warning claims remain separated.
- [x] No unsupported claim of superiority remains.

## Result

T50 PASS CONDITION:

ResQShield has at least three strong Indian/existing EWS comparators with an explicit,
scientifically bounded difference statement for each.

## Status After Review
CANDIDATE FOR DONE — pending automated checklist verification.
