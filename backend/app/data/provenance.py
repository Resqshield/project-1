"""Canonical measured/imputed/fallback/model provenance contract for T72."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ProvenanceType(str, Enum):
    MEASURED = "MEASURED"
    IMPUTED = "IMPUTED"
    FALLBACK_DERIVED = "FALLBACK_DERIVED"
    MODEL_ESTIMATED = "MODEL_ESTIMATED"


DISPLAY_LABELS = {
    ProvenanceType.MEASURED: "Measured",
    ProvenanceType.IMPUTED: "Imputed",
    ProvenanceType.FALLBACK_DERIVED: "Fallback-derived",
    ProvenanceType.MODEL_ESTIMATED: "Model-estimated",
}


@dataclass(frozen=True)
class ProvenanceRecord:
    provenance_type: str
    source_id: str
    source_timestamp: datetime
    method: str
    uncertainty_score: Optional[float] = None

    def __post_init__(self) -> None:
        kind = ProvenanceType(self.provenance_type)

        object.__setattr__(
            self,
            "provenance_type",
            kind.value,
        )

        if not self.source_id.strip():
            raise ValueError(
                "source_id must not be blank"
            )

        if not self.method.strip():
            raise ValueError(
                "method must not be blank"
            )

        timestamp = self.source_timestamp

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "source_timestamp must be timezone-aware"
            )

        object.__setattr__(
            self,
            "source_timestamp",
            timestamp.astimezone(timezone.utc),
        )

        if (
            self.uncertainty_score is not None
            and not 0.0 <= self.uncertainty_score <= 1.0
        ):
            raise ValueError(
                "uncertainty_score must be between 0 and 1"
            )

    @property
    def is_estimated(self) -> bool:
        return (
            self.provenance_type
            != ProvenanceType.MEASURED.value
        )

    @property
    def display_label(self) -> str:
        return DISPLAY_LABELS[
            ProvenanceType(self.provenance_type)
        ]

    @property
    def display_badge(self) -> str:
        if self.is_estimated:
            return (
                f"ESTIMATED — {self.display_label.upper()}"
            )

        return "MEASURED"

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "provenance_type": self.provenance_type,
            "source_id": self.source_id,
            "source_timestamp": (
                self.source_timestamp.isoformat()
            ),
            "method": self.method,
            "uncertainty_score": self.uncertainty_score,
        }

    def technical_view(self) -> dict[str, Any]:
        return {
            **self.to_storage_dict(),
            "is_estimated": self.is_estimated,
            "display_label": self.display_label,
            "display_badge": self.display_badge,
        }

    def authority_view(self) -> dict[str, Any]:
        return {
            "provenance_type": self.provenance_type,
            "display_badge": self.display_badge,
            "is_estimated": self.is_estimated,
            "source_id": self.source_id,
            "source_timestamp": (
                self.source_timestamp.isoformat()
            ),
            "method": self.method,
            "uncertainty_score": self.uncertainty_score,
        }


def merge_provenance_metadata(
    existing_metadata: Optional[dict[str, Any]],
    provenance: ProvenanceRecord,
) -> dict[str, Any]:
    """Store provenance without destroying sensor metadata such as RSSI."""

    merged = dict(existing_metadata or {})
    merged["value_provenance"] = provenance.to_storage_dict()
    return merged


def provenance_from_metadata(
    metadata: dict[str, Any],
) -> ProvenanceRecord:
    payload = metadata.get("value_provenance")

    if not isinstance(payload, dict):
        raise ValueError(
            "value_provenance metadata is required"
        )

    timestamp = datetime.fromisoformat(
        payload["source_timestamp"]
    )

    return ProvenanceRecord(
        provenance_type=payload["provenance_type"],
        source_id=payload["source_id"],
        source_timestamp=timestamp,
        method=payload["method"],
        uncertainty_score=payload.get(
            "uncertainty_score"
        ),
    )
