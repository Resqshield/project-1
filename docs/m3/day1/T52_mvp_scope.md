# T52 - Frozen MVP Scope and Explicit Avoid-List

**Day:** 1
**Owner:** M3 - SW Backend & Data
**Priority:** P0
**Task:** T52 - Do not overbuild
**Hard dependency:** T51

## Scope Rule

ResQShield will prioritize a small, testable and integrated early-warning MVP over adding technologies merely because they appear advanced.

A new feature must not enter the MVP unless:

1. it addresses a documented project gap or acceptance criterion;
2. its dependency and test are clear;
3. it does not weaken delivery of an existing P0 item; and
4. if it materially expands scope, another equivalent scope item is explicitly deferred or removed.

## P0 - Core MVP

- Frozen primary pilot geography and geographically separate holdout
- Shared backend/configuration/database foundation
- Common timestamped event/data schema
- Core static GIS context
- Rainfall history features
- Soil-moisture / wetness history
- Missing-data-safe handling
- Source health and freshness
- Observation confidence
- Measured / imputed / fallback provenance
- External-source connector contracts
- REST / live-data API contracts
- Simple validated hazard baselines
- Failure-aware and testable system behaviour

## P1 - Strong Enhancements

- Advanced ML only if it beats strong baselines
- Better cascade reasoning
- More advanced uncertainty calibration
- Additional dashboard/research diagnostics
- Selective higher-quality sensing
- Regional/local recalibration improvements

## P2 - Optional / Pilot-Specific

- Optional GLOF / cryosphere module
- Experimental uncertainty methods
- Additional specialised sensors
- Research-only advanced models
- Extra non-core visualisations

## AVOID - Outside Current MVP

- Blockchain
- GNN / Transformer everywhere
- Deep learning where a simple validated baseline is enough
- Fibre-optic sensing everywhere
- Microseismic / geophone networks everywhere
- Advanced geotechnical sensing at every node
- New routing metaheuristic when dynamic A* / Dijkstra is sufficient
- Separate model for every village without evidence
- Full glacier or dam-breach modelling as mandatory core
- Duplicate parallel architectures
- Features with no task, gap, deliverable or test

## Engineering Decision Rule

Before adding a non-frozen feature, answer:

1. Which Task ID or gap requires it?
2. What measurable improvement should it produce?
3. What is its acceptance test?
4. What current scope item will be delayed or removed?

If these cannot be answered, the feature stays outside the MVP.

## T52 Acceptance Check

- P0 / P1 / P2 / AVOID are separated.
- Advanced methods are evidence-driven.
- Optional modules cannot block the core MVP.
- Scope expansion requires an explicit trade-off.
