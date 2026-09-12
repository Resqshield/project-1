"""Wetness / soil-moisture history features for T05.

Safety rules:
- Missing data is never converted to zero.
- Genuine numeric zero remains zero.
- Stale observations remain visible but are explicitly marked stale.
- Source, resolution, location, timestamp and provenance are preserved.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional


DEFAULT_STALE_THRESHOLD_SECONDS = 3 * 3600.0


class WetnessQualityStatus(str, Enum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    MISSING = "MISSING"
    STALE = "STALE"


@dataclass(frozen=True)
class WetnessRecord:
    observed_at: datetime
    location_id: str
    numeric_value: Optional[float]
    unit: str
    source_id: str
    source: str = "sensor_telemetry"
    source_type: str = "local_sensor"
    quality_flag: str = "VALID"
    spatial_resolution_m: Optional[float] = None
    temporal_resolution_seconds: Optional[float] = None
    provenance_status: str = "MEASURED"


@dataclass(frozen=True)
class WetnessFeatureRow:
    timestamp: datetime
    location_id: str
    wetness_value: Optional[float]
    wetness_unit: str
    source_id: str
    source: str
    source_type: str
    spatial_resolution_m: Optional[float]
    temporal_resolution_seconds: Optional[float]
    source_age_seconds: float
    quality_flag: str
    quality_status: str
    is_stale: bool
    provenance_status: str


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            f"Timestamp must be timezone-aware (got naive: {value})"
        )

    return value.astimezone(timezone.utc)


def _require_nonblank(value: Any, field_name: str) -> str:
    text = str(value).strip()

    if not text:
        raise ValueError(f"{field_name} must not be blank")

    return text


def _extract_record(obj: Any) -> WetnessRecord:
    if isinstance(obj, WetnessRecord):
        return obj

    if isinstance(obj, dict):
        return WetnessRecord(
            observed_at=obj["observed_at"],
            location_id=_require_nonblank(
                obj["location_id"],
                "location_id",
            ),
            numeric_value=obj.get("numeric_value"),
            unit=_require_nonblank(
                obj.get("unit", "%"),
                "unit",
            ),
            source_id=_require_nonblank(
                obj["source_id"],
                "source_id",
            ),
            source=obj.get(
                "source",
                "sensor_telemetry",
            ),
            source_type=obj.get(
                "source_type",
                "local_sensor",
            ),
            quality_flag=obj.get(
                "quality_flag",
                "VALID",
            ),
            spatial_resolution_m=obj.get(
                "spatial_resolution_m"
            ),
            temporal_resolution_seconds=obj.get(
                "temporal_resolution_seconds"
            ),
            provenance_status=obj.get(
                "provenance_status",
                "MEASURED",
            ),
        )

    return WetnessRecord(
        observed_at=getattr(obj, "observed_at"),
        location_id=_require_nonblank(
            getattr(
                obj,
                "location_id",
                f"sensor:{getattr(obj, 'sensor_id')}",
            ),
            "location_id",
        ),
        numeric_value=getattr(
            obj,
            "numeric_value",
            None,
        ),
        unit=getattr(obj, "unit", "%"),
        source_id=_require_nonblank(
            getattr(
                obj,
                "source_id",
                f"sensor:{getattr(obj, 'sensor_id')}",
            ),
            "source_id",
        ),
        source=getattr(
            obj,
            "source",
            "sensor_telemetry",
        ),
        source_type=getattr(
            obj,
            "source_type",
            "local_sensor",
        ),
        quality_flag=getattr(
            obj,
            "quality_flag",
            "VALID",
        ),
        spatial_resolution_m=getattr(
            obj,
            "spatial_resolution_m",
            None,
        ),
        temporal_resolution_seconds=getattr(
            obj,
            "temporal_resolution_seconds",
            None,
        ),
        provenance_status=getattr(
            obj,
            "provenance_status",
            "MEASURED",
        ),
    )


def build_wetness_history(
    records: Iterable[Any],
    evaluation_time: datetime,
    stale_threshold_seconds: float = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> list[WetnessFeatureRow]:
    """Normalize wetness history into an aligned feature table."""

    eval_utc = _ensure_utc(evaluation_time)

    normalized = []

    for obj in records:
        record = _extract_record(obj)
        observed_at = _ensure_utc(record.observed_at)

        # Future observation cannot be used for current/event state.
        if observed_at > eval_utc:
            continue

        age_seconds = (
            eval_utc - observed_at
        ).total_seconds()

        quality_flag = (
            record.quality_flag or "VALID"
        ).upper()

        missing = (
            record.numeric_value is None
            or quality_flag in {"MISSING", "ERROR"}
        )

        is_stale = (
            age_seconds > stale_threshold_seconds
        )

        if missing:
            value = None
            quality_status = (
                WetnessQualityStatus.MISSING.value
            )
        else:
            value = float(record.numeric_value)

            if is_stale:
                quality_status = (
                    WetnessQualityStatus.STALE.value
                )
            elif quality_flag == "SUSPECT":
                quality_status = (
                    WetnessQualityStatus.SUSPECT.value
                )
            else:
                quality_status = (
                    WetnessQualityStatus.VALID.value
                )

        normalized.append(
            WetnessFeatureRow(
                timestamp=observed_at,
                location_id=record.location_id,
                wetness_value=value,
                wetness_unit=record.unit,
                source_id=record.source_id,
                source=record.source,
                source_type=record.source_type,
                spatial_resolution_m=(
                    record.spatial_resolution_m
                ),
                temporal_resolution_seconds=(
                    record.temporal_resolution_seconds
                ),
                source_age_seconds=round(
                    age_seconds,
                    3,
                ),
                quality_flag=quality_flag,
                quality_status=quality_status,
                is_stale=is_stale,
                provenance_status=(
                    record.provenance_status
                ),
            )
        )

    normalized.sort(
        key=lambda row: (
            row.timestamp,
            row.location_id,
            row.source_id,
        )
    )

    return normalized


def latest_wetness_state(
    history: Iterable[WetnessFeatureRow],
) -> Optional[WetnessFeatureRow]:
    rows = list(history)

    if not rows:
        return None

    return max(
        rows,
        key=lambda row: row.timestamp,
    )


def write_wetness_feature_table(
    rows: Iterable[WetnessFeatureRow],
    output_path: str | Path,
) -> Path:
    """Write normalized wetness history as a reproducible CSV table."""

    output = Path(output_path)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    materialized = list(rows)

    fieldnames = [
        "timestamp",
        "location_id",
        "wetness_value",
        "wetness_unit",
        "source_id",
        "source",
        "source_type",
        "spatial_resolution_m",
        "temporal_resolution_seconds",
        "source_age_seconds",
        "quality_flag",
        "quality_status",
        "is_stale",
        "provenance_status",
    ]

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in materialized:
            data = asdict(row)

            data["timestamp"] = (
                row.timestamp.isoformat()
            )

            # csv writes None as an empty field:
            # missing value stays missing, never 0.
            writer.writerow(data)

    return output
