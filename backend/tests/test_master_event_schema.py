from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.data.master_event import MasterEventRecord


def valid_record(**overrides):
    payload = {
        "event_id": "T02_TEST_EVENT_001",
        "timestamp": datetime(2023, 7, 9, 12, 0, tzinfo=timezone.utc),
        "pilot_id": "HP_MANDI_PANDOH_CORRIDOR",
        "region_code": "HP_MANDI",
        "catchment_code": None,
        "village_code": None,
        "rainfall_mm_30m": None,
        "rainfall_mm_1h": None,
        "rainfall_mm_3h": None,
        "rainfall_mm_6h": None,
        "rainfall_mm_24h": None,
        "rainfall_mm_3d": None,
        "rainfall_mm_7d": None,
        "wetness_value": None,
        "wetness_unit": None,
        "water_level_m": None,
        "slope_state": None,
        "hazard_label": "FLASH_FLOOD",
        "label_confidence": 0.90,
        "source_id": "TEST_SOURCE",
        "source_type": "event_inventory",
        "source_timestamp": datetime(2023, 7, 9, 12, 0, tzinfo=timezone.utc),
        "provenance_status": "MEASURED_OR_REPORTED",
    }
    payload.update(overrides)
    return payload


def test_valid_master_event_record():
    row = MasterEventRecord(**valid_record())

    assert row.pilot_id == "HP_MANDI_PANDOH_CORRIDOR"
    assert row.hazard_label == "FLASH_FLOOD"
    assert row.label_confidence == 0.90


def test_missing_environmental_data_remains_null():
    row = MasterEventRecord(**valid_record())

    assert row.rainfall_mm_1h is None
    assert row.wetness_value is None
    assert row.water_level_m is None


def test_naive_event_timestamp_rejected():
    with pytest.raises(ValidationError):
        MasterEventRecord(
            **valid_record(timestamp=datetime(2023, 7, 9, 12, 0))
        )


def test_naive_source_timestamp_rejected():
    with pytest.raises(ValidationError):
        MasterEventRecord(
            **valid_record(source_timestamp=datetime(2023, 7, 9, 12, 0))
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_label_confidence_outside_zero_one_rejected(confidence):
    with pytest.raises(ValidationError):
        MasterEventRecord(**valid_record(label_confidence=confidence))


def test_source_provenance_is_required():
    payload = valid_record()
    del payload["source_id"]

    with pytest.raises(ValidationError):
        MasterEventRecord(**payload)
