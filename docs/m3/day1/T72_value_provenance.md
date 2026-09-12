# T72 — Measured / Imputed / Fallback Provenance

## Canonical Value Provenance

Every derived or observed value must be distinguishable as one of:

- MEASURED
- IMPUTED
- FALLBACK_DERIVED
- MODEL_ESTIMATED

## Required Metadata

Each provenance record preserves:

- provenance type
- source ID
- source timestamp
- method
- uncertainty score

## Display Rule

Only MEASURED values may display as `MEASURED`.

IMPUTED, FALLBACK_DERIVED and MODEL_ESTIMATED values must display
an explicit `ESTIMATED` badge and must not appear equivalent to
directly measured observations.

## Observation Integration

The existing sensing model already stores `provenance_metadata`.

T72 stores canonical value-level provenance inside:

`provenance_metadata["value_provenance"]`

Existing sensor metadata such as RSSI and battery voltage is preserved.

## Missing Data

Missing observations are not converted to zero.

Provenance classification does not change the original measurement value.

## Development Artifact

`data/processed/provenance_examples_dev.csv`

This artifact is synthetic and development-only. DEV identifiers must not
be interpreted as real Mandi/Pandoh measurements.
