"""Build deterministic DEV-only normalized external-source artifact for B05."""

from datetime import datetime, timezone
from pathlib import Path

from backend.app.connectors.base import write_normalized_records
from backend.app.connectors.csv_rainfall import CSVRainfallAdapter
from backend.app.connectors.geojson_hydrology import GeoJSONHydrologyAdapter


RAIN_FILE = Path("data/external/dev/rainfall_source.csv")
HYDRO_FILE = Path("data/external/dev/hydrology_source.geojson")
OUTPUT = Path("data/processed/external_sources_normalized_dev.csv")

EVALUATION_TIME = datetime(
    2026, 9, 12, 12, 0,
    tzinfo=timezone.utc,
)


def build_records():
    rainfall = CSVRainfallAdapter(
        source_id="DEV_RAIN_SOURCE",
        temporal_resolution_minutes=5.0,
        spatial_resolution_m=1000.0,
        provenance_status="MEASURED",
    ).normalize(
        RAIN_FILE.read_text(encoding="utf-8-sig"),
        EVALUATION_TIME,
    )

    hydrology = GeoJSONHydrologyAdapter(
        source_id="DEV_HYDRO_SOURCE",
        temporal_resolution_minutes=15.0,
        spatial_resolution_m=500.0,
        provenance_status="MEASURED",
    ).normalize(
        HYDRO_FILE.read_text(encoding="utf-8-sig"),
        EVALUATION_TIME,
    )

    return rainfall + hydrology


def main():
    records = build_records()

    output = write_normalized_records(
        records,
        OUTPUT,
    )

    print("Created:", output)
    print("Rows:", len(records))
    print(
        "Adapters:",
        sorted(
            {
                row.adapter_name
                for row in records
            }
        ),
    )
    print(
        "Missing values:",
        sum(
            row.value is None
            for row in records
        ),
    )
    print(
        "Source types:",
        sorted(
            {
                row.source_type
                for row in records
            }
        ),
    )


if __name__ == "__main__":
    main()
