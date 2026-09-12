# B05 — External-Source Connector Adapters

## Purpose

Normalize heterogeneous external data sources into one backend observation
contract before downstream models or APIs consume them.

## Shared Contract

Every normalized record preserves:

- source ID
- source type
- metric
- observed timestamp
- ingestion timestamp
- value and unit
- temporal resolution
- spatial resolution
- source age / freshness
- ingestion latency
- provenance status
- adapter identity

Missing values remain missing and are never silently converted to zero.

## Implemented DEV Adapters

### CSV Rainfall

Adapter:

`backend/app/connectors/csv_rainfall.py`

Normalizes rainfall CSV input into the shared observation schema.

### GeoJSON Hydrology

Adapter:

`backend/app/connectors/geojson_hydrology.py`

Normalizes water-level GeoJSON input into the same schema.

## Forecast and GIS Feeds

The `ExternalSourceAdapter` interface is source-agnostic and is the extension
point for official forecast and GIS providers.

No live provider URL/API credentials are currently frozen in project
configuration, so B05 uses deterministic local/mock fixtures as explicitly
allowed by the task contract.

Existing T03 GIS acquisition scripts remain the static-GIS ingestion path;
future remote forecast/GIS connectors must normalize metadata through the same
source/resolution/freshness/latency/provenance principles.

## Development Fixtures

- `data/external/dev/rainfall_source.csv`
- `data/external/dev/hydrology_source.geojson`

Normalized artifact:

- `data/processed/external_sources_normalized_dev.csv`

All `DEV_` identifiers are synthetic development data and are not real
Mandi/Pandoh observations.
