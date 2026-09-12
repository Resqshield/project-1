# T63 — Rainfall / Source Hierarchy and Time-Resolution Audit

## Scope

This task freezes the rainfall-source priority, freshness, resolution,
and fallback rules used by the MVP.

The hierarchy does not claim that coarse satellite or reanalysis products
provide minute-level hyperlocal ground truth.

## Frozen Source Hierarchy

1. LOCAL_GAUGE
   - Role: PRIMARY
   - Highest priority when healthy and fresh.
   - Point measurement.
   - Suitable for minute-level hyperlocal use when temporal resolution
     is below 60 minutes and the source is not stale.

2. RADAR_GAUGE
   - Role: PRIMARY
   - Second priority when reliable, healthy and fresh.
   - Spatial-grid observation calibrated or supported by gauge information.
   - May support minute-level operational use when temporal resolution
     is below 60 minutes.

3. SATELLITE
   - Role: SUPPORTING
   - Must not be treated as PRIMARY in this contract.
   - Used to support or fill gaps when local/radar sources are unavailable.
   - Spatial and temporal resolution must remain explicit.

4. REANALYSIS
   - Role: FALLBACK
   - Lowest operational priority.
   - Used only when higher-priority observations are unavailable.
   - Must not be presented as minute-level hyperlocal evidence.

## Required Metadata

Every source record stores:

- source_id
- source_type
- role
- priority
- temporal_resolution_minutes
- spatial_resolution_m
- spatial_support
- age_seconds
- max_age_seconds
- reliability status / score
- fallback_rule
- provenance_status
- stale state
- minute-level hyperlocal eligibility

## Freshness Rule

A source is stale when:

`age_seconds > max_age_seconds`

Stale sources are ranked below usable fresh sources.

## Hyperlocal Rule

A source is minute-level hyperlocal eligible only when all of the following
are true:

- type is LOCAL_GAUGE or RADAR_GAUGE
- role is PRIMARY
- source is reliable
- source is not stale
- temporal resolution is less than 60 minutes

Satellite and reanalysis products therefore cannot silently become
minute-level hyperlocal evidence.

## Development Artifact

`data/processed/source_hierarchy_dev.csv`

This artifact is synthetic and development-only. Its `DEV_` identifiers
and `SYNTHETIC_DEV` provenance must not be interpreted as measurements
from the Mandi/Pandoh pilot.
