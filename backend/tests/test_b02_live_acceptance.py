"""B02 Acceptance Test Suite against Live PostgreSQL + PostGIS + TimescaleDB.

COVERS ALL 12 ACCEPTANCE CRITERIA:
1. Extension verification: PostGIS installed/enabled
2. Extension verification: TimescaleDB installed/enabled
3. Hypertable verification: observations table is a Timescale hypertable
4. Sensor CRUD: Create, Read, Update
5. GIS CRUD: Create, Read, Update PostGIS entity
6. Prediction CRUD: Create, Read, Update
7. Warning CRUD: Create, Read, Update
8. Incident CRUD: Create, Read, Update
9. Spatial query: Execute real PostGIS ST_* query (e.g. ST_Contains / ST_DWithin)
10. Time-series preservation: Timezone-aware timestamp round-trip (asserts same instant)
11. Missing data != zero: Prove missing observation stored as NULL and never coerced to 0
12. Duplicate protection: Prove QoS-1 device_sequence integrity constraint rejects duplicates

BLOCKING BEHAVIOR (MANDATED BY STEP B & STEP K):
If Docker or the live database service is unavailable, these tests are clearly marked
as BLOCKED rather than faked with SQLite or mock engines.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.session import get_sync_engine
from backend.app.models.events import Incident, Prediction, Warning
from backend.app.models.geography import Catchment, Region, Village
from backend.app.models.operations import Road, Shelter
from backend.app.models.sensing import Observation, Sensor
from backend.app.models.users import User


def _check_live_db_available() -> bool:
    """Probe whether the live database service is reachable."""
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# Module-level skip if live database is not reachable
pytestmark = pytest.mark.skipif(
    not _check_live_db_available(),
    reason=(
        "BLOCKED: Live PostgreSQL/PostGIS/TimescaleDB database is not reachable. "
        "Docker is not installed on this host. Run `docker compose up -d` to start the "
        "reproducible database container before running live acceptance tests."
    ),
)


@pytest.fixture
def db_session():
    """Yield a database session connected to the live database."""
    engine = get_sync_engine()
    with Session(engine) as session:
        yield session


class TestExtensions:
    """Verify required database extensions are enabled."""

    def test_postgis_extension_enabled(self, db_session):
        result = db_session.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname = 'postgis';")
        ).fetchone()
        assert result is not None, "PostGIS extension is not installed/enabled in PostgreSQL"

    def test_timescaledb_extension_enabled(self, db_session):
        result = db_session.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';")
        ).fetchone()
        assert result is not None, "TimescaleDB extension is not installed/enabled in PostgreSQL"

    def test_timescale_hypertable_configured(self, db_session):
        result = db_session.execute(
            text("SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_name = 'observations';")
        ).fetchone()
        assert result is not None, "observations table was not configured as a TimescaleDB hypertable"


class TestCrudAcceptance:
    """Verify Create / Read / Update across core disaster domain entities."""

    def test_sensor_crud(self, db_session):
        code = f"TEST_SENSOR_{int(datetime.now().timestamp())}"
        # Create
        sensor = Sensor(
            sensor_code=code,
            sensor_type="rain_gauge",
            location="SRID=4326;POINT(79.25 30.50)",
            status="ACTIVE",
        )
        db_session.add(sensor)
        db_session.commit()

        # Read
        fetched = db_session.scalars(select(Sensor).where(Sensor.sensor_code == code)).first()
        assert fetched is not None
        assert fetched.sensor_type == "rain_gauge"

        # Update
        fetched.status = "MAINTENANCE"
        db_session.commit()
        db_session.refresh(fetched)
        assert fetched.status == "MAINTENANCE"

    def test_gis_feature_crud(self, db_session):
        code = f"TEST_SHELTER_{int(datetime.now().timestamp())}"
        # Fetch or create dev village
        village = db_session.scalars(select(Village)).first()
        assert village is not None, "Requires seeded dev village"

        # Create Shelter (GIS feature)
        shelter = Shelter(
            shelter_code=code,
            name="Test Evacuation Shelter",
            capacity=200,
            status="AVAILABLE",
            village_id=village.id,
            location="SRID=4326;POINT(79.251 30.501)",
        )
        db_session.add(shelter)
        db_session.commit()

        # Read
        fetched = db_session.scalars(select(Shelter).where(Shelter.shelter_code == code)).first()
        assert fetched is not None
        assert fetched.capacity == 200

        # Update
        fetched.capacity = 250
        db_session.commit()
        db_session.refresh(fetched)
        assert fetched.capacity == 250

    def test_prediction_crud(self, db_session):
        code = f"TEST_PRED_{int(datetime.now().timestamp())}"
        now = datetime.now(timezone.utc)
        pred = Prediction(
            prediction_code=code,
            model_name="TestLandslideModel",
            model_version="1.0",
            target_metric="risk_score",
            predicted_value=0.65,
            risk_level="MEDIUM",
            valid_from=now,
            valid_to=now + timedelta(hours=4),
        )
        db_session.add(pred)
        db_session.commit()

        # Read
        fetched = db_session.scalars(select(Prediction).where(Prediction.prediction_code == code)).first()
        assert fetched is not None
        assert fetched.predicted_value == 0.65

        # Update
        fetched.risk_level = "HIGH"
        db_session.commit()
        db_session.refresh(fetched)
        assert fetched.risk_level == "HIGH"

    def test_warning_crud(self, db_session):
        code = f"TEST_WARN_{int(datetime.now().timestamp())}"
        warn = Warning(
            warning_code=code,
            severity="WATCH",
            status="ACTIVE",
            title="Flash Flood Watch",
            description="High runoff anticipated in dev catchment.",
        )
        db_session.add(warn)
        db_session.commit()

        # Read
        fetched = db_session.scalars(select(Warning).where(Warning.warning_code == code)).first()
        assert fetched is not None
        assert fetched.severity == "WATCH"

        # Update
        fetched.status = "RESOLVED"
        db_session.commit()
        db_session.refresh(fetched)
        assert fetched.status == "RESOLVED"

    def test_incident_crud(self, db_session):
        code = f"TEST_INC_{int(datetime.now().timestamp())}"
        inc = Incident(
            incident_code=code,
            incident_type="LANDSLIDE",
            status="REPORTED",
            severity="HIGH",
            location="SRID=4326;POINT(79.245 30.495)",
            description="Debris blocking secondary access path.",
        )
        db_session.add(inc)
        db_session.commit()

        # Read
        fetched = db_session.scalars(select(Incident).where(Incident.incident_code == code)).first()
        assert fetched is not None
        assert fetched.incident_type == "LANDSLIDE"

        # Update
        fetched.status = "VERIFIED"
        db_session.commit()
        db_session.refresh(fetched)
        assert fetched.status == "VERIFIED"


class TestSpatialQueries:
    """Verify real PostGIS spatial operations."""

    def test_st_contains_catchment_contains_village(self, db_session):
        """Execute real PostGIS ST_Contains query asserting DEV village is inside DEV catchment."""
        query = text("""
            SELECT c.code AS catchment_code, v.code AS village_code
            FROM catchments c
            JOIN villages v ON ST_Contains(c.geometry, v.location)
            WHERE c.code = 'DEV_CATCHMENT_001' AND v.code = 'DEV_VILLAGE_001';
        """)
        result = db_session.execute(query).fetchone()
        assert result is not None, "PostGIS ST_Contains failed: DEV_VILLAGE_001 should be inside DEV_CATCHMENT_001"
        assert result.catchment_code == "DEV_CATCHMENT_001"
        assert result.village_code == "DEV_VILLAGE_001"


class TestTimeSeriesAndDataPrinciples:
    """Verify disaster data preservation principles."""

    def test_timezone_aware_timestamp_round_trip(self, db_session):
        """Rule 2: Timestamp round-trip must preserve the exact same UTC instant."""
        sensor = db_session.scalars(select(Sensor)).first()
        assert sensor is not None

        specific_utc_time = datetime.now(timezone.utc).replace(microsecond=0)
        obs = Observation(
            observed_at=specific_utc_time,
            sensor_id=sensor.id,
            metric_type="test_roundtrip_metric",
            numeric_value=42.0,
            unit="unit",
            quality_flag="VALID",
            source="test_telemetry",
        )
        db_session.add(obs)
        db_session.commit()

        # Read back
        fetched = db_session.scalars(
            select(Observation).where(
                Observation.observed_at == specific_utc_time,
                Observation.sensor_id == sensor.id,
                Observation.metric_type == "test_roundtrip_metric",
            )
        ).first()

        assert fetched is not None
        # Assert exact instant matches
        assert fetched.observed_at.timestamp() == specific_utc_time.timestamp()
        assert fetched.observed_at == specific_utc_time

    def test_missing_data_is_null_not_zero(self, db_session):
        """Rule 1: Missing measurement must be NULL and not converted to 0.0."""
        sensor = db_session.scalars(select(Sensor)).first()
        assert sensor is not None

        missing_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=30)
        obs = Observation(
            observed_at=missing_time,
            sensor_id=sensor.id,
            metric_type="test_missing_metric",
            numeric_value=None,  # Unavailable / failed sensor reading
            unit="mm",
            quality_flag="MISSING",
            source="test_telemetry",
        )
        db_session.add(obs)
        db_session.commit()

        # Read back
        fetched = db_session.scalars(
            select(Observation).where(
                Observation.observed_at == missing_time,
                Observation.sensor_id == sensor.id,
                Observation.metric_type == "test_missing_metric",
            )
        ).first()

        assert fetched is not None
        assert fetched.numeric_value is None, "Missing reading must be NULL"
        assert fetched.numeric_value != 0, "Missing reading must NOT be converted to zero"
        assert fetched.quality_flag == "MISSING"

    def test_duplicate_protection_retransmissions(self, db_session):
        """Rule 4: QoS-1 retransmissions with identical device_sequence must trigger integrity constraint."""
        sensor = db_session.scalars(select(Sensor)).first()
        assert sensor is not None

        t = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=60)
        seq = int(datetime.now().timestamp() * 1000) % 2147483647

        # First insert
        obs1 = Observation(
            observed_at=t,
            sensor_id=sensor.id,
            metric_type="test_dedup_metric",
            numeric_value=10.0,
            unit="mm",
            quality_flag="VALID",
            device_sequence=seq,
        )
        db_session.add(obs1)
        db_session.commit()

        # Attempt duplicate insert with same (sensor_id, device_sequence, observed_at)
        obs2 = Observation(
            observed_at=t,
            sensor_id=sensor.id,
            metric_type="test_dedup_metric",
            numeric_value=10.0,
            unit="mm",
            quality_flag="VALID",
            device_sequence=seq,
        )
        db_session.add(obs2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
