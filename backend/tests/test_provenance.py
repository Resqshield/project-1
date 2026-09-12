from datetime import datetime, timezone

import pytest

from backend.app.data.provenance import (
    ProvenanceRecord,
    merge_provenance_metadata,
    provenance_from_metadata,
)


NOW = datetime(
    2026, 9, 12, 12, 0,
    tzinfo=timezone.utc,
)


def record(**overrides):
    payload = {
        "provenance_type": "MEASURED",
        "source_id": "DEV_SENSOR_001",
        "source_timestamp": NOW,
        "method": "direct_sensor_reading",
        "uncertainty_score": 0.05,
    }
    payload.update(overrides)
    return ProvenanceRecord(**payload)


@pytest.mark.parametrize(
    "kind",
    [
        "MEASURED",
        "IMPUTED",
        "FALLBACK_DERIVED",
        "MODEL_ESTIMATED",
    ],
)
def test_all_t72_provenance_types_are_supported(kind):
    row = record(provenance_type=kind)
    assert row.provenance_type == kind


def test_measured_value_is_visibly_measured():
    row = record()

    assert row.is_estimated is False
    assert row.display_badge == "MEASURED"


def test_imputed_value_is_visibly_estimated():
    row = record(
        provenance_type="IMPUTED",
        method="linear_interpolation",
    )

    assert row.is_estimated is True
    assert "ESTIMATED" in row.display_badge
    assert "IMPUTED" in row.display_badge


@pytest.mark.parametrize(
    "kind",
    [
        "FALLBACK_DERIVED",
        "MODEL_ESTIMATED",
    ],
)
def test_derived_values_never_look_measured(kind):
    row = record(
        provenance_type=kind,
    )

    assert row.is_estimated is True
    assert row.display_badge != "MEASURED"


def test_existing_sensor_metadata_is_preserved():
    provenance = record()

    metadata = merge_provenance_metadata(
        {
            "rssi": -78,
            "battery_v": 3.7,
        },
        provenance,
    )

    assert metadata["rssi"] == -78
    assert metadata["battery_v"] == 3.7
    assert "value_provenance" in metadata


def test_storage_metadata_round_trip():
    original = record(
        provenance_type="FALLBACK_DERIVED",
        source_id="DEV_SATELLITE_001",
        method="satellite_fallback",
        uncertainty_score=0.35,
    )

    metadata = merge_provenance_metadata(
        {},
        original,
    )

    restored = provenance_from_metadata(
        metadata
    )

    assert restored == original


def test_naive_source_timestamp_is_rejected():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        record(
            source_timestamp=datetime(
                2026, 9, 12, 12, 0
            )
        )


@pytest.mark.parametrize(
    "uncertainty",
    [-0.01, 1.01],
)
def test_invalid_uncertainty_is_rejected(
    uncertainty,
):
    with pytest.raises(ValueError):
        record(
            uncertainty_score=uncertainty
        )


def test_blank_method_is_rejected():
    with pytest.raises(ValueError):
        record(method=" ")


def test_technical_view_preserves_required_fields():
    row = record(
        provenance_type="MODEL_ESTIMATED",
        method="model_inference",
        uncertainty_score=0.2,
    )

    view = row.technical_view()

    assert view["source_id"] == "DEV_SENSOR_001"
    assert view["source_timestamp"]
    assert view["method"] == "model_inference"
    assert view["uncertainty_score"] == 0.2
    assert view["is_estimated"] is True
