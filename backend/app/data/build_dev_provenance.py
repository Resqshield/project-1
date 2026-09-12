"""Build deterministic DEV-only provenance examples for T72."""

import csv
from datetime import datetime, timezone
from pathlib import Path

from backend.app.data.provenance import ProvenanceRecord


OUTPUT = Path("data/processed/provenance_examples_dev.csv")

NOW = datetime(
    2026, 9, 12, 12, 0,
    tzinfo=timezone.utc,
)


def build_rows():
    return [
        ProvenanceRecord(
            provenance_type="MEASURED",
            source_id="DEV_SENSOR_001",
            source_timestamp=NOW,
            method="direct_sensor_reading",
            uncertainty_score=0.05,
        ),
        ProvenanceRecord(
            provenance_type="IMPUTED",
            source_id="DEV_SENSOR_001",
            source_timestamp=NOW,
            method="linear_interpolation",
            uncertainty_score=0.25,
        ),
        ProvenanceRecord(
            provenance_type="FALLBACK_DERIVED",
            source_id="DEV_SATELLITE_001",
            source_timestamp=NOW,
            method="satellite_fallback",
            uncertainty_score=0.35,
        ),
        ProvenanceRecord(
            provenance_type="MODEL_ESTIMATED",
            source_id="DEV_MODEL_001",
            source_timestamp=NOW,
            method="model_inference",
            uncertainty_score=0.20,
        ),
    ]


def main():
    rows = build_rows()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = [
        row.technical_view()
        for row in rows
    ]

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(data[0].keys()),
        )
        writer.writeheader()
        writer.writerows(data)

    print("Created:", OUTPUT)
    print("Rows:", len(rows))
    print(
        "Types:",
        sorted(
            row.provenance_type
            for row in rows
        ),
    )
    print(
        "Estimated rows:",
        sum(
            row.is_estimated
            for row in rows
        ),
    )


if __name__ == "__main__":
    main()
