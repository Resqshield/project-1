# T66 — EWS Completeness + Monitoring/Detection/Prediction/Warning Claim Separation

## Status
DONE

## Purpose
T66 prevents ResQShield from calling every sensor, dashboard, threshold or AI output a
"prediction" or a complete "early warning system".

The system must distinguish:

1. Risk Knowledge
2. Monitoring
3. Detection
4. Prediction
5. Warning
6. Action / Response
7. Validation / Support

The four end-to-end EWS stages used for completeness are:

1. Risk Knowledge
2. Monitoring / Forecasting
3. Warning Dissemination / Communication
4. Preparedness / Response Capability

A technically strong model is not by itself a complete EWS.

---

## 1. Claim Definitions

### Risk Knowledge
Static or slowly changing information describing where people, infrastructure or terrain are
generally vulnerable.

Examples:
- susceptibility
- terrain
- drainage
- geology
- population exposure
- infrastructure vulnerability

Risk knowledge does NOT mean that an event is happening now.

### Monitoring
Observation of current or recent physical/system state.

Examples:
- rainfall reading
- soil-moisture reading
- river level
- tilt
- source freshness
- current catchment wetness

Monitoring answers:

"What is happening now?"

Monitoring alone is NOT prediction.

### Detection
Identification of an observed threshold crossing, abnormal condition or state change.

Examples:
- rapid river rise detected
- sensor fault detected
- abnormal slope movement detected
- threshold exceeded

Detection answers:

"Has a concerning condition already appeared in the available observations?"

Detection is NOT automatically future prediction.

### Prediction
A validated estimate of a future hazard/state over a defined horizon.

Examples:
- flood probability for the next hour
- predicted river level
- landslide probability in the next warning window
- predicted downstream cascade

Prediction must have:
- future horizon
- validation
- uncertainty/confidence
- appropriate performance metrics

Prediction answers:

"What is expected to happen next?"

### Warning
A decision/action message produced from risk, observations, prediction, uncertainty,
impact and warning policy, then communicated to intended users.

Examples:
- WATCH
- WARNING
- EVACUATION
- ALL CLEAR

Warning is NOT identical to model probability.

### Action / Response
Operational action taken because of the warning/risk state.

Examples:
- close road
- open shelter
- pre-position resources
- evacuate population
- reroute responders
- move people to high ground

### Validation / Support
Modules that test, maintain, explain or improve the system but do not themselves constitute
a live hazard prediction.

Examples:
- historical replay
- post-event validation
- model drift monitoring
- system health monitoring

---

## 2. ResQShield 23-Module Claim-Separation Matrix

| Module | Module Name | Primary T66 Classification | What It May Claim | What It Must NOT Claim |
|---|---|---|---|---|
| M01 | Risk & Digital Terrain | Risk Knowledge | Static susceptibility/exposure context | Current event prediction |
| M02 | Hyperlocal IoT | Monitoring | Current field observations | Prediction merely because sensors are real-time |
| M03 | External Data Integration | Monitoring | External evidence/forecast ingestion | Village ground truth from coarse regional data |
| M04 | Sensor/Data Quality | Detection / Support | Missing, stale, drift, fault or inconsistency detection | Hazard prediction |
| M05 | Rainfall Intelligence | Monitoring + Prediction where forecast exists | Current rainfall state and validated near-term rainfall estimate | Calling current rainfall measurement a hazard forecast |
| M06 | Soil & Catchment State | Monitoring; Prediction only for explicit future wetness | Current wetness/saturation state | Landslide prediction merely from current wetness |
| M07 | Flood Prediction | Prediction | Future flash-flood probability/state over defined horizon | Guaranteed flood occurrence |
| M08 | Landslide Prediction | Prediction | Future landslide-risk estimate over defined horizon | Guaranteed slope failure |
| M09 | Water-Level Prediction | Prediction | Future river/water-level estimate over defined horizon | Calling current level measurement prediction |
| M10 | Cascade Intelligence | Detection + Prediction | Current cascade evidence and validated future cascade pathway | Claiming every possible cascade will occur |
| M11 | AI + Physics Ensemble | Prediction Support | Combined/validated hazard estimate | Novelty merely because AI and physics are combined |
| M12 | Risk & Uncertainty | Decision / Prediction Support | Probability, confidence, disagreement and uncertainty | Treating low confidence as low hazard |
| M13 | Early Warning | Warning | Actionable warning level and dissemination | Calling a raw model score a public warning |
| M14 | Disaster Prevention / Pre-positioning | Action / Response | Resource staging recommendation | Hazard prediction |
| M15 | Dynamic Evacuation | Action / Response | Lowest-known-risk route recommendation | Guaranteed safe route |
| M16 | Shelter Allocation | Action / Response | Risk/capacity-aware shelter recommendation | Guaranteed shelter availability without live status |
| M17 | Population Reallocation | Action / Response | Dynamic population/shelter reassignment | Hazard prediction |
| M18 | Edge / Offline Resilience | Warning Support | Local fallback alert/dissemination and buffered operation | Independent proof of prediction accuracy |
| M19 | Authority Dashboard | Warning + Action Interface | Operational situation and decision support | Prediction merely because a forecast is displayed |
| M20 | Citizen App | Warning + Action Interface | Warning, route, shelter and public safety information | Independent hazard prediction |
| M21 | Historical Replay | Validation | Replay/test/drill evidence | Live forecast merely because a past event is replayed |
| M22 | Post-Event Validation | Validation | Predicted-vs-observed evaluation | Pre-event warning capability |
| M23 | Model Monitoring / Updating | Validation / Support | Drift, recalibration and retraining governance | Confusing model monitoring with hazard monitoring |

