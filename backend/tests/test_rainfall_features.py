"""Test suite for T04: Rainfall History & Accumulation Feature Foundation.

Covers:
1. All 7 accumulation windows (30m, 1h, 3h, 6h, 24h, 3d, 7d) on deterministic fixture
2. Boundary behavior: (eval_time - window, eval_time]
3. Timezone awareness and UTC normalization
4. Out-of-order observation handling and deduplication
5. Genuine 0.0 mm rainfall preservation (COMPLETE status, 0.0 mm value)
6. Missing data != zero principle (NULL/MISSING never coerced to 0.0)
7. Completely empty window behavior (EMPTY status, NULL value)
8. Partial coverage representation (PARTIAL status, coverage_ratio < 1.0)
9. Source provenance retention and latest observation timestamp
10. Source age / freshness calculation and stale detection
11. Live database integration against PostgreSQL/Timescale hypertable
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.db.session import get_sync_engine
from backend.app.features.rainfall import (
    DEFAULT_STALE_THRESHOLD_SECONDS,
    QualityStatus,
    RainfallFeatureResult,
    RainfallRecord,
    calculate_rainfall_features,
    calculate_rainfall_features_for_sensor,
    calculate_window_accumulation,
    deduplicate_and_sort_records,
)
from backend.app.models.sensing import Observation, Sensor


# Fixed evaluation anchor for deterministic tests
EVAL_TIME = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


def _check_live_db_available() -> bool:
    """Probe live database container reachability."""
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# =============================================================================
# DETERMINISTIC KNOWN-CASE FIXTURES
# =============================================================================

@pytest.fixture
def deterministic_known_fixture() -> list[RainfallRecord]:
    """Synthetic known fixture with manually verifiable accumulations.

    Anchor: EVAL_TIME = 2026-09-12 12:00:00 UTC
    Readings:
      - 11:45 UTC (t - 15m)  :  5.0 mm -> inside 30m, 1h, 3h, 6h, 24h, 3d, 7d
      - 11:15 UTC (t - 45m)  : 10.0 mm -> inside 1h, 3h, 6h, 24h, 3d, 7d
      - 10:00 UTC (t - 2h)   : 15.0 mm -> inside 3h, 6h, 24h, 3d, 7d
      - 07:00 UTC (t - 5h)   : 20.0 mm -> inside 6h, 24h, 3d, 7d
      - 2026-09-11 18:00 (t - 18h) : 25.0 mm -> inside 24h, 3d, 7d
      - 2026-09-10 12:00 (t - 48h) : 30.0 mm -> inside 3d, 7d
      - 2026-09-07 12:00 (t - 5d)  : 40.0 mm -> inside 7d
      - 2026-09-04 12:00 (t - 8d)  : 50.0 mm -> outside all 7 windows
    """
    return [
        RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=15), numeric_value=5.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=45), numeric_value=10.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(hours=2), numeric_value=15.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(hours=5), numeric_value=20.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(hours=18), numeric_value=25.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(days=2), numeric_value=30.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(days=5), numeric_value=40.0, source="DEV_GAUGE_001"),
        RainfallRecord(observed_at=EVAL_TIME - timedelta(days=8), numeric_value=50.0, source="DEV_GAUGE_001"),
    ]


# =============================================================================
# TESTS: 7 WINDOWS ON KNOWN FIXTURE
# =============================================================================

class TestSevenRainfallWindows:
    """Verify exact accumulations across all 7 mandated windows."""

    def test_rain_30m_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(minutes=30),
            window_name="rain_30m",
            source_id="DEV_GAUGE_001",
        )
        assert res.value == 5.0
        assert res.unit == "mm"
        assert res.quality_status == QualityStatus.COMPLETE.value
        assert res.valid_sample_count == 1

    def test_rain_1h_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=1),
            window_name="rain_1h",
            source_id="DEV_GAUGE_001",
        )
        # 5.0 (at 15m) + 10.0 (at 45m) = 15.0
        assert res.value == 15.0
        assert res.quality_status == QualityStatus.COMPLETE.value
        assert res.valid_sample_count == 2

    def test_rain_3h_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=3),
            window_name="rain_3h",
            source_id="DEV_GAUGE_001",
        )
        # 15.0 + 15.0 (at 2h) = 30.0
        assert res.value == 30.0
        assert res.valid_sample_count == 3

    def test_rain_6h_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=6),
            window_name="rain_6h",
            source_id="DEV_GAUGE_001",
        )
        # 30.0 + 20.0 (at 5h) = 50.0
        assert res.value == 50.0
        assert res.valid_sample_count == 4

    def test_rain_24h_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=24),
            window_name="rain_24h",
            source_id="DEV_GAUGE_001",
        )
        # 50.0 + 25.0 (at 18h) = 75.0
        assert res.value == 75.0
        assert res.valid_sample_count == 5

    def test_rain_3d_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(days=3),
            window_name="rain_3d",
            source_id="DEV_GAUGE_001",
        )
        # 75.0 + 30.0 (at 2d) = 105.0
        assert res.value == 105.0
        assert res.valid_sample_count == 6

    def test_rain_7d_accumulation(self, deterministic_known_fixture):
        res = calculate_window_accumulation(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(days=7),
            window_name="rain_7d",
            source_id="DEV_GAUGE_001",
        )
        # 105.0 + 40.0 (at 5d) = 145.0 (8d observation of 50.0 mm is excluded)
        assert res.value == 145.0
        assert res.valid_sample_count == 7

    def test_all_seven_windows_combined(self, deterministic_known_fixture):
        results = calculate_rainfall_features(
            deterministic_known_fixture,
            evaluation_time=EVAL_TIME,
            source_id="DEV_GAUGE_001",
        )
        assert len(results) == 7
        assert results["rain_30m"].value == 5.0
        assert results["rain_1h"].value == 15.0
        assert results["rain_3h"].value == 30.0
        assert results["rain_6h"].value == 50.0
        assert results["rain_24h"].value == 75.0
        assert results["rain_3d"].value == 105.0
        assert results["rain_7d"].value == 145.0


# =============================================================================
# TESTS: BOUNDARY BEHAVIOR
# =============================================================================

class TestIntervalBoundarySemantics:
    """Prove exact interval boundary behavior: (evaluation_time - window, evaluation_time]."""

    def test_exact_right_boundary_included(self):
        """Reading precisely AT evaluation_time is included."""
        records = [
            RainfallRecord(observed_at=EVAL_TIME, numeric_value=12.0),
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=1),
            window_name="rain_1h",
            source_id="DEV_GAUGE",
        )
        assert res.value == 12.0
        assert res.valid_sample_count == 1

    def test_exact_left_boundary_excluded(self):
        """Reading precisely AT evaluation_time - window_duration is EXCLUDED (left-open)."""
        window_start = EVAL_TIME - timedelta(hours=1)
        records = [
            RainfallRecord(observed_at=window_start, numeric_value=10.0),  # Exactly at boundary
            RainfallRecord(observed_at=window_start + timedelta(seconds=1), numeric_value=20.0),  # Just inside
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=1),
            window_name="rain_1h",
            source_id="DEV_GAUGE",
        )
        # Only 20.0 is inside; 10.0 is on the left boundary and excluded
        assert res.value == 20.0
        assert res.valid_sample_count == 1

    def test_future_observation_excluded(self):
        """Reading after evaluation_time is excluded."""
        records = [
            RainfallRecord(observed_at=EVAL_TIME + timedelta(seconds=1), numeric_value=99.0),
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=1),
            window_name="rain_1h",
            source_id="DEV_GAUGE",
        )
        assert res.value is None
        assert res.quality_status == QualityStatus.EMPTY.value


# =============================================================================
# TESTS: ORDERING AND DEDUPLICATION
# =============================================================================

class TestOrderingAndDeduplication:
    """Prove calculation is deterministic and handles unordered/duplicate inputs."""

    def test_out_of_order_data_produces_identical_result(self, deterministic_known_fixture):
        """Permuting input order produces the exact same accumulation."""
        shuffled = list(deterministic_known_fixture)
        random.seed(42)
        random.shuffle(shuffled)

        res_ordered = calculate_rainfall_features(deterministic_known_fixture, EVAL_TIME, "DEV_GAUGE")
        res_shuffled = calculate_rainfall_features(shuffled, EVAL_TIME, "DEV_GAUGE")

        for window in res_ordered:
            assert res_ordered[window].value == res_shuffled[window].value
            assert res_ordered[window].latest_observation_timestamp == res_shuffled[window].latest_observation_timestamp

    def test_duplicate_device_sequence_deduplicated(self):
        """QoS-1 retransmissions with identical device_sequence are deduplicated in memory."""
        t = EVAL_TIME - timedelta(minutes=10)
        records = [
            RainfallRecord(observed_at=t, numeric_value=7.5, device_sequence=5001, sensor_id=1),
            RainfallRecord(observed_at=t, numeric_value=7.5, device_sequence=5001, sensor_id=1),  # Duplicate
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(minutes=30),
            window_name="rain_30m",
            source_id="DEV_GAUGE",
        )
        assert res.value == 7.5  # Not 15.0
        assert res.valid_sample_count == 1


# =============================================================================
# TESTS: CRITICAL SAFETY RULE — MISSING DATA != ZERO
# =============================================================================

class TestMissingDataSafetyPrinciples:
    """Verify strict adherence to MISSING DATA != ZERO principle."""

    def test_genuine_zero_rainfall_is_numeric_zero(self):
        """A complete window where rain gauge recorded 0.0 mm results in 0.0 mm."""
        records = [
            RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=10), numeric_value=0.0),
            RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=20), numeric_value=0.0),
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(minutes=30),
            window_name="rain_30m",
            source_id="DEV_GAUGE",
        )
        assert res.value == 0.0
        assert res.quality_status == QualityStatus.COMPLETE.value
        assert res.coverage_ratio == 1.0

    def test_completely_empty_window_is_null_not_zero(self):
        """An empty window (no telemetry) produces value=None, NOT 0.0 mm."""
        res = calculate_window_accumulation(
            records=[],
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=1),
            window_name="rain_1h",
            source_id="DEV_GAUGE",
        )
        assert res.value is None, "Empty window must be NULL"
        assert res.value != 0, "Empty window must NOT become 0.0"
        assert res.quality_status == QualityStatus.EMPTY.value
        assert res.coverage_ratio == 0.0

    def test_explicit_missing_observation_is_null_not_zero(self):
        """Explicit missing observation (sensor failure) produces value=None, NOT 0.0 mm."""
        records = [
            RainfallRecord(
                observed_at=EVAL_TIME - timedelta(minutes=10),
                numeric_value=None,
                quality_flag="MISSING",
            ),
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(minutes=30),
            window_name="rain_30m",
            source_id="DEV_GAUGE",
        )
        assert res.value is None, "Missing observation must be NULL"
        assert res.value != 0, "Missing observation must NOT be converted to 0.0"
        assert res.quality_status == QualityStatus.MISSING.value
        assert res.missing_sample_count == 1
        assert res.valid_sample_count == 0

    def test_partial_window_explicitly_represented(self):
        """Mixed valid and missing readings produce PARTIAL status and coverage < 1.0."""
        records = [
            RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=10), numeric_value=4.0),
            RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=20), numeric_value=None, quality_flag="MISSING"),
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(minutes=30),
            window_name="rain_30m",
            source_id="DEV_GAUGE",
            allow_partial_sum=False,  # Strict default
        )
        assert res.quality_status == QualityStatus.PARTIAL.value
        assert res.value is None  # Strict safety: partial data not passed as complete total
        assert res.partial_value == 4.0  # Retained for inspection
        assert res.coverage_ratio == 0.5
        assert res.valid_sample_count == 1
        assert res.missing_sample_count == 1

    def test_partial_window_with_allow_partial_sum(self):
        """When allow_partial_sum=True, partial sum is returned but status remains PARTIAL."""
        records = [
            RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=10), numeric_value=4.0),
            RainfallRecord(observed_at=EVAL_TIME - timedelta(minutes=20), numeric_value=None, quality_flag="MISSING"),
        ]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(minutes=30),
            window_name="rain_30m",
            source_id="DEV_GAUGE",
            allow_partial_sum=True,
        )
        assert res.quality_status == QualityStatus.PARTIAL.value
        assert res.value == 4.0
        assert res.coverage_ratio == 0.5


# =============================================================================
# TESTS: SOURCE PROVENANCE AND FRESHNESS
# =============================================================================

class TestSourceProvenanceAndFreshness:
    """Verify source metadata retention and staleness calculation."""

    def test_metadata_retention(self):
        t_obs = EVAL_TIME - timedelta(minutes=10)
        records = [RainfallRecord(observed_at=t_obs, numeric_value=3.2, source="TEST_SOURCE_XYZ")]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=1),
            window_name="rain_1h",
            source_id="TEST_SOURCE_XYZ",
        )
        assert res.source_id == "TEST_SOURCE_XYZ"
        assert res.evaluation_timestamp == EVAL_TIME
        assert res.latest_observation_timestamp == t_obs
        assert res.source_age_seconds == 600.0  # 10 minutes = 600s
        assert not res.is_stale

    def test_stale_detection(self):
        """Observations older than staleness threshold trigger is_stale=True."""
        t_old = EVAL_TIME - timedelta(hours=4)  # 4 hours old (> 3h threshold)
        records = [RainfallRecord(observed_at=t_old, numeric_value=5.0)]
        res = calculate_window_accumulation(
            records,
            evaluation_time=EVAL_TIME,
            window_duration=timedelta(hours=6),
            window_name="rain_6h",
            source_id="DEV_GAUGE",
            stale_threshold_seconds=DEFAULT_STALE_THRESHOLD_SECONDS,  # 3 hours
        )
        assert res.is_stale is True
        assert res.quality_status == QualityStatus.STALE.value
        assert res.source_age_seconds == 4 * 3600.0

    def test_naive_timestamp_rejected(self):
        """Naive datetime without tzinfo raises ValueError."""
        naive_time = datetime(2026, 9, 12, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            calculate_window_accumulation(
                records=[],
                evaluation_time=naive_time,
                window_duration=timedelta(hours=1),
                window_name="rain_1h",
                source_id="DEV_GAUGE",
            )


# =============================================================================
# TESTS: LIVE DATABASE INTEGRATION (PostgreSQL / TimescaleDB)
# =============================================================================

@pytest.mark.skipif(
    not _check_live_db_available(),
    reason="Live PostgreSQL/TimescaleDB container not reachable.",
)
class TestLiveDatabaseIntegration:
    """Verify feature calculation over live PostgreSQL/TimescaleDB observations table."""

    @pytest.fixture
    def db_session(self):
        engine = get_sync_engine()
        with Session(engine) as session:
            yield session

    def test_sensor_rainfall_features_query_integration(self, db_session):
        """Insert deterministic observations into live DB and query via feature service."""
        sensor_code = f"TEST_RAIN_SENS_{int(datetime.now().timestamp())}"
        now_utc = datetime.now(timezone.utc).replace(microsecond=0)

        # 1. Create sensor
        sensor = Sensor(
            sensor_code=sensor_code,
            sensor_type="rain_gauge",
            location="SRID=4326;POINT(79.25 30.50)",
            status="ACTIVE",
        )
        db_session.add(sensor)
        db_session.commit()

        # 2. Insert test rainfall observations
        # - 15m ago: 4.5 mm
        # - 45m ago: 5.5 mm
        # - 2h ago: 10.0 mm
        obs1 = Observation(
            observed_at=now_utc - timedelta(minutes=15),
            sensor_id=sensor.id,
            metric_type="rainfall_mm",
            numeric_value=4.5,
            unit="mm",
            quality_flag="VALID",
            device_sequence=1001,
        )
        obs2 = Observation(
            observed_at=now_utc - timedelta(minutes=45),
            sensor_id=sensor.id,
            metric_type="rainfall_mm",
            numeric_value=5.5,
            unit="mm",
            quality_flag="VALID",
            device_sequence=1002,
        )
        obs3 = Observation(
            observed_at=now_utc - timedelta(hours=2),
            sensor_id=sensor.id,
            metric_type="rainfall_mm",
            numeric_value=10.0,
            unit="mm",
            quality_flag="VALID",
            device_sequence=1003,
        )
        db_session.add_all([obs1, obs2, obs3])
        db_session.commit()

        # 3. Calculate features using live database service
        features = calculate_rainfall_features_for_sensor(
            session=db_session,
            sensor_id=sensor.id,
            evaluation_time=now_utc,
            metric_type="rainfall_mm",
        )

        assert features["rain_30m"].value == 4.5
        assert features["rain_30m"].valid_sample_count == 1
        assert features["rain_1h"].value == 10.0  # 4.5 + 5.5
        assert features["rain_1h"].valid_sample_count == 2
        assert features["rain_3h"].value == 20.0  # 4.5 + 5.5 + 10.0
        assert features["rain_3h"].valid_sample_count == 3
        assert features["rain_6h"].value == 20.0
        assert features["rain_24h"].value == 20.0
        assert features["rain_3d"].value == 20.0
        assert features["rain_7d"].value == 20.0

        # Provenance verification
        assert features["rain_30m"].source_id == sensor_code
        assert features["rain_30m"].latest_observation_timestamp == now_utc - timedelta(minutes=15)
        assert features["rain_30m"].source_age_seconds == 900.0
