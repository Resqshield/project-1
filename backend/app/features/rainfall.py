"""Rainfall history and accumulation feature services (T04).

Converts timestamped environmental observations into historical accumulation
windows required by downstream hazard assessment and modeling pipelines.

REQUIRED WINDOWS (MANDATED BY T04):
- rain_30m : 30 minutes
- rain_1h  : 1 hour
- rain_3h  : 3 hours
- rain_6h  : 6 hours
- rain_24h : 24 hours
- rain_3d  : 3 days
- rain_7d  : 7 days

RAINFALL OBSERVATION SEMANTICS:
- Existing B02 rainfall observations represent INCREMENTAL precipitation (in mm)
  measured during the reporting interval ending at ``observed_at``.
- Accumulation across an interval is therefore the sum of all valid incremental
  readings whose timestamps fall strictly within the evaluation window:
      (evaluation_time - window_duration, evaluation_time]
- Boundary rule: Strictly open on the left, closed on the right.
  This guarantees adjacent non-overlapping intervals partition time without
  double-counting boundary observations.

CRITICAL SAFETY PRINCIPLE — MISSING DATA != ZERO:
- An absent or failed sensor reading (numeric_value is None or quality_flag == 'MISSING')
  is NEVER coerced to 0.0 mm.
- An empty window (0 samples) produces value=None with quality_status='EMPTY'.
- Genuine zero rainfall (all samples report 0.0 mm) produces value=0.0 with quality_status='COMPLETE'.
- Incomplete windows produce quality_status='PARTIAL' or 'MISSING' with an explicit
  coverage_ratio < 1.0.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.sensing import Observation, Sensor


class QualityStatus(str, Enum):
    """Quality / completeness state of an aggregated rainfall window."""

    COMPLETE = "COMPLETE"  # Window has all valid observations; no missing data
    PARTIAL = "PARTIAL"    # Window has some valid data, but also missing or incomplete coverage
    MISSING = "MISSING"    # Window contains only explicit missing/failed observations
    EMPTY = "EMPTY"        # Zero observations recorded in the window (distinct from 0.0 mm rain)
    STALE = "STALE"        # Latest reading exceeds the staleness threshold


# Standard 7 windows ordered by duration
STANDARD_WINDOWS: dict[str, timedelta] = {
    "rain_30m": timedelta(minutes=30),
    "rain_1h": timedelta(hours=1),
    "rain_3h": timedelta(hours=3),
    "rain_6h": timedelta(hours=6),
    "rain_24h": timedelta(hours=24),
    "rain_3d": timedelta(days=3),
    "rain_7d": timedelta(days=7),
}

# Default staleness threshold (e.g., 3 hours with no telemetry)
DEFAULT_STALE_THRESHOLD_SECONDS = 3 * 3600.0


@dataclass(frozen=True)
class RainfallFeatureResult:
    """Calculated accumulation feature for a single time window.

    Retains complete provenance, timestamps, quality flags, and freshness metadata.
    """

    window_name: str
    window_duration_seconds: float
    value: Optional[float]
    unit: str
    source_id: str
    evaluation_timestamp: datetime
    latest_observation_timestamp: Optional[datetime]
    source_age_seconds: Optional[float]
    coverage_ratio: float
    quality_status: str
    is_stale: bool
    valid_sample_count: int
    missing_sample_count: int
    total_sample_count: int
    partial_value: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a dictionary with ISO formatted datetimes."""
        d = asdict(self)
        d["evaluation_timestamp"] = self.evaluation_timestamp.isoformat()
        if self.latest_observation_timestamp is not None:
            d["latest_observation_timestamp"] = self.latest_observation_timestamp.isoformat()
        return d


