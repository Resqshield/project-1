import csv

from backend.app.data.build_master_event_dataset import (
    build_master_event_records,
    write_master_event_dataset,
)


def test_builds_two_verified_replay_events():
    rows = build_master_event_records()

    assert len(rows) == 2
    assert {
        row.hazard_label
        for row in rows
    } == {
        "FLOOD",
        "LANDSLIDE",
    }


def test_all_records_use_frozen_pilot():
    rows = build_master_event_records()

    assert all(
        row.pilot_id
        == "HP_MANDI_PANDOH_CORRIDOR"
        for row in rows
    )


def test_missing_environmental_values_are_not_zero():
    rows = build_master_event_records()

    for row in rows:
        assert row.rainfall_mm_24h is None
        assert row.wetness_value is None
        assert row.water_level_m is None


def test_verified_event_provenance_is_retained():
    rows = build_master_event_records()

    for row in rows:
        assert (
            row.source_type
            == "verified_event_inventory"
        )
        assert (
            row.provenance_status
            == "REPORTED_VERIFIED"
        )
        assert row.label_confidence == 1.0


def test_master_event_csv_contains_required_columns():
    rows = build_master_event_records()
    output = write_master_event_dataset(rows)

    with output.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        csv_rows = list(
            csv.DictReader(handle)
        )

    assert len(csv_rows) == 2

    required = {
        "timestamp",
        "region_code",
        "rainfall_mm_24h",
        "wetness_value",
        "water_level_m",
        "slope_state",
        "hazard_label",
        "label_confidence",
        "source_id",
        "source_type",
        "source_timestamp",
        "provenance_status",
    }

    assert required.issubset(
        csv_rows[0].keys()
    )


def test_csv_missing_values_remain_blank():
    rows = build_master_event_records()
    output = write_master_event_dataset(rows)

    with output.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        csv_rows = list(
            csv.DictReader(handle)
        )

    assert all(
        row["rainfall_mm_24h"] == ""
        for row in csv_rows
    )

    assert all(
        row["wetness_value"] == ""
        for row in csv_rows
    )

    assert all(
        row["water_level_m"] == ""
        for row in csv_rows
    )
