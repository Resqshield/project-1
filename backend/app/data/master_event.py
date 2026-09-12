"""Canonical master-event dataset contract.

T02 requires every downstream model/test to consume one consistent event
structure. Missing environmental values remain None; they are never converted
to zero merely because observations are unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MasterEventRecord(BaseModel):
    """One canonical timestamped hazard/event observation."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    timestamp: datetime

    pilot_id: str
    region_code: str
    catchment_code: Optional[str] = None
    village_code: Optional[str] = None

    rainfall_mm_30m: Optional[float] = None
    rainfall_mm_1h: Optional[float] = None
    rainfall_mm_3h: Optional[float] = None
    rainfall_mm_6h: Optional[float] = None
    rainfall_mm_24h: Optional[float] = None
    rainfall_mm_3d: Optional[float] = None
    rainfall_mm_7d: Optional[float] = None

    wetness_value: Optional[float] = None
    wetness_unit: Optional[str] = None

    water_level_m: Optional[float] = None
    slope_state: Optional[str] = None

    hazard_label: str
    label_confidence: float = Field(ge=0.0, le=1.0)

    # T34: uncertainty is preserved instead of deleting or
    # pretending weak/approximate labels are exact.
    label_window_start: Optional[datetime] = None
    label_window_end: Optional[datetime] = None
    location_precision: Optional[str] = None
    location_uncertain: bool = False

    source_id: str
    source_type: str
    source_timestamp: datetime
    provenance_status: str

    @field_validator(
        "timestamp",
        "source_timestamp",
        "label_window_start",
        "label_window_end",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return value

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        return value

    @model_validator(mode="after")
    def uncertainty_metadata_must_be_consistent(self):
        start = self.label_window_start
        end = self.label_window_end

        if (start is None) != (end is None):
            raise ValueError(
                "label uncertainty window requires both start and end"
            )

        if start is not None and end is not None and start > end:
            raise ValueError(
                "label_window_start must not be after label_window_end"
            )

        if self.location_uncertain:
            if (
                self.location_precision is None
                or not self.location_precision.strip()
            ):
                raise ValueError(
                    "uncertain location requires location_precision"
                )

        return self

    @field_validator("event_id", "pilot_id", "region_code", "hazard_label",
                     "source_id", "source_type", "provenance_status")
    @classmethod
    def required_strings_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required string field must not be blank")
        return value