@dataclass(frozen=True)
class RainfallRecord:
    """Normalized in-memory rainfall observation record."""

    observed_at: datetime
    numeric_value: Optional[float]
    quality_flag: str = "VALID"
    source: str = "sensor_telemetry"
    device_sequence: Optional[int] = None
    sensor_id: Optional[int | str] = None


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware and normalized to UTC."""
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp must be timezone-aware (got naive: {dt})")
    return dt.astimezone(timezone.utc)


def _extract_record(obj: Any) -> RainfallRecord:
    """Extract a RainfallRecord from an ORM Observation, dict, or tuple."""
    if isinstance(obj, RainfallRecord):
        return obj
    if isinstance(obj, Observation):
        return RainfallRecord(
            observed_at=_ensure_utc(obj.observed_at),
            numeric_value=obj.numeric_value,
            quality_flag=obj.quality_flag or "VALID",
            source=obj.source or "sensor_telemetry",
            device_sequence=obj.device_sequence,
            sensor_id=obj.sensor_id,
        )
    if isinstance(obj, dict):
        return RainfallRecord(
            observed_at=_ensure_utc(obj["observed_at"]),
            numeric_value=obj.get("numeric_value"),
            quality_flag=obj.get("quality_flag", "VALID"),
            source=obj.get("source", "sensor_telemetry"),
            device_sequence=obj.get("device_sequence"),
            sensor_id=obj.get("sensor_id"),
        )
    # Generic object with attributes
    return RainfallRecord(
        observed_at=_ensure_utc(getattr(obj, "observed_at")),
        numeric_value=getattr(obj, "numeric_value", None),
        quality_flag=getattr(obj, "quality_flag", "VALID"),
        source=getattr(obj, "source", "sensor_telemetry"),
        device_sequence=getattr(obj, "device_sequence", None),
        sensor_id=getattr(obj, "sensor_id", None),
    )


def deduplicate_and_sort_records(records: Iterable[Any]) -> list[RainfallRecord]:
    """Deduplicate records by (device_sequence, observed_at) or observed_at and sort chronologically.

    Commutative and deterministic: input ordering does not affect output.
    """
    normalized: list[RainfallRecord] = [_extract_record(r) for r in records]

    # Deduplicate: if duplicate (device_sequence, observed_at) or (observed_at, sensor_id),
    # keep the first valid record encountered.
    seen: set[tuple[Any, ...]] = set()
    unique_records: list[RainfallRecord] = []

    for rec in normalized:
        # Key on sensor_id, device_sequence (if present), and observed_at instant
        instant_epoch = rec.observed_at.timestamp()
        key = (rec.sensor_id, rec.device_sequence, instant_epoch) if rec.device_sequence is not None else (rec.sensor_id, instant_epoch)
        if key in seen:
            continue
        seen.add(key)
        unique_records.append(rec)

    # Sort ascending by timestamp
    unique_records.sort(key=lambda r: r.observed_at)
    return unique_records


def calculate_window_accumulation(
    records: Iterable[Any],
    evaluation_time: datetime,
    window_duration: timedelta,
    window_name: str,
    source_id: str,
    stale_threshold_seconds: float = DEFAULT_STALE_THRESHOLD_SECONDS,
    expected_interval_minutes: Optional[float] = None,
    allow_partial_sum: bool = False,
) -> RainfallFeatureResult:
    """Calculate accumulation for a single window over records.

    Interval: (evaluation_time - window_duration, evaluation_time]
    """
    eval_utc = _ensure_utc(evaluation_time)
    sorted_records = deduplicate_and_sort_records(records)
    window_start = eval_utc - window_duration
    window_duration_seconds = window_duration.total_seconds()

    # Filter observations in the half-open window: (window_start, eval_utc]
    window_records = [
        r for r in sorted_records
        if window_start < r.observed_at <= eval_utc
    ]

    total_count = len(window_records)

    # If completely empty (no observations in this window)
    if total_count == 0:
        # Find latest overall observation up to eval_utc (if any) to assess freshness
        prior_records = [r for r in sorted_records if r.observed_at <= eval_utc]
        latest_ts = prior_records[-1].observed_at if prior_records else None
        source_age = (eval_utc - latest_ts).total_seconds() if latest_ts else None
        is_stale = (source_age is not None and source_age > stale_threshold_seconds)

        return RainfallFeatureResult(
            window_name=window_name,
            window_duration_seconds=window_duration_seconds,
            value=None,  # EMPTY IS NULL, NEVER 0.0 mm
            unit="mm",
            source_id=source_id,
            evaluation_timestamp=eval_utc,
            latest_observation_timestamp=latest_ts,
            source_age_seconds=source_age,
            coverage_ratio=0.0,
            quality_status=QualityStatus.STALE.value if is_stale else QualityStatus.EMPTY.value,
            is_stale=is_stale,
            valid_sample_count=0,
            missing_sample_count=0,
            total_sample_count=0,
            partial_value=None,
        )

    # Latest observation within this window
    latest_ts = window_records[-1].observed_at
    source_age = (eval_utc - latest_ts).total_seconds()
    is_stale = source_age > stale_threshold_seconds

    # Partition into valid vs missing samples
    valid_samples: list[float] = []
    missing_count = 0

    for r in window_records:
        if r.numeric_value is not None and r.quality_flag not in ("MISSING", "ERROR"):
            valid_samples.append(float(r.numeric_value))
        else:
            missing_count += 1

    valid_count = len(valid_samples)

    # Expected count calculation when expected sampling rate is provided
    if expected_interval_minutes and expected_interval_minutes > 0:
        expected_samples = max(1, int(round(window_duration_seconds / (expected_interval_minutes * 60.0))))
        coverage_ratio = min(1.0, valid_count / expected_samples)
    else:
        coverage_ratio = valid_count / total_count if total_count > 0 else 0.0

    # Determine Quality Status and Value
    if valid_count == 0:
        # All reported readings in window are explicitly MISSING / ERROR
        quality_status = QualityStatus.MISSING.value
        final_value = None
        partial_value = None
    elif missing_count > 0 or (expected_interval_minutes and coverage_ratio < 0.95):
        # Mixed: Some valid readings, but some missing or sample density incomplete
        quality_status = QualityStatus.PARTIAL.value
        partial_sum = round(sum(valid_samples), 4)
        partial_value = partial_sum
        # Safety rule: if allow_partial_sum is False, final value remains None to prevent
        # downstream models from assuming partial precipitation represents the true total.
        final_value = partial_sum if allow_partial_sum else None
    else:
        # Complete window: all samples present and valid
        quality_status = QualityStatus.COMPLETE.value
        final_value = round(sum(valid_samples), 4)
        partial_value = final_value

    if is_stale and quality_status == QualityStatus.COMPLETE.value:
        # If complete but old
        quality_status = QualityStatus.STALE.value

    return RainfallFeatureResult(
        window_name=window_name,
        window_duration_seconds=window_duration_seconds,
        value=final_value,
        unit="mm",
        source_id=source_id,
        evaluation_timestamp=eval_utc,
        latest_observation_timestamp=latest_ts,
        source_age_seconds=source_age,
        coverage_ratio=round(coverage_ratio, 4),
        quality_status=quality_status,
        is_stale=is_stale,
        valid_sample_count=valid_count,
        missing_sample_count=missing_count,
        total_sample_count=total_count,
        partial_value=partial_value,
    )


def calculate_rainfall_features(
    records: Iterable[Any],
    evaluation_time: datetime,
    source_id: str,
    windows: Optional[dict[str, timedelta]] = None,
    stale_threshold_seconds: float = DEFAULT_STALE_THRESHOLD_SECONDS,
    expected_interval_minutes: Optional[float] = None,
    allow_partial_sum: bool = False,
) -> dict[str, RainfallFeatureResult]:
    """Calculate all 7 standard rainfall features from an iterable of observation records.

    Deterministic, idempotent, timezone-aware.
    """
    eval_utc = _ensure_utc(evaluation_time)
    active_windows = windows or STANDARD_WINDOWS
    sorted_records = deduplicate_and_sort_records(records)

    results: dict[str, RainfallFeatureResult] = {}
    for window_name, duration in active_windows.items():
        results[window_name] = calculate_window_accumulation(
            records=sorted_records,
            evaluation_time=eval_utc,
            window_duration=duration,
            window_name=window_name,
            source_id=source_id,
            stale_threshold_seconds=stale_threshold_seconds,
            expected_interval_minutes=expected_interval_minutes,
            allow_partial_sum=allow_partial_sum,
        )

    return results


def calculate_rainfall_features_for_sensor(
    session: Session,
    sensor_id: int | str,
    evaluation_time: Optional[datetime] = None,
    metric_type: str = "rainfall_mm",
    windows: Optional[dict[str, timedelta]] = None,
    stale_threshold_seconds: float = DEFAULT_STALE_THRESHOLD_SECONDS,
    expected_interval_minutes: Optional[float] = None,
    allow_partial_sum: bool = False,
) -> dict[str, RainfallFeatureResult]:
    """Query live PostgreSQL/Timescale observations and calculate rainfall features.

    Filters efficiently via database index up to max window duration (default 7 days).
    """
    eval_utc = _ensure_utc(evaluation_time) if evaluation_time is not None else datetime.now(timezone.utc)
    active_windows = windows or STANDARD_WINDOWS
    max_duration = max(active_windows.values())
    query_start = eval_utc - max_duration

    # Resolve sensor record to get code and primary key id
    if isinstance(sensor_id, int):
        sensor = session.scalars(select(Sensor).where(Sensor.id == sensor_id)).first()
    else:
        sensor = session.scalars(select(Sensor).where(Sensor.sensor_code == str(sensor_id))).first()

    if sensor is None:
        raise ValueError(f"Sensor '{sensor_id}' not found in registry.")

    source_id = sensor.sensor_code

    # Query observations using hypertable indexes on (sensor_id, observed_at)
    stmt = (
        select(Observation)
        .where(
            Observation.sensor_id == sensor.id,
            Observation.metric_type == metric_type,
            Observation.observed_at > query_start,
            Observation.observed_at <= eval_utc,
        )
        .order_by(Observation.observed_at.asc())
    )
    obs_list = list(session.scalars(stmt).all())

    return calculate_rainfall_features(
        records=obs_list,
        evaluation_time=eval_utc,
        source_id=source_id,
        windows=active_windows,
        stale_threshold_seconds=stale_threshold_seconds,
        expected_interval_minutes=expected_interval_minutes,
        allow_partial_sum=allow_partial_sum,
    )
