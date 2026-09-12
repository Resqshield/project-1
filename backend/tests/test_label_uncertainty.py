from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.data.build_master_event_dataset import (
    build_master_event_records,
)
from backend.app.data.master_event import MasterEventRecord


UTC = timezone.utc


def weak_record(**overrides):
    start = datetime(
        2023, 8, 22, 6, 0, tzinfo=UTC
    )

    payload = {
        "event_id": "T34_WEAK_EVENT_001",
        "timestamp": start,
        "pilot_id": "HP_MANDI_PANDOH_CORRIDOR",
        "region_code": "HP_MANDI",
        "hazard_label": "LANDSLIDE",
        "label_confidence": 0.55,
        "label_window_start": start,
        "label_window_end": (
            start + timedelta(hours=6)
        ),
        "location_precision": (
            "Approximate settlement-level location"
        ),
        "location_uncertain": True,
        "source_id": "T34_TEST_SOURCE",
        "source_type": "event_inventory",
        "source_timestamp": start,
        "provenance_status": "REPORTED_UNCERTAIN",
    }

    payload.update(overrides)
    return payload


def test_weak_label_is_retained_with_confidence():
    row = MasterEventRecord(**weak_record())

    assert row.hazard_label == "LANDSLIDE"
    assert row.label_confidence == 0.55
    assert row.location_uncertain is True


def test_uncertainty_time_window_is_retained():
    row = MasterEventRecord(**weak_record())

    assert row.label_window_start is not None
    assert row.label_window_end is not None
    assert (
        row.label_window_end
        > row.label_window_start
    )


def test_reversed_uncertainty_window_is_rejected():
    start = datetime(
        2023, 8, 22, 6, 0, tzinfo=UTC
    )

    with pytest.raises(ValidationError):
        MasterEventRecord(
            **weak_record(
                label_window_start=(
                    start + timedelta(hours=6)
                ),
                label_window_end=start,
            )
        )


def test_partial_uncertainty_window_is_rejected():
    with pytest.raises(ValidationError):
        MasterEventRecord(
            **weak_record(
                label_window_end=None
            )
        )


def test_uncertain_location_requires_precision():
    with pytest.raises(ValidationError):
        MasterEventRecord(
            **weak_record(
                location_precision=None
            )
        )


def test_verified_replay_events_preserve_real_uncertainty():
    rows = build_master_event_records()

    flood = next(
        row
        for row in rows
        if row.hazard_label == "FLOOD"
    )

    landslide = next(
        row
        for row in rows
        if row.hazard_label == "LANDSLIDE"
    )

    assert flood.label_window_start.date().isoformat() == (
        "2023-07-07"
    )
    assert flood.label_window_end.date().isoformat() == (
        "2023-07-11"
    )

    assert flood.location_uncertain is True
    assert flood.location_precision is not None

    assert landslide.label_window_start.date().isoformat() == (
        "2023-08-14"
    )
    assert landslide.label_window_end.date().isoformat() == (
        "2023-08-14"
    )

    assert landslide.location_uncertain is True
    assert landslide.location_precision is not None
