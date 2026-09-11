"""Operations models: Roads and Shelters with PostGIS geometries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Road(Base):
    """Road segment geometry for accessibility and route modeling."""

    __tablename__ = "roads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    road_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    surface_type: Mapped[str] = mapped_column(String(64), default="paved", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)  # OPEN, BLOCKED, AT_RISK
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    geometry: Mapped[str] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    region: Mapped[Region] = relationship("Region", back_populates="roads")


class Shelter(Base):
    """Emergency evacuation shelter location."""

    __tablename__ = "shelters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shelter_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="AVAILABLE", nullable=False)
    village_id: Mapped[int] = mapped_column(ForeignKey("villages.id", ondelete="CASCADE"), nullable=False)
    location: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    village: Mapped[Village] = relationship("Village", back_populates="shelters")
