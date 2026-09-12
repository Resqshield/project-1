# T50 — Comparison with Existing Indian Early-Warning Systems

## Purpose

This document compares ResQShield with established or pilot early-warning
systems relevant to flash floods and landslides in India.

The purpose is not to claim that ResQShield replaces national systems.
Instead, the comparison identifies the specific niche ResQShield is intended
to address: local, multi-hazard, sensor-assisted decision support combining
flash-flood and landslide indicators in one deployment.

---

## Systems Compared

### 1. Amrita Landslide Early Warning System (A-LEWS)

Amrita Vishwa Vidyapeetham has deployed a real-time landslide monitoring and
early-warning system in Munnar, Kerala.

The system uses an IoT / wireless sensor network and monitors variables such as:

- rainfall
- soil moisture
- pore-water pressure
- ground movement / tilt
- vibration

It has operated in Munnar since 2009 and has been used to issue warnings to
government authorities.

Primary strength:
Highly localized, sensor-rich landslide monitoring.

Hazard focus:
Landslides.

---

### 2. GSI / LANDSLIP Regional Landslide Early Warning System

The Geological Survey of India, working with the British Geological Survey and
other partners through the LANDSLIP project, developed a prototype regional
Landslide Early Warning System for India.

Pilot regions included:

- Darjeeling, West Bengal
- Nilgiris, Tamil Nadu

The system uses rainfall thresholds and regional landslide susceptibility /
hazard information to support regional warnings.

Primary strength:
Regional-scale landslide warning and rainfall-threshold methodology.

Hazard focus:
Landslides.

---

### 3. South Asia Flash Flood Guidance System (SAsiaFFGS)

The South Asia Flash Flood Guidance System is operated regionally by the India
Meteorological Department.

It serves:

- India
- Nepal
- Bhutan
- Bangladesh
- Sri Lanka

The system combines hydrometeorological observations, satellite information,
soil-moisture / land-surface modelling and numerical weather prediction to
provide flash-flood guidance.

It can provide watershed-level guidance several hours before potential flash
flood occurrence.

Primary strength:
Large-scale operational flash-flood guidance backed by national and
international meteorological infrastructure.

Hazard focus:
Flash floods.

---

### 4. Central Water Commission Flood Forecasting System

The Central Water Commission is India's nodal organisation for river flood
forecasting and early flood warnings.

CWC operates a large national network of level and inflow forecasting
stations and provides river-level / reservoir-inflow forecasts.

Primary strength:
Large operational river-monitoring and forecasting network.

Hazard focus:
River flooding and reservoir inflow.

---

## Comparison

| Capability | Amrita A-LEWS | GSI / LANDSLIP | South Asia FFGS | CWC Flood Forecasting | ResQShield |
|---|---|---|---|---|---|
| Landslide warning | Yes | Yes | No | No | Planned |
| Flash-flood warning | No / not primary | No | Yes | Flood forecasting | Planned |
| Multi-hazard flood + landslide | No | No | No | No | Yes |
| Local IoT sensors | Strong | Limited / regional approach | Primarily regional meteorological products | Hydrological station network | Planned |
| Rainfall input | Yes | Yes | Yes | Yes | Yes |
| Soil moisture / wetness | Yes | Can contribute to susceptibility modelling | Land-surface / soil-saturation products | Not primary local input | Yes |
| Water-level sensor input | Not primary | No | Hydrological products rather than local ResQShield sensor | Yes | Yes |
| Ground movement sensors | Yes | Primarily regional modelling / threshold approach | No | No | Optional / planned |
| Rate-of-water-level-rise feature | Not primary | No | System-dependent hydrological guidance | Water-level forecasting | Planned |
| Static terrain susceptibility | Site-specific knowledge | Yes | Watershed hydrology | River network / basin models | Planned |
| ML-ready sensor fusion | Limited / system-specific | Threshold / regional model based | Advanced hydrometeorological modelling | Forecasting models | Planned RF / XGBoost fusion |
| Local deployment focus | Very strong | Regional | Regional / national | National river network | Very strong |
| National-scale infrastructure | No | GSI regional framework | Yes | Yes | No |
| Edge / low-connectivity deployment | Sensor-network oriented | Not main objective | No | No | Planned |
| Explainable risk factors | Sensor thresholds | Rainfall thresholds / susceptibility | Meteorological guidance | Water levels / forecasts | Planned feature-level explanation |
| Open experiment pipeline | Not the focus of comparison | Not the focus | Operational system | Operational system | Yes — reproducible ML pipeline |

---

## ResQShield's Intended Differentiation

ResQShield should NOT be presented as replacing IMD, GSI, CWC or Amrita
systems.

Its proposed contribution is a smaller-scale complementary system combining:

1. Local rainfall measurements.
2. Soil-moisture / wetness sensing.
3. River or stream water-level sensing.
4. Rate-of-rise detection.
5. Static terrain / landslide susceptibility.
6. Forecast rainfall where available.
7. Flood and landslide risk within the same platform.
8. Reproducible ML models such as Random Forest / Gradient Boosting / XGBoost.
9. Local alerts and decision support in locations where dense national sensor
   coverage may not exist.

The intended architecture therefore combines ideas from two types of systems:

    Regional / national forecasting
              +
       local IoT sensing
              +
       terrain information
              +
    reproducible ML inference
              ↓
          ResQShield

---

## Important Positioning

ResQShield should not claim:

- to outperform CWC, IMD, GSI or Amrita systems without comparative validation
- nationwide operational coverage
- proven warning lead times before real-world testing
- validated landslide or flood accuracy before real Indian data is evaluated
- that ML automatically provides better warnings than physical or threshold
  models

Instead, the SIH prototype should demonstrate that heterogeneous local inputs
can be integrated into one reproducible flood-and-landslide risk pipeline.

---

## Sources

1. Amrita Vishwa Vidyapeetham — Real-time Landslide Warning Systems.
2. Amrita Vishwa Vidyapeetham — Munnar landslide early-warning deployments.
3. Government of India / Ministry of Earth Sciences — Early Warning System for Landslides.
4. Geological Survey of India / LANDSLIP project.
5. World Meteorological Organization — South Asia Flash Flood Guidance System.
6. India Meteorological Department — South Asia Flash Flood Guidance bulletins.
7. Government of India / Ministry of Jal Shakti — Central Water Commission flood forecasting.