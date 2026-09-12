"""Normalized contract shared by all B05 external-source adapters."""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        timestamp = value
    else:
        timestamp = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )

    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
    ):
        raise ValueError(
            "external-source timestamp must be timezone-aware"
        )

    return timestamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class NormalizedExternalRecord:
    source_id: str
    source_type: str
    metric: str
    observed_at: datetime
    ingested_at: datetime
    value: Optional[float]
    unit: str
    temporal_resolution_minutes: Optional[float]
    spatial_resolution_m: Optional[float]
    source_age_seconds: float
    latency_seconds: float
    provenance_status: str
    adapter_name: str

    def __post_init__(self) -> None:
        for name, value in (
            ("source_id", self.source_id),
            ("source_type", self.source_type),
            ("metric", self.metric),
            ("unit", self.unit),
            ("provenance_status", self.provenance_status),
            ("adapter_name", self.adapter_name),
        ):
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if self.source_age_seconds < 0:
            raise ValueError(
                "source_age_seconds must be non-negative"
            )

        if self.latency_seconds < 0:
            raise ValueError(
                "latency_seconds must be non-negative"
            )

        if (
            self.temporal_resolution_minutes is not None
            and self.temporal_resolution_minutes <= 0
        ):
            raise ValueError(
                "temporal resolution must be > 0"
            )

        if (
            self.spatial_resolution_m is not None
            and self.spatial_resolution_m <= 0
        ):
            raise ValueError(
                "spatial resolution must be > 0"
            )

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["observed_at"] = self.observed_at.isoformat()
        row["ingested_at"] = self.ingested_at.isoformat()
        return row


class ExternalSourceAdapter(ABC):
    @abstractmethod
    def normalize(
        self,
        payload: Any,
        evaluation_time: datetime,
    ) -> list[NormalizedExternalRecord]:
        """Convert one external format into the shared schema."""


def build_record(
    *,
    source_id: str,
    source_type: str,
    metric: str,
    observed_at: str | datetime,
    ingested_at: str | datetime,
    evaluation_time: datetime,
    value: Optional[float],
    unit: str,
    temporal_resolution_minutes: Optional[float],
    spatial_resolution_m: Optional[float],
    provenance_status: str,
    adapter_name: str,
) -> NormalizedExternalRecord:
    observed = parse_timestamp(observed_at)
    ingested = parse_timestamp(ingested_at)
    evaluated = parse_timestamp(evaluation_time)

    if observed > evaluated:
        raise ValueError(
            "future observation cannot be normalized"
        )

    if ingested < observed:
        raise ValueError(
            "ingested_at cannot precede observed_at"
        )

    return NormalizedExternalRecord(
        source_id=source_id,
        source_type=source_type,
        metric=metric,
        observed_at=observed,
        ingested_at=ingested,
        value=value,
        unit=unit,
        temporal_resolution_minutes=(
            temporal_resolution_minutes
        ),
        spatial_resolution_m=spatial_resolution_m,
        source_age_seconds=round(
            (evaluated - observed).total_seconds(),
            3,
        ),
        latency_seconds=round(
            (ingested - observed).total_seconds(),
            3,
        ),
        provenance_status=provenance_status,
        adapter_name=adapter_name,
    )


def write_normalized_records(
    records: Iterable[NormalizedExternalRecord],
    output_path: Path,
) -> Path:
    rows = [record.to_row() for record in records]

    if not rows:
        raise ValueError(
            "normalized connector output cannot be empty"
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
