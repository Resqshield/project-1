from datetime import datetime, timedelta, timezone

import pytest

from backend.app.features.wetness import (
    WetnessRecord,
    build_wetness_history,
    latest_wetness_state,
    write_wetness_feature_table,
)


EVAL = datetime(
    2026,
    9,
    12,
    12,
    0,
    tzinfo=timezone.utc,
)


def record(
    *,
    minutes_ago=10,
    value=55.0,
    quality="VALID",
    location="DEV_LOCATION_001",
    source_id="DEV_SENSOR_SOIL_001",
):
    return WetnessRecord(
        observed_at=EVAL - timedelta(
            minutes=minutes_ago
        ),
        location_id=location,
        numeric_value=value,
        unit="%",
        source_id=source_id,
        source="sensor_telemetry",
        source_type="local_sensor",
        quality_flag=quality,
        spatial_resolution_m=1.0,
        temporal_resolution_seconds=300.0,
        provenance_status="MEASURED",
    )


def test_valid_wetness_retains_source_resolution_and_freshness():
    rows = build_wetness_history(
        [record(value=61.5)],
        EVAL,
    )

    assert len(rows) == 1

    row = rows[0]

    assert row.wetness_value == 61.5
    assert row.wetness_unit == "%"
    assert row.location_id == "DEV_LOCATION_001"
    assert row.source_id == "DEV_SENSOR_SOIL_001"
    assert row.source == "sensor_telemetry"
    assert row.source_type == "local_sensor"
    assert row.spatial_resolution_m == 1.0
    assert row.temporal_resolution_seconds == 300.0
    assert row.source_age_seconds == 600.0
    assert row.quality_status == "VALID"
    assert row.is_stale is False
    assert row.provenance_status == "MEASURED"


def test_missing_wetness_is_none_not_zero():
    rows = build_wetness_history(
        [
            record(
                value=None,
                quality="MISSING",
            )
        ],
        EVAL,
    )

    row = rows[0]

    assert row.wetness_value is None
    assert row.quality_status == "MISSING"
    assert row.wetness_value != 0.0


def test_real_zero_is_preserved_as_zero():
    rows = build_wetness_history(
        [record(value=0.0)],
        EVAL,
    )

    row = rows[0]

    assert row.wetness_value == 0.0
    assert row.quality_status == "VALID"


def test_stale_wetness_is_explicit():
    rows = build_wetness_history(
        [record(minutes_ago=240, value=48.0)],
        EVAL,
        stale_threshold_seconds=3 * 3600,
    )

    row = rows[0]

    assert row.wetness_value == 48.0
    assert row.is_stale is True
    assert row.quality_status == "STALE"
    assert row.source_age_seconds == 14400.0


def test_suspect_value_is_not_silently_removed():
    rows = build_wetness_history(
        [
            record(
                value=82.0,
                quality="SUSPECT",
            )
        ],
        EVAL,
    )

    row = rows[0]

    assert row.wetness_value == 82.0
    assert row.quality_status == "SUSPECT"


def test_future_observation_is_excluded():
    future = WetnessRecord(
        observed_at=EVAL + timedelta(minutes=5),
        location_id="DEV_LOCATION_001",
        numeric_value=75.0,
        unit="%",
        source_id="DEV_SENSOR_SOIL_001",
    )

    rows = build_wetness_history(
        [record(), future],
        EVAL,
    )

    assert len(rows) == 1
    assert rows[0].timestamp <= EVAL


def test_naive_timestamp_is_rejected():
    naive = WetnessRecord(
        observed_at=datetime(2026, 9, 12, 11, 0),
        location_id="DEV_LOCATION_001",
        numeric_value=50.0,
        unit="%",
        source_id="DEV_SENSOR_SOIL_001",
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_wetness_history(
            [naive],
            EVAL,
        )


def test_latest_state_uses_latest_timestamp():
    rows = build_wetness_history(
        [
            record(
                minutes_ago=30,
                value=40.0,
            ),
            record(
                minutes_ago=5,
                value=65.0,
            ),
        ],
        EVAL,
    )

    latest = latest_wetness_state(rows)

    assert latest is not None
    assert latest.wetness_value == 65.0


def test_csv_export_keeps_missing_value_blank(tmp_path):
    rows = build_wetness_history(
        [
            record(
                value=None,
                quality="MISSING",
            )
        ],
        EVAL,
    )

    output = write_wetness_feature_table(
        rows,
        tmp_path / "wetness.csv",
    )

    text = output.read_text(
        encoding="utf-8"
    )

    assert "MISSING" in text

    data_line = text.splitlines()[1]
    columns = data_line.split(",")

    # wetness_value column is index 2.
    assert columns[2] == ""
