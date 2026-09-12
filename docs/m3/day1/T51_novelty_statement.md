# T51 - Defensible Novelty Statement

**Day:** 1
**Owner:** M3 - SW Backend & Data
**Priority:** P0
**Task:** T51 - Do not claim AI / IoT / LoRa as novelty

## What is NOT our novelty

ResQShield does not claim that the following technologies are new:

- Artificial Intelligence / Machine Learning
- IoT sensing
- LoRa communication
- GIS mapping
- REST APIs or dashboards
- Government weather, river or disaster alert feeds

These are established technologies and system components.

## What ResQShield actually improves

Our defensible contribution is the way these existing components are combined into a reliability-aware, transferable and confidence-aware early-warning workflow.

### 1. Reliability under imperfect observations

The system is designed so that missing, stale or failed observations are not interpreted as safe conditions.

It explicitly tracks source health, freshness and fallback behaviour instead of silently treating missing data as zero.

### 2. Transfer and region awareness

The system is not presented as a model that works only in one valley.

A primary pilot and a geographically separate holdout are frozen explicitly, while region/catchment configuration remains separate from reusable system logic.

### 3. Observation confidence separate from hazard risk

ResQShield separates:

- hazard risk: how likely/severe the hazard appears to be
- observation confidence: how trustworthy and complete the supporting observations are

High hazard risk with low observation confidence must not become false safety.

### 4. Existing systems are augmented, not replaced

Official forecasting, hydrology and alert systems remain upstream sources.

ResQShield adds a hyperlocal decision layer that combines local observations, source reliability, catchment context and downstream action.

## Claims we will NOT make

- "AI itself is our novelty"
- "IoT itself is our novelty"
- "LoRa itself is our novelty"
- "World's first" or "India's first" without evidence
- "We replace IMD / CWC / GSI / NDMA systems"

## 30-second team explanation

"AI, IoT and LoRa are not our novelty; they are existing components. ResQShield's contribution is making the warning workflow more operationally trustworthy: we track whether observations are healthy and fresh, avoid treating missing data as safe data, keep hazard risk separate from observation confidence, and test whether the system transfers beyond one pilot region. Existing government intelligence remains an input; our layer converts it with local observations into a more reliable hyperlocal decision workflow."

## T51 Acceptance Check

- Existing technologies are explicitly identified as non-novel.
- Primary claim is reliability + transfer + observation confidence.
- No unsupported 'first in India/world' claim is made.
- Government systems are positioned as inputs/partners, not systems to replace.
- The explanation can be delivered in approximately 30 seconds.
