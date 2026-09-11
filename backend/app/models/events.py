"""Decision and operational event models: Prediction, Warning, Incident, FieldReport."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Double, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Prediction(Base):
    """Machine learning model output prediction."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    catchment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("catchments.id", ondelete="SET NULL"),
        nullable=True,
    )
    village_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("villages.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_metric: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g., landslide_risk, flood_depth
    predicted_value: Mapped[float] = mapped_column(Double, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    warnings: Mapped[list[Warning]] = relationship("Warning", back_populates="prediction")


class Warning(Base):
    """Actionable alert or warning issued for a catchment or village."""

    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warning_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)  # ADVISORY, WATCH, WARNING, EMERGENCY
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, RESOLVED, CANCELLED
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    catchment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("catchments.id", ondelete="SET NULL"),
        nullable=True,
    )
    village_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("villages.id", ondelete="SET NULL"),
        nullable=True,
    )
    prediction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    prediction: Mapped[Optional[Prediction]] = relationship("Prediction", back_populates="warnings")


class Incident(Base):
    """Ground truth disaster event or physical hazard."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(64), nullable=False)  # LANDSLIDE, FLASH_FLOOD, ROAD_BLOCKAGE
    status: Mapped[str] = mapped_column(String(32), default="REPORTED", nullable=False)  # REPORTED, VERIFIED, RESPONDING, RESOLVED
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    location: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    village_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("villages.id", ondelete="SET NULL"),
        nullable=True,
    )
    road_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roads.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    field_reports: Mapped[list[FieldReport]] = relationship("FieldReport", back_populates="incident")


class FieldReport(Base):
    """Ground report submitted by field observers or responders."""

    __tablename__ = "field_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    reporter_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    village_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("villages.id", ondelete="SET NULL"),
        nullable=True,
    )
    incident_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(String(2048), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    attachments_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    incident: Mapped[Optional[Incident]] = relationship("Incident", back_populates="field_reports")
