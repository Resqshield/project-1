"""Build the T02 canonical master-event replay dataset.

Uses verified 2023 hazard-history events from T03.
Environmental observations remain None when no time-aligned measured
source exists. Missing data is never converted to zero.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.data.master_event import MasterEventRecord


SOURCE = Path(
    "data/gis/hazard_history/"
    "verified_hazard_history_mandi_pandoh_2023.geojson"
)

OUTPUT = Path(
    "data/processed/master_event_replay_2023.csv"
)


HAZARD_LABELS = {
    "flood": "FLOOD",
    "landslide": "LANDSLIDE",
}


def build_master_event_records() -> list[MasterEventRecord]:
    data = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    rows: list[MasterEventRecord] = []

    for feature in data["features"]:
        props = feature["properties"]

        window_start = datetime.fromisoformat(
            props["start_date"]
        ).replace(tzinfo=timezone.utc)

        window_end = (
            datetime.fromisoformat(
                props["end_date"]
            ).replace(tzinfo=timezone.utc)
            + timedelta(days=1)
            - timedelta(microseconds=1)
        )

        geometry_precision = props.get(
            "geometry_precision"
        )

        precision_text = (
            geometry_precision or ""
        ).casefold()

        location_uncertain = (
            "centroid" in precision_text
            or "approx" in precision_text
        )

        hazard_type = props["hazard_type"].lower()

        if hazard_type not in HAZARD_LABELS:
            raise ValueError(
                f"Unsupported hazard type: {hazard_type}"
            )

        # VERIFIED means the event occurrence itself is supported
        # by an authoritative report. Geometry precision is tracked
        # separately in the hazard-history layer.
        label_confidence = 1.0

        rows.append(
            MasterEventRecord(
                event_id=props["event_id"],
                timestamp=window_start,
                pilot_id="HP_MANDI_PANDOH_CORRIDOR",
                region_code="HP_MANDI",
                catchment_code=None,
                village_code=None,

                # No aligned historical observation source has
                # been established for these event timestamps.
                rainfall_mm_30m=None,
                rainfall_mm_1h=None,
                rainfall_mm_3h=None,
                rainfall_mm_6h=None,
                rainfall_mm_24h=None,
                rainfall_mm_3d=None,
                rainfall_mm_7d=None,
                wetness_value=None,
                wetness_unit=None,
                water_level_m=None,

                # Event geometry uses settlement anchors, so we do
                # not pretend it is precise enough for local slope.
                slope_state=None,

                hazard_label=HAZARD_LABELS[
                    hazard_type
                ],
                label_confidence=label_confidence,
                label_window_start=window_start,
                label_window_end=window_end,
                location_precision=geometry_precision,
                location_uncertain=location_uncertain,

                source_id=props["event_id"],
                source_type="verified_event_inventory",
                source_timestamp=window_start,
                provenance_status="REPORTED_VERIFIED",
            )
        )

    rows.sort(
        key=lambda row: (
            row.timestamp,
            row.event_id,
        )
    )

    return rows


def write_master_event_dataset(
    rows: list[MasterEventRecord],
) -> Path:
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialized = [
        row.model_dump(mode="json")
        for row in rows
    ]

    if not serialized:
        raise RuntimeError(
            "No master-event records generated"
        )

    fieldnames = list(serialized[0].keys())

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(serialized)

    return OUTPUT


def main() -> None:
    rows = build_master_event_records()
    output = write_master_event_dataset(rows)

    print("Created:", output)
    print("Rows:", len(rows))
    print(
        "Hazards:",
        sorted(
            row.hazard_label
            for row in rows
        ),
    )
    print(
        "Missing rainfall rows:",
        sum(
            row.rainfall_mm_24h is None
            for row in rows
        ),
    )
    print(
        "Missing wetness rows:",
        sum(
            row.wetness_value is None
            for row in rows
        ),
    )
    print(
        "Fake zero imputation: NO"
    )


if __name__ == "__main__":
    main()
