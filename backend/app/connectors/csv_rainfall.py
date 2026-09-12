"""CSV rainfall adapter for B05."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from backend.app.connectors.base import (
    ExternalSourceAdapter,
    NormalizedExternalRecord,
    build_record,
)


class CSVRainfallAdapter(ExternalSourceAdapter):
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
        payload: str,
        evaluation_time: datetime,
    ) -> list[NormalizedExternalRecord]:
        reader = csv.DictReader(io.StringIO(payload))
        records = []

        for row in reader:
            raw_value = (row.get("rainfall_mm") or "").strip()

            value = (
                None
                if raw_value == ""
                else float(raw_value)
            )

            records.append(
                build_record(
                    source_id=self.source_id,
                    source_type="RAINFALL",
                    metric="rainfall_mm",
                    observed_at=row["observed_at"],
                    ingested_at=row["ingested_at"],
                    evaluation_time=evaluation_time,
                    value=value,
                    unit=row.get("unit") or "mm",
                    temporal_resolution_minutes=self.temporal_resolution_minutes,
                    spatial_resolution_m=self.spatial_resolution_m,
                    provenance_status=self.provenance_status,
                    adapter_name="csv_rainfall",
                )
            )

        return records
