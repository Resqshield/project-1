"""Sensing models: Sensor registry and Time-Series Observation hypertable."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Sensor(Base):
    """Physical or virtual sensor device registry."""

    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensor_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    sensor_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    village_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("villages.id", ondelete="SET NULL"),
        nullable=True,
    )
    catchment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("catchments.id", ondelete="SET NULL"),
        nullable=True,
    )
    location: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    village: Mapped[Optional[Village]] = relationship("Village", back_populates="sensors")
    catchment: Mapped[Optional[Catchment]] = relationship("Catchment", back_populates="sensors")
    observations: Mapped[list[Observation]] = relationship("Observation", back_populates="sensor")


class Observation(Base):
    """High-frequency environmental observation time-series record.

    TimescaleDB hypertable partitioned on ``observed_at``.
    Unified representation for rainfall, soil moisture, water level, pore pressure,
    tilt, etc.

    CORE PRINCIPLES ENFORCED:
    1. MISSING DATA != ZERO:
       ``numeric_value`` is nullable. When a sensor reports an error or missing
       reading, ``numeric_value`` is NULL, accompanied by ``quality_flag='MISSING'``.
       It is NEVER coerced to 0.0.
    2. TIME PRESERVATION:
       ``observed_at`` preserves original event time at the sensor.
       ``ingested_at`` records backend receipt time. Both are timezone-aware UTC.
    3. PROVENANCE:
       Includes ``source``, ``sensor_id``, ``quality_flag``, and ``provenance_metadata``.
    4. DUPLICATE PROTECTION:
       ``device_sequence`` allows detecting and discarding QoS-1 retransmissions.
    """

    __tablename__ = "observations"
    __table_args__ = (
        PrimaryKeyConstraint("observed_at", "sensor_id", "metric_type", name="pk_observations"),
        UniqueConstraint("sensor_id", "device_sequence", "observed_at", name="uq_sensor_seq_observed"),
        Index("ix_observations_sensor_observed", "sensor_id", "observed_at"),
        Index("ix_observations_metric_observed", "metric_type", "observed_at"),
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        primary_key=True,
    )
    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    metric_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        primary_key=True,
    )
    numeric_value: Mapped[Optional[float]] = mapped_column(
        Double,
        nullable=True,  # Missing != 0: Explicitly NULL when reading unavailable
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_flag: Mapped[str] = mapped_column(
        String(32),
        default="VALID",
        nullable=False,  # VALID, SUSPECT, MISSING, ERROR
    )
    source: Mapped[str] = mapped_column(
        String(64),
        default="sensor_telemetry",
        nullable=False,
    )
    device_sequence: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,  # Device sequence counter for QoS-1 deduplication
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    provenance_metadata: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    sensor: Mapped[Sensor] = relationship("Sensor", back_populates="observations")
