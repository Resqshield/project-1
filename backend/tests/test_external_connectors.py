from datetime import datetime, timezone

import pytest

from backend.app.connectors.csv_rainfall import CSVRainfallAdapter
from backend.app.connectors.geojson_hydrology import GeoJSONHydrologyAdapter


NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


CSV_PAYLOAD = """observed_at,ingested_at,rainfall_mm,unit
2026-09-12T11:50:00Z,2026-09-12T11:52:00Z,12.5,mm
2026-09-12T11:55:00Z,2026-09-12T11:56:00Z,,mm
"""


GEOJSON_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "observed_at": "2026-09-12T11:45:00Z",
                "ingested_at": "2026-09-12T11:48:00Z",
                "water_level_m": 1.85,
                "unit": "m",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [77.05, 31.67],
            },
        }
    ],
}


def test_csv_rainfall_normalizes_to_shared_schema():
    rows = CSVRainfallAdapter(
        source_id="DEV_RAIN_SOURCE",
        temporal_resolution_minutes=5.0,
        spatial_resolution_m=1000.0,
    ).normalize(CSV_PAYLOAD, NOW)

    assert len(rows) == 2
    assert rows[0].source_type == "RAINFALL"
    assert rows[0].metric == "rainfall_mm"
    assert rows[0].value == 12.5


def test_geojson_hydrology_normalizes_to_shared_schema():
    rows = GeoJSONHydrologyAdapter(
        source_id="DEV_HYDRO_SOURCE",
        temporal_resolution_minutes=15.0,
        spatial_resolution_m=500.0,
    ).normalize(GEOJSON_PAYLOAD, NOW)

    assert len(rows) == 1
    assert rows[0].source_type == "HYDROLOGY"
    assert rows[0].metric == "water_level_m"
    assert rows[0].value == 1.85


def test_two_formats_share_identical_internal_fields():
    rainfall = CSVRainfallAdapter(
        source_id="DEV_RAIN_SOURCE",
        temporal_resolution_minutes=5.0,
    ).normalize(CSV_PAYLOAD, NOW)[0]

    hydrology = GeoJSONHydrologyAdapter(
        source_id="DEV_HYDRO_SOURCE",
        temporal_resolution_minutes=15.0,
    ).normalize(GEOJSON_PAYLOAD, NOW)[0]

    assert rainfall.to_row().keys() == hydrology.to_row().keys()


def test_source_age_and_latency_are_retained():
    row = CSVRainfallAdapter(
        source_id="DEV_RAIN_SOURCE",
        temporal_resolution_minutes=5.0,
    ).normalize(CSV_PAYLOAD, NOW)[0]

    assert row.source_age_seconds == 600.0
    assert row.latency_seconds == 120.0


def test_resolution_is_retained():
    row = GeoJSONHydrologyAdapter(
        source_id="DEV_HYDRO_SOURCE",
        temporal_resolution_minutes=15.0,
        spatial_resolution_m=500.0,
    ).normalize(GEOJSON_PAYLOAD, NOW)[0]

    assert row.temporal_resolution_minutes == 15.0
    assert row.spatial_resolution_m == 500.0


def test_missing_external_value_remains_none():
    rows = CSVRainfallAdapter(
        source_id="DEV_RAIN_SOURCE",
        temporal_resolution_minutes=5.0,
    ).normalize(CSV_PAYLOAD, NOW)

    assert rows[1].value is None


def test_provenance_is_retained():
    row = CSVRainfallAdapter(
        source_id="DEV_RAIN_SOURCE",
        temporal_resolution_minutes=5.0,
        provenance_status="FALLBACK_DERIVED",
    ).normalize(CSV_PAYLOAD, NOW)[0]

    assert row.provenance_status == "FALLBACK_DERIVED"


def test_future_observation_is_rejected():
    payload = """observed_at,ingested_at,rainfall_mm,unit
2026-09-12T12:05:00Z,2026-09-12T12:06:00Z,1.0,mm
"""

    with pytest.raises(ValueError):
        CSVRainfallAdapter(
            source_id="DEV_RAIN_SOURCE",
            temporal_resolution_minutes=5.0,
        ).normalize(payload, NOW)


def test_negative_latency_is_rejected():
    payload = """observed_at,ingested_at,rainfall_mm,unit
2026-09-12T11:50:00Z,2026-09-12T11:49:00Z,1.0,mm
"""

    with pytest.raises(ValueError):
        CSVRainfallAdapter(
            source_id="DEV_RAIN_SOURCE",
            temporal_resolution_minutes=5.0,
        ).normalize(payload, NOW)
