"""Build deterministic DEV-only rainfall source hierarchy for T63."""

from pathlib import Path

from backend.app.data.source_hierarchy import (
    SourceHierarchyRecord,
    write_source_hierarchy_table,
)


OUTPUT = Path(
    "data/processed/source_hierarchy_dev.csv"
)


def build_dev_source_hierarchy() -> list[SourceHierarchyRecord]:
    return [
        SourceHierarchyRecord(
            source_id="DEV_LOCAL_GAUGE_001",
            source_type="LOCAL_GAUGE",
            role="PRIMARY",
            priority=1,
            temporal_resolution_minutes=5.0,
            spatial_resolution_m=None,
            spatial_support="POINT_MEASUREMENT",
            age_seconds=300.0,
            max_age_seconds=10800.0,
            reliable=True,
            reliability_score=0.98,
            fallback_rule=(
                "RADAR_GAUGE -> SATELLITE -> REANALYSIS"
            ),
            provenance_status="SYNTHETIC_DEV",
        ),
        SourceHierarchyRecord(
            source_id="DEV_RADAR_GAUGE_001",
            source_type="RADAR_GAUGE",
            role="PRIMARY",
            priority=2,
            temporal_resolution_minutes=10.0,
            spatial_resolution_m=1000.0,
            spatial_support="GRID_CELL",
            age_seconds=600.0,
            max_age_seconds=10800.0,
            reliable=True,
            reliability_score=0.93,
            fallback_rule=(
                "SATELLITE -> REANALYSIS"
            ),
            provenance_status="SYNTHETIC_DEV",
        ),
        SourceHierarchyRecord(
            source_id="DEV_SATELLITE_001",
            source_type="SATELLITE",
            role="SUPPORTING",
            priority=3,
            temporal_resolution_minutes=30.0,
            spatial_resolution_m=10000.0,
            spatial_support="COARSE_GRID",
            age_seconds=1800.0,
            max_age_seconds=21600.0,
            reliable=True,
            reliability_score=0.85,
            fallback_rule="REANALYSIS",
            provenance_status="SYNTHETIC_DEV",
        ),
        SourceHierarchyRecord(
            source_id="DEV_REANALYSIS_001",
            source_type="REANALYSIS",
            role="FALLBACK",
            priority=4,
            temporal_resolution_minutes=360.0,
            spatial_resolution_m=25000.0,
            spatial_support="COARSE_GRID",
            age_seconds=7200.0,
            max_age_seconds=43200.0,
            reliable=True,
            reliability_score=0.80,
            fallback_rule="NO_LOWER_PRIORITY_SOURCE",
            provenance_status="SYNTHETIC_DEV",
        ),
    ]


def main() -> None:
    rows = build_dev_source_hierarchy()

    output = write_source_hierarchy_table(
        rows,
        OUTPUT,
    )

    print("Created:", output)
    print("Rows:", len(rows))
    print(
        "Primary:",
        [
            row.source_id
            for row in rows
            if row.role == "PRIMARY"
        ],
    )
    print(
        "Remote sources used as PRIMARY:",
        any(
            row.source_type
            in {"SATELLITE", "REANALYSIS"}
            and row.role == "PRIMARY"
            for row in rows
        ),
    )
    print(
        "Provenance:",
        sorted(
            {
                row.provenance_status
                for row in rows
            }
        ),
    )


if __name__ == "__main__":
    main()
