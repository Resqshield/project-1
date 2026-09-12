from pathlib import Path

import pytest

from backend.app.data.source_hierarchy import (
    SourceHierarchyRecord,
    rank_sources,
    write_source_hierarchy_table,
)


def source(**overrides):
    payload = {
        "source_id": "DEV_LOCAL_GAUGE_001",
        "source_type": "LOCAL_GAUGE",
        "role": "PRIMARY",
        "priority": 1,
        "temporal_resolution_minutes": 5.0,
        "spatial_resolution_m": None,
        "spatial_support": "POINT_MEASUREMENT",
        "age_seconds": 300.0,
        "max_age_seconds": 10800.0,
        "reliable": True,
        "reliability_score": 0.95,
        "fallback_rule": (
            "RADAR_GAUGE -> SATELLITE -> REANALYSIS"
        ),
        "provenance_status": "SYNTHETIC_DEV",
    }
    payload.update(overrides)
    return SourceHierarchyRecord(**payload)


def test_reliable_local_gauge_can_be_primary():
    row = source()

    assert row.role == "PRIMARY"
    assert row.minute_level_hyperlocal_eligible is True


def test_reliable_radar_gauge_can_be_primary():
    row = source(
        source_id="DEV_RADAR_001",
        source_type="RADAR_GAUGE",
        priority=2,
        spatial_resolution_m=1000.0,
        spatial_support="GRID_CELL",
    )

    assert row.minute_level_hyperlocal_eligible is True


@pytest.mark.parametrize(
    "source_type",
    ["SATELLITE", "REANALYSIS"],
)
def test_remote_sources_cannot_be_primary(source_type):
    with pytest.raises(ValueError):
        source(
            source_type=source_type,
            role="PRIMARY",
        )


def test_unreliable_source_cannot_be_primary():
    with pytest.raises(ValueError):
        source(reliable=False)


def test_stale_primary_source_is_not_hyperlocal_eligible():
    row = source(
        age_seconds=20000.0,
    )

    assert row.is_stale is True
    assert row.minute_level_hyperlocal_eligible is False


def test_daily_data_is_not_minute_level_hyperlocal():
    row = source(
        temporal_resolution_minutes=1440.0,
    )

    assert (
        row.minute_level_hyperlocal_eligible
        is False
    )


def test_rank_sources_prefers_non_stale_then_priority():
    records = [
        source(
            source_id="STALE_PRIMARY",
            priority=1,
            age_seconds=20000.0,
        ),
        source(
            source_id="FRESH_SECONDARY",
            source_type="RADAR_GAUGE",
            priority=2,
        ),
    ]

    ranked = rank_sources(records)

    assert ranked[0].source_id == "FRESH_SECONDARY"


def test_table_contains_t63_required_fields(tmp_path: Path):
    output = write_source_hierarchy_table(
        [source()],
        tmp_path / "source_hierarchy.csv",
    )

    text = output.read_text(
        encoding="utf-8"
    )

    for field in (
        "temporal_resolution_minutes",
        "spatial_resolution_m",
        "age_seconds",
        "priority",
        "fallback_rule",
        "is_stale",
        "minute_level_hyperlocal_eligible",
    ):
        assert field in text
