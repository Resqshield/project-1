"""Initial schema with PostGIS, TimescaleDB hypertable, and all core entities.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-09-11 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable Required Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # 2. Regions
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_regions_code"),
    )
    op.create_index("ix_regions_code", "regions", ["code"])

    # 3. Catchments
    op.create_table(
        "catchments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("geometry", Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=False),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_catchments_code"),
    )
    op.create_index("ix_catchments_code", "catchments", ["code"])

    # 4. Villages
    op.create_table(
        "villages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("catchment_id", sa.Integer(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False),
        sa.Column("boundary", Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=True),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["catchment_id"], ["catchments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_villages_code"),
    )
    op.create_index("ix_villages_code", "villages", ["code"])

    # 5. Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role_name", sa.String(length=64), server_default="operator", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # 6. Sensors
    op.create_table(
        "sensors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sensor_code", sa.String(length=64), nullable=False),
        sa.Column("sensor_type", sa.String(length=64), nullable=False),
        sa.Column("village_id", sa.Integer(), nullable=True),
        sa.Column("catchment_id", sa.Integer(), nullable=True),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("installation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["catchment_id"], ["catchments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sensor_code", name="uq_sensors_code"),
    )
    op.create_index("ix_sensors_sensor_code", "sensors", ["sensor_code"])
    op.create_index("ix_sensors_sensor_type", "sensors", ["sensor_type"])

    # 7. Observations (Time-series hypertable)
    op.create_table(
        "observations",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sensor_id", sa.Integer(), nullable=False),
        sa.Column("metric_type", sa.String(length=64), nullable=False),
        sa.Column("numeric_value", sa.Double(), nullable=True),  # Missing != 0: Nullable
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("quality_flag", sa.String(length=32), server_default="VALID", nullable=False),
        sa.Column("source", sa.String(length=64), server_default="sensor_telemetry", nullable=False),
        sa.Column("device_sequence", sa.BigInteger(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provenance_metadata", JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("observed_at", "sensor_id", "metric_type", name="pk_observations"),
        sa.UniqueConstraint("sensor_id", "device_sequence", "observed_at", name="uq_sensor_seq_observed"),
    )
    op.create_index("ix_observations_sensor_observed", "observations", ["sensor_id", "observed_at"])
    op.create_index("ix_observations_metric_observed", "observations", ["metric_type", "observed_at"])

    # 8. Configure TimescaleDB Hypertable on observations
    op.execute("SELECT create_hypertable('observations', 'observed_at', if_not_exists => TRUE);")

    # 9. Roads
    op.create_table(
        "roads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("road_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("surface_type", sa.String(length=64), server_default="paved", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="OPEN", nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("geometry", Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True), nullable=False),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("road_code", name="uq_roads_code"),
    )
    op.create_index("ix_roads_road_code", "roads", ["road_code"])

    # 10. Shelters
    op.create_table(
        "shelters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shelter_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("capacity", sa.Integer(), server_default="100", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="AVAILABLE", nullable=False),
        sa.Column("village_id", sa.Integer(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shelter_code", name="uq_shelters_code"),
    )
    op.create_index("ix_shelters_shelter_code", "shelters", ["shelter_code"])

    # 11. Predictions
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_code", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("catchment_id", sa.Integer(), nullable=True),
        sa.Column("village_id", sa.Integer(), nullable=True),
        sa.Column("target_metric", sa.String(length=64), nullable=False),
        sa.Column("predicted_value", sa.Double(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Double(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["catchment_id"], ["catchments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prediction_code", name="uq_predictions_code"),
    )
    op.create_index("ix_predictions_code", "predictions", ["prediction_code"])
    op.create_index("ix_predictions_model_name", "predictions", ["model_name"])

    # 12. Warnings
    op.create_table(
        "warnings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("warning_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("catchment_id", sa.Integer(), nullable=True),
        sa.Column("village_id", sa.Integer(), nullable=True),
        sa.Column("prediction_id", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["catchment_id"], ["catchments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warning_code", name="uq_warnings_code"),
    )
    op.create_index("ix_warnings_code", "warnings", ["warning_code"])

    # 13. Incidents
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("incident_code", sa.String(length=64), nullable=False),
        sa.Column("incident_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="REPORTED", nullable=False),
        sa.Column("severity", sa.String(length=32), server_default="MEDIUM", nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False),
        sa.Column("village_id", sa.Integer(), nullable=True),
        sa.Column("road_id", sa.Integer(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("metadata_json", JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["road_id"], ["roads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_code", name="uq_incidents_code"),
    )
    op.create_index("ix_incidents_code", "incidents", ["incident_code"])

    # 14. Field Reports
    op.create_table(
        "field_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_code", sa.String(length=64), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=True),
        sa.Column("village_id", sa.Integer(), nullable=True),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.String(length=2048), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("attachments_json", JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_code", name="uq_field_reports_code"),
    )
    op.create_index("ix_field_reports_code", "field_reports", ["report_code"])

    # 15. Audit Logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("performed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("changes_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])

    # 16. Model Registry
    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.String(length=512), nullable=False),
        sa.Column("input_schema_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("metrics_json", JSONB(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="EXPERIMENTAL", nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_registry_model_name", "model_registry", ["model_name"])


def downgrade() -> None:
    op.drop_table("model_registry")
    op.drop_table("audit_logs")
    op.drop_table("field_reports")
    op.drop_table("incidents")
    op.drop_table("warnings")
    op.drop_table("predictions")
    op.drop_table("shelters")
    op.drop_table("roads")
    op.drop_table("observations")
    op.drop_table("sensors")
    op.drop_table("users")
    op.drop_table("villages")
    op.drop_table("catchments")
    op.drop_table("regions")
