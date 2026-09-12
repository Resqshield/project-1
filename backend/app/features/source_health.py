"""Source-health evaluation for T11.

Determines whether a sensor/data source is healthy, degraded,
stale, offline, or unknown using existing telemetry metadata.

This module does not infer missing measurements as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional


DEFAULT_STALE_AFTER_SECONDS = 3 * 3600.0
DEFAULT_OFFLINE_AFTER_SECONDS = 12 * 3600.0
DEFAULT_DEGRADED_INGESTION_LAG_SECONDS = 15 * 60.0
DEFAULT_DEGRADED_PROBLEM_RATIO = 0.25


class SourceHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceObservationRecord:
    observed_at: datetime
    ingested_at: datetime
    quality_flag: str = "VALID"


@dataclass(frozen=True)
class SourceHealthResult:
    source_id: str
    sensor_status: str
    health_state: str
    evaluated_at: datetime
    latest_observed_at: Optional[datetime]
    latest_ingested_at: Optional[datetime]
    observation_age_seconds: Optional[float]
    ingestion_lag_seconds: Optional[float]
    total_observations: int
    valid_observations: int
    problem_observations: int
    problem_ratio: Optional[float]
    reason_codes: tuple[str, ...]
    availability: bool
    last_timestamp: Optional[datetime]
    freshness_seconds: Optional[float]
    reliability_score: Optional[float]
    coverage_ratio: float
    consistency_score: Optional[float]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            f"Timestamp must be timezone-aware (got naive: {value})"
        )

    return value.astimezone(timezone.utc)


def _extract_record(obj: Any) -> SourceObservationRecord:
    if isinstance(obj, SourceObservationRecord):
        return SourceObservationRecord(
            observed_at=_ensure_utc(obj.observed_at),
            ingested_at=_ensure_utc(obj.ingested_at),
            quality_flag=(obj.quality_flag or "VALID").upper(),
        )

    if isinstance(obj, dict):
        return SourceObservationRecord(
            observed_at=_ensure_utc(obj["observed_at"]),
            ingested_at=_ensure_utc(obj["ingested_at"]),
            quality_flag=(
                obj.get("quality_flag", "VALID") or "VALID"
            ).upper(),
        )

    return SourceObservationRecord(
        observed_at=_ensure_utc(
            getattr(obj, "observed_at")
        ),
        ingested_at=_ensure_utc(
            getattr(obj, "ingested_at")
        ),
        quality_flag=(
            getattr(obj, "quality_flag", "VALID")
            or "VALID"
        ).upper(),
    )


def evaluate_source_health(
    source_id: str,
    sensor_status: str,
    observations: Iterable[Any],
    evaluation_time: datetime,
    *,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    offline_after_seconds: float = DEFAULT_OFFLINE_AFTER_SECONDS,
    degraded_ingestion_lag_seconds: float = (
        DEFAULT_DEGRADED_INGESTION_LAG_SECONDS
    ),
    degraded_problem_ratio: float = DEFAULT_DEGRADED_PROBLEM_RATIO,
) -> SourceHealthResult:
    """Evaluate the current health of one sensor/data source."""

    if not source_id.strip():
        raise ValueError("source_id must not be blank")

    if stale_after_seconds < 0:
        raise ValueError("stale_after_seconds must be non-negative")

    if offline_after_seconds <= stale_after_seconds:
        raise ValueError(
            "offline_after_seconds must be greater than stale_after_seconds"
        )

    if not 0.0 <= degraded_problem_ratio <= 1.0:
        raise ValueError(
            "degraded_problem_ratio must be between 0 and 1"
        )

    eval_utc = _ensure_utc(evaluation_time)
    sensor_status_normalized = (
        sensor_status or "UNKNOWN"
    ).upper()

    records = [
        _extract_record(item)
        for item in observations
    ]

    # Do not use observations from the future.
    records = [
        record
        for record in records
        if record.observed_at <= eval_utc
    ]

    records.sort(
        key=lambda record: record.observed_at
    )

    reason_codes: list[str] = []

    explicitly_offline = sensor_status_normalized in {
        "OFFLINE",
        "DISABLED",
        "INACTIVE",
    }

    if not records:
        if explicitly_offline:
            state = SourceHealthState.OFFLINE
            reason_codes.append("SENSOR_STATUS_OFFLINE")
        else:
            state = SourceHealthState.UNKNOWN
            reason_codes.append("NO_OBSERVATIONS")

        return SourceHealthResult(
            source_id=source_id,
            sensor_status=sensor_status_normalized,
            health_state=state.value,
            evaluated_at=eval_utc,
            latest_observed_at=None,
            latest_ingested_at=None,
            observation_age_seconds=None,
            ingestion_lag_seconds=None,
            total_observations=0,
            valid_observations=0,
            problem_observations=0,
            problem_ratio=None,
            reason_codes=tuple(reason_codes),
            availability=False,
            last_timestamp=None,
            freshness_seconds=None,
            reliability_score=None,
            coverage_ratio=0.0,
            consistency_score=None,
        )

    latest = records[-1]

    observation_age = (
        eval_utc - latest.observed_at
    ).total_seconds()

    ingestion_lag = max(
        0.0,
        (
            latest.ingested_at
            - latest.observed_at
        ).total_seconds(),
    )

    problem_flags = {
        "SUSPECT",
        "MISSING",
        "ERROR",
    }

    problem_count = sum(
        record.quality_flag in problem_flags
        for record in records
    )

    valid_count = len(records) - problem_count

    problem_ratio = (
        problem_count / len(records)
    )

    reliability_score = valid_count / len(records)

    covered_count = sum(
        record.quality_flag not in {
            "MISSING",
            "ERROR",
        }
        for record in records
    )

    coverage_ratio = covered_count / len(records)

    consistent_count = sum(
        max(
            0.0,
            (
                record.ingested_at
                - record.observed_at
            ).total_seconds(),
        )
        <= degraded_ingestion_lag_seconds
        for record in records
    )

    consistency_score = (
        consistent_count / len(records)
    )

    if explicitly_offline:
        state = SourceHealthState.OFFLINE
        reason_codes.append("SENSOR_STATUS_OFFLINE")

    elif observation_age > offline_after_seconds:
        state = SourceHealthState.OFFLINE
        reason_codes.append("OBSERVATION_TOO_OLD")

    elif observation_age > stale_after_seconds:
        state = SourceHealthState.STALE
        reason_codes.append("OBSERVATION_STALE")

    else:
        degraded = False

        if sensor_status_normalized in {
            "DEGRADED",
            "MAINTENANCE",
        }:
            degraded = True
            reason_codes.append(
                "SENSOR_STATUS_DEGRADED"
            )

        if latest.quality_flag in problem_flags:
            degraded = True
            reason_codes.append(
                "LATEST_QUALITY_PROBLEM"
            )

        if problem_ratio >= degraded_problem_ratio:
            degraded = True
            reason_codes.append(
                "HIGH_PROBLEM_RATIO"
            )

        if (
            ingestion_lag
            > degraded_ingestion_lag_seconds
        ):
            degraded = True
            reason_codes.append(
                "HIGH_INGESTION_LAG"
            )

        if degraded:
            state = SourceHealthState.DEGRADED
        else:
            state = SourceHealthState.HEALTHY
            reason_codes.append("SOURCE_OK")

    return SourceHealthResult(
        source_id=source_id,
        sensor_status=sensor_status_normalized,
        health_state=state.value,
        evaluated_at=eval_utc,
        latest_observed_at=latest.observed_at,
        latest_ingested_at=latest.ingested_at,
        observation_age_seconds=round(
            observation_age,
            3,
        ),
        ingestion_lag_seconds=round(
            ingestion_lag,
            3,
        ),
        total_observations=len(records),
        valid_observations=valid_count,
        problem_observations=problem_count,
        problem_ratio=round(
            problem_ratio,
            4,
        ),
        reason_codes=tuple(reason_codes),
        availability=state not in {
            SourceHealthState.OFFLINE,
            SourceHealthState.UNKNOWN,
        },
        last_timestamp=latest.observed_at,
        freshness_seconds=round(
            observation_age,
            3,
        ),
        reliability_score=round(
            reliability_score,
            4,
        ),
        coverage_ratio=round(
            coverage_ratio,
            4,
        ),
        consistency_score=round(
            consistency_score,
            4,
        ),
    )
