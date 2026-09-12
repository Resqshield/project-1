"""GeoJSON hydrology adapter for B05."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from backend.app.connectors.base import (
    ExternalSourceAdapter,
    NormalizedExternalRecord,
    build_record,
)


class GeoJSONHydrologyAdapter(ExternalSourceAdapter):
    def __init__(
        self,
        *,
        source_id: str,
        temporal_resolution_minutes: float,
        spatial_resolution_m: float | None = None,
        provenance_status: str = "MEASURED",
    ) -> None:
        self.source_id = source_id
        self.temporal_resolution_minutes = temporal_resolution_minutes
        self.spatial_resolution_m = spatial_resolution_m
        self.provenance_status = provenance_status

    def normalize(
        self,
        payload: str | dict[str, Any],
        evaluation_time: datetime,
    ) -> list[NormalizedExternalRecord]:
        data = json.loads(payload) if isinstance(payload, str) else payload

        records = []

        for feature in data.get("features", []):
            props = feature.get("properties", {})

            raw_value = props.get("water_level_m")

            value = (
                None
                if raw_value in (None, "")
                else float(raw_value)
            )

            records.append(
                build_record(
                    source_id=props.get("source_id") or self.source_id,
                    source_type="HYDROLOGY",
                    metric="water_level_m",
                    observed_at=props["observed_at"],
                    ingested_at=props["ingested_at"],
                    evaluation_time=evaluation_time,
                    value=value,
                    unit=props.get("unit", "m"),
                    temporal_resolution_minutes=props.get(
                        "temporal_resolution_minutes",
                        self.temporal_resolution_minutes,
                    ),
                    spatial_resolution_m=props.get(
                        "spatial_resolution_m",
                        self.spatial_resolution_m,
                    ),
                    provenance_status=props.get(
                        "provenance_status",
                        self.provenance_status,
                    ),
                    adapter_name="geojson_hydrology",
                )
            )

        return records
