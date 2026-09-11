"""Schema and ORM structural tests for ResQShield database entities.

Verifies:
- All 14 tables registered in Base.metadata
- PostGIS geometry column configurations and SRID 4326
- Core disaster-management rules:
  1. Missing != 0: Observation.numeric_value is strictly nullable
  2. Timescale hypertable primary key: Observation PK includes observed_at
  3. Duplicate protection: Observation has device_sequence deduplication constraint
  4. Timezone-aware timestamp columns across models
"""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Double
import pytest

from backend.app.db.base import Base
import backend.app.models  # noqa: F401
from backend.app.models.events import FieldReport, Incident, Prediction, Warning
from backend.app.models.geography import Catchment, Region, Village
from backend.app.models.governance import AuditLog, ModelRegistry
from backend.app.models.operations import Road, Shelter
from backend.app.models.sensing import Observation, Sensor
from backend.app.models.users import User


class TestModelRegistration:
    """Verify all expected domain entities are registered in the ORM metadata."""

    EXPECTED_TABLES = {
        "regions",
        "catchments",
        "villages",
        "users",
        "sensors",
        "observations",
        "roads",
        "shelters",
        "predictions",
        "warnings",
        "incidents",
        "field_reports",
        "audit_logs",
        "model_registry",
    }

    def test_all_tables_present_in_metadata(self):
        actual_tables = set(Base.metadata.tables.keys())
        assert self.EXPECTED_TABLES.issubset(actual_tables), (
            f"Missing tables: {self.EXPECTED_TABLES - actual_tables}"
        )


class TestDataModelPrinciples:
    """Verify core disaster-management data model principles."""

    def test_missing_data_not_zero_numeric_value_nullable(self):
        """Rule 1: MISSING != ZERO.

        Observation.numeric_value must be NULLABLE so that missing or unavailable
        sensor observations are stored as NULL rather than 0.
        """
        table = Base.metadata.tables["observations"]
        col = table.columns["numeric_value"]
        assert col.nullable is True, "Observation.numeric_value must be nullable (missing != 0)"
        assert isinstance(col.type, Double)

    def test_timescale_hypertable_composite_primary_key(self):
        """Rule 2: TimescaleDB hypertable requirement.

        The partitioning column (observed_at) MUST be part of the primary key.
        """
        table = Base.metadata.tables["observations"]
        pk_cols = [c.name for c in table.primary_key.columns]
        assert "observed_at" in pk_cols, "observed_at must be in primary key for TimescaleDB"
        assert "sensor_id" in pk_cols
        assert "metric_type" in pk_cols

    def test_duplicate_protection_constraint(self):
        """Rule 4: QoS-1 deduplication support.

        observations table must have a unique constraint or index including
        (sensor_id, device_sequence, observed_at) to reject duplicate deliveries.
        """
        table = Base.metadata.tables["observations"]
        uq_constraints = [c.name for c in table.constraints if hasattr(c, "columns")]
        uq_col_sets = [{col.name for col in c.columns} for c in table.constraints if hasattr(c, "columns")]

        has_dedup = any({"sensor_id", "device_sequence", "observed_at"}.issubset(s) for s in uq_col_sets)
        assert has_dedup, "observations table must enforce uniqueness on sensor_id + device_sequence + observed_at"

    def test_timezone_aware_timestamps(self):
        """Rule 2: PRESERVE TIME.

        All timestamp columns must have timezone=True.
        """
        table = Base.metadata.tables["observations"]
        assert table.columns["observed_at"].type.timezone is True
        assert table.columns["ingested_at"].type.timezone is True


class TestSpatialColumnConfigurations:
    """Verify PostGIS geometry columns and SRID 4326 specification."""

    def test_catchment_geometry(self):
        table = Base.metadata.tables["catchments"]
        col = table.columns["geometry"]
        assert isinstance(col.type, Geometry)
        assert col.type.geometry_type == "POLYGON"
        assert col.type.srid == 4326

    def test_village_location(self):
        table = Base.metadata.tables["villages"]
        col = table.columns["location"]
        assert isinstance(col.type, Geometry)
        assert col.type.geometry_type == "POINT"
        assert col.type.srid == 4326

    def test_sensor_location(self):
        table = Base.metadata.tables["sensors"]
        col = table.columns["location"]
        assert isinstance(col.type, Geometry)
        assert col.type.geometry_type == "POINT"
        assert col.type.srid == 4326

    def test_road_geometry(self):
        table = Base.metadata.tables["roads"]
        col = table.columns["geometry"]
        assert isinstance(col.type, Geometry)
        assert col.type.geometry_type == "LINESTRING"
        assert col.type.srid == 4326

    def test_shelter_location(self):
        table = Base.metadata.tables["shelters"]
        col = table.columns["location"]
        assert isinstance(col.type, Geometry)
        assert col.type.geometry_type == "POINT"
        assert col.type.srid == 4326

    def test_incident_location(self):
        table = Base.metadata.tables["incidents"]
        col = table.columns["location"]
        assert isinstance(col.type, Geometry)
        assert col.type.geometry_type == "POINT"
        assert col.type.srid == 4326


class TestGovernanceModels:
    """Verify audit log and model registry schemas."""

    def test_audit_log_structure(self):
        table = Base.metadata.tables["audit_logs"]
        for col_name in ["entity_type", "entity_id", "action", "timestamp", "changes_json"]:
            assert col_name in table.columns

    def test_model_registry_structure(self):
        table = Base.metadata.tables["model_registry"]
        for col_name in ["model_name", "version", "algorithm", "artifact_uri", "status"]:
            assert col_name in table.columns