---

## 3. Four-Stage EWS Completeness Matrix

### Stage 1 — Risk Knowledge

Covered by:
- M01 Risk & Digital Terrain
- static flood/landslide susceptibility
- DEM/slope/drainage/geology/soil/LULC
- population and infrastructure exposure
- historical hazard information

Question answered:

"Where is risk generally high, and who/what is exposed?"

Status: COVERED IN ARCHITECTURE

---

### Stage 2 — Monitoring / Forecasting

Covered by:
- M02 Hyperlocal IoT
- M03 External Data Integration
- M04 Sensor/Data Quality
- M05 Rainfall Intelligence
- M06 Soil & Catchment State
- M07 Flood Prediction
- M08 Landslide Prediction
- M09 Water-Level Prediction
- M10 Cascade Intelligence
- M11 AI + Physics Ensemble
- M12 Risk & Uncertainty

Question answered:

"What is happening now, what may happen next, and how trustworthy is the evidence?"

Status: COVERED IN ARCHITECTURE

---

### Stage 3 — Warning Dissemination / Communication

Covered by:
- M13 Early Warning
- M18 Edge / Offline Resilience
- M19 Authority Dashboard
- M20 Citizen App

Planned/defined warning paths include:
- authority dashboard
- citizen application
- responder interfaces
- SMS/push/local warning integrations
- edge/offline warning fallback

Question answered:

"Who needs to know, what should they be told, and can the warning still reach them?"

Status: COVERED IN ARCHITECTURE

Important:
Communication capability does not itself prove forecast skill.
Alert generation does not itself prove a complete EWS.
External official publishing authority must not be implied unless formally integrated/authorized.

---

### Stage 4 — Preparedness / Response Capability

Covered by:
- M14 Disaster Prevention / Pre-positioning
- M15 Dynamic Evacuation
- M16 Shelter Allocation
- M17 Population Reallocation
- M19 Authority Dashboard
- M20 Citizen App

Question answered:

"What action should authorities, responders and citizens take now?"

Status: COVERED IN ARCHITECTURE

---

## 4. Required ResQShield Claim Rules

### Rule 1 — Static susceptibility is not prediction
Allowed:
"Static background landslide susceptibility is high."

Not allowed:
"A landslide will occur soon" based only on a static susceptibility map.

### Rule 2 — Sensor monitoring is not prediction
Allowed:
"The river is currently rising rapidly."

Not allowed:
"The system predicted the flood" if it only detected a current high water level.

### Rule 3 — Detection is not automatically forecasting
Allowed:
"A rapid-rise threshold was detected."

Prediction may only be claimed when a future state/hazard is estimated and validated.

### Rule 4 — Prediction is not warning
A model probability becomes part of a warning decision only after:
- data quality/confidence check
- hazard evaluation
- impact/context evaluation
- policy/threshold decision
- authorized dissemination workflow

