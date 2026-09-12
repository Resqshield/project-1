"""Generate deterministic DEV-only wetness history for T05 validation.

This file creates synthetic development fixtures only.
It must never be interpreted as real Mandi/Pandoh observations.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.features.wetness import (
    WetnessRecord,
    build_wetness_history,
    write_wetness_feature_table,
)


OUTPUT = Path(
    "data/processed/dev_wetness_history.csv"
)

EVALUATION_TIME = datetime(
    2026,
    9,
    12,
    12,
    0,
    tzinfo=timezone.utc,
)


def build_dev_records() -> list[WetnessRecord]:
    records = []

    start = EVALUATION_TIME - timedelta(hours=2)

    for index in range(25):
        observed_at = start + timedelta(
            minutes=index * 5
        )

        value = round(
            48.0 + ((index % 8) * 1.25),
            2,
        )

        quality = "VALID"

        # Explicit missing sample: never converted to zero.
        if index == 8:
            value = None
            quality = "MISSING"

        # Explicit suspect reading retained with its quality.
        if index == 15:
            value = 67.5
            quality = "SUSPECT"

        records.append(
            WetnessRecord(
                observed_at=observed_at,
                location_id="DEV_VILLAGE_001",
                numeric_value=value,
                unit="%",
                source_id="DEV_SENSOR_SOIL_001",
                source="synthetic_dev_fixture",
                source_type="dev_fixture",
                quality_flag=quality,
                spatial_resolution_m=1.0,
                temporal_resolution_seconds=300.0,
                provenance_status="SYNTHETIC_DEV",
            )
        )

    return records


def main() -> None:
    history = build_wetness_history(
        build_dev_records(),
        EVALUATION_TIME,
    )

    output = write_wetness_feature_table(
        history,
        OUTPUT,
    )

    print("Created:", output)
    print("Rows:", len(history))
    print(
        "Missing rows:",
        sum(
            row.wetness_value is None
            for row in history
        ),
    )
    print(
        "Suspect rows:",
        sum(
            row.quality_status == "SUSPECT"
            for row in history
        ),
    )
    print(
        "Provenance:",
        sorted(
            {
                row.provenance_status
                for row in history
            }
        ),
    )


if __name__ == "__main__":
    main()
