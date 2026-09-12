"""T63 rainfall/source hierarchy and time-resolution audit."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional


class RainfallSourceType(str, Enum):
    LOCAL_GAUGE = "LOCAL_GAUGE"
    RADAR_GAUGE = "RADAR_GAUGE"
    SATELLITE = "SATELLITE"
    REANALYSIS = "REANALYSIS"


class SourceRole(str, Enum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    FALLBACK = "FALLBACK"


@dataclass(frozen=True)
class SourceHierarchyRecord:
    source_id: str
    source_type: str
    role: str
    priority: int

    temporal_resolution_minutes: float
    spatial_resolution_m: Optional[float]
    spatial_support: str

    age_seconds: float
    max_age_seconds: float

    reliable: bool
    reliability_score: Optional[float]

    fallback_rule: str
    provenance_status: str

    def __post_init__(self) -> None:
        source_type = RainfallSourceType(
            self.source_type
        )
        role = SourceRole(self.role)

        for field_name, value in (
            ("source_id", self.source_id),
            ("spatial_support", self.spatial_support),
            ("fallback_rule", self.fallback_rule),
            ("provenance_status", self.provenance_status),
        ):
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if self.priority < 1:
            raise ValueError(
                "priority must be >= 1"
            )

        if self.temporal_resolution_minutes <= 0:
            raise ValueError(
                "temporal_resolution_minutes must be > 0"
            )

        if (
            self.spatial_resolution_m is not None
            and self.spatial_resolution_m <= 0
        ):
            raise ValueError(
                "spatial_resolution_m must be > 0 when supplied"
            )

        if self.age_seconds < 0:
            raise ValueError(
                "age_seconds must be non-negative"
            )

        if self.max_age_seconds <= 0:
            raise ValueError(
                "max_age_seconds must be > 0"
            )

        if (
            self.reliability_score is not None
            and not 0.0 <= self.reliability_score <= 1.0
        ):
            raise ValueError(
                "reliability_score must be between 0 and 1"
            )

        if role == SourceRole.PRIMARY:
            if source_type not in {
                RainfallSourceType.LOCAL_GAUGE,
                RainfallSourceType.RADAR_GAUGE,
            }:
                raise ValueError(
                    "satellite/reanalysis cannot be PRIMARY"
                )

            if not self.reliable:
                raise ValueError(
                    "PRIMARY rainfall source must be reliable"
                )

    @property
    def is_stale(self) -> bool:
        return self.age_seconds > self.max_age_seconds

    @property
    def minute_level_hyperlocal_eligible(self) -> bool:
        source_type = RainfallSourceType(
            self.source_type
        )
        role = SourceRole(self.role)

        return (
            source_type
            in {
                RainfallSourceType.LOCAL_GAUGE,
                RainfallSourceType.RADAR_GAUGE,
            }
            and role == SourceRole.PRIMARY
            and self.reliable
            and not self.is_stale
            and self.temporal_resolution_minutes < 60
        )

    def to_row(self) -> dict:
        row = asdict(self)
        row["is_stale"] = self.is_stale
        row[
            "minute_level_hyperlocal_eligible"
        ] = self.minute_level_hyperlocal_eligible
        return row


def rank_sources(
    records: Iterable[SourceHierarchyRecord],
) -> list[SourceHierarchyRecord]:
    """Rank usable sources by staleness, priority, then age."""

    return sorted(
        records,
        key=lambda record: (
            record.is_stale,
            record.priority,
            record.age_seconds,
        ),
    )


def write_source_hierarchy_table(
    records: Iterable[SourceHierarchyRecord],
    output_path: Path,
) -> Path:
    rows = [
        record.to_row()
        for record in records
    ]

    if not rows:
        raise ValueError(
            "source hierarchy must contain at least one source"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    return output_path