### Rule 5 — Warning delivery is not the whole EWS
A message channel alone does not provide:
- risk knowledge
- monitoring/forecasting
- response capability

### Rule 6 — AI / IoT / LoRa are enabling technologies
Do not use:
"AI Early Warning" as a blanket technical claim.

The evidence must say what AI actually predicts and what IoT actually monitors.

### Rule 7 — Route safety language must remain bounded
Use:
"lowest-known-risk recommended route"

Do not use:
"guaranteed safe route"

### Rule 8 — Current data and estimated data must remain distinguishable
Measured, imputed, fallback-derived and model-estimated values must not be presented as the same kind of evidence.

### Rule 9 — Alert authority must not be overstated
ResQShield may generate decision-support warnings and integration-ready alert objects.

Do not claim official public-alert publishing authority unless formal authorization/integration exists.

### Rule 10 — Validation scope controls wording
If a module has only simulation/replay evidence, say:
"validated in simulation/replay"

Do not say:
"field-proven operational warning"

unless real operational evidence exists.

---

## 5. End-to-End Claim Chain

Correct ResQShield language:

Risk Knowledge
->
Monitoring
->
Detection / State Assessment
->
Prediction
->
Uncertainty / Impact Assessment
->
Warning Decision
->
Communication
->
Action / Response
->
Post-Event Validation

Each stage has a different technical meaning.

---

## 6. Example — Flash Flood

Rain gauge reports 68 mm/h
= Monitoring

River rises 22 cm in 10 minutes and threshold is exceeded
= Detection

Model estimates 0.82 probability of dangerous downstream flooding within the defined horizon
= Prediction

Authority/system policy issues a WARNING with confidence, affected area and required action
= Warning

Road is closed and citizens are directed to a lower-risk route/high-ground point
= Action / Response

After the event, observed flood extent is compared with the forecast
= Validation

---

## 7. Example — Landslide

Soil moisture, rainfall and tilt are continuously observed
= Monitoring

Acceleration/threshold abnormality appears
= Detection

Validated model estimates elevated slope-failure risk in the future warning window
= Prediction

Affected road/village receives an authorized landslide warning
= Warning

Road closure / evacuation / shelter action is initiated
= Action / Response

Actual post-event slope condition is compared with prediction
= Validation

---

## 8. Evaluation Metrics Must Also Be Stage-Specific

### Monitoring
- data availability
- freshness
- coverage
- sensor error
- packet delivery
- missing-data rate

### Detection
- detection rate
- false detection rate
- detection latency
- threshold performance

### Prediction
- recall / POD
- precision
- false alarm ratio
- CSI
- calibration / Brier score where applicable
- lead time
- horizon-specific error

### Warning / Communication
- alert generation latency
- delivery success
- acknowledgement
- channel coverage
- escalation success

### Response
- decision time
- evacuation margin
- route availability
- shelter capacity violations
- reroutes
- affected population reached

One metric must not be used as proof for a different stage.

---

## 9. T66 Acceptance Checklist

- [x] Risk Knowledge is separated from current prediction.
- [x] Monitoring is separated from Prediction.
- [x] Detection is separated from Prediction.
- [x] Prediction is separated from Warning.
- [x] Warning is separated from Response.
- [x] Static susceptibility is not called real-time prediction.
- [x] Sensor/dashboard presence is not called predictive capability.
- [x] Model outputs require a defined future horizon before using "prediction".
- [x] Warning requires decision + communication, not only probability.
- [x] Response/action capability is explicitly represented.
- [x] All four EWS stages are represented.
- [x] All 23 ResQShield granular modules are explicitly classified.
- [x] Stage-specific validation metrics are defined.
- [x] Official publishing authority is not overstated.
- [x] Simulation/replay evidence is not described as field-proven evidence.

---

## 10. T66 Result

T66 PASS CONDITION:

Every ResQShield module has an explicit functional/claim classification and the architecture
covers the complete chain:

Risk Knowledge
->
Monitoring / Forecasting
->
Warning Communication
->
Preparedness / Response

ResQShield must therefore be presented as an end-to-end decision-support and early-warning
architecture, while each individual component is described only according to what it has
actually been designed and validated to do.

## Status After Review
DONE — checklist verification and automated acceptance checks passed.

