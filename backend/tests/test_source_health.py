from datetime import datetime, timedelta, timezone

import pytest

from backend.app.features.source_health import (
    SourceHealthState,
    SourceObservationRecord,
    evaluate_source_health,
)


NOW = datetime(
    2026,
    9,
    12,
    12,
    0,
    tzinfo=timezone.utc,
)


def obs(
    *,
    minutes_ago=10,
    ingestion_delay_minutes=1,
    quality="VALID",
):
    observed = NOW - timedelta(
        minutes=minutes_ago
    )

    return SourceObservationRecord(
        observed_at=observed,
        ingested_at=observed + timedelta(
            minutes=ingestion_delay_minutes
        ),
        quality_flag=quality,
    )


def test_fresh_valid_source_is_healthy():
    result = evaluate_source_health(
        "DEV_SENSOR_RAIN_001",
        "ACTIVE",
        [obs()],
        NOW,
    )

    assert result.health_state == "HEALTHY"
    assert result.observation_age_seconds == 600.0
    assert result.problem_ratio == 0.0
    assert "SOURCE_OK" in result.reason_codes


def test_missing_latest_reading_is_degraded():
    result = evaluate_source_health(
        "DEV_SENSOR_SOIL_001",
        "ACTIVE",
        [
            obs(
                quality="VALID",
                minutes_ago=20,
            ),
            obs(
                quality="MISSING",
                minutes_ago=10,
            ),
        ],
        NOW,
    )

    assert result.health_state == "DEGRADED"
    assert result.problem_observations == 1
    assert "LATEST_QUALITY_PROBLEM" in result.reason_codes


def test_high_problem_ratio_is_degraded():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [
            obs(minutes_ago=20),
            obs(
                minutes_ago=15,
                quality="ERROR",
            ),
            obs(
                minutes_ago=10,
                quality="SUSPECT",
            ),
        ],
        NOW,
    )

    assert result.health_state == "DEGRADED"
    assert result.problem_ratio > 0.25
    assert "HIGH_PROBLEM_RATIO" in result.reason_codes


def test_high_ingestion_lag_is_degraded():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [
            obs(
                ingestion_delay_minutes=30
            )
        ],
        NOW,
    )

    assert result.health_state == "DEGRADED"
    assert "HIGH_INGESTION_LAG" in result.reason_codes


def test_old_source_is_stale():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [
            obs(minutes_ago=4 * 60)
        ],
        NOW,
    )

    assert result.health_state == "STALE"
    assert "OBSERVATION_STALE" in result.reason_codes


def test_very_old_source_is_offline():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [
            obs(minutes_ago=13 * 60)
        ],
        NOW,
    )

    assert result.health_state == "OFFLINE"
    assert "OBSERVATION_TOO_OLD" in result.reason_codes


def test_explicit_offline_sensor_is_offline():
    result = evaluate_source_health(
        "SOURCE_001",
        "OFFLINE",
        [obs()],
        NOW,
    )

    assert result.health_state == "OFFLINE"
    assert "SENSOR_STATUS_OFFLINE" in result.reason_codes


def test_no_observations_is_unknown():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [],
        NOW,
    )

    assert result.health_state == "UNKNOWN"
    assert result.latest_observed_at is None
    assert "NO_OBSERVATIONS" in result.reason_codes


def test_future_observation_is_not_used():
    future = SourceObservationRecord(
        observed_at=NOW + timedelta(minutes=5),
        ingested_at=NOW + timedelta(minutes=6),
        quality_flag="VALID",
    )

    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [future],
        NOW,
    )

    assert result.health_state == "UNKNOWN"


def test_naive_evaluation_time_is_rejected():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        evaluate_source_health(
            "SOURCE_001",
            "ACTIVE",
            [obs()],
            datetime(2026, 9, 12, 12, 0),
        )


def test_offline_threshold_must_exceed_stale_threshold():
    with pytest.raises(ValueError):
        evaluate_source_health(
            "SOURCE_001",
            "ACTIVE",
            [obs()],
            NOW,
            stale_after_seconds=3600,
            offline_after_seconds=1800,
        )


def test_health_result_exposes_required_t11_fields():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [obs()],
        NOW,
    )

    assert result.availability is True
    assert result.last_timestamp is not None
    assert result.freshness_seconds == 600.0
    assert result.reliability_score == 1.0
    assert result.coverage_ratio == 1.0
    assert result.consistency_score == 1.0


def test_missing_reading_reduces_coverage_and_reliability():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [
            obs(minutes_ago=20),
            obs(
                minutes_ago=10,
                quality="MISSING",
            ),
        ],
        NOW,
    )

    assert result.reliability_score == 0.5
    assert result.coverage_ratio == 0.5


def test_slow_ingestion_reduces_consistency():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [
            obs(
                minutes_ago=20,
                ingestion_delay_minutes=1,
            ),
            obs(
                minutes_ago=10,
                ingestion_delay_minutes=30,
            ),
        ],
        NOW,
    )

    assert result.consistency_score == 0.5


def test_no_observations_reports_zero_coverage():
    result = evaluate_source_health(
        "SOURCE_001",
        "ACTIVE",
        [],
        NOW,
    )

    assert result.availability is False
    assert result.last_timestamp is None
    assert result.freshness_seconds is None
    assert result.reliability_score is None
    assert result.coverage_ratio == 0.0
    assert result.consistency_score is None
