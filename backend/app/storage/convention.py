"""Object storage path and key naming conventions.

Defines deterministic, configurable object storage keys for:
- Raw ingest data: raw/<source>/<YYYY>/<MM>/<DD>/<filename>
- Derived datasets: derived/<dataset>/<version>/<filename>
- Model artifacts: models/<model>/<version>/<filename>
- Operational attachments: attachments/<context>/<YYYY>/<MM>/<filename>
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Optional

from backend.app.config import Settings, get_settings


def _sanitize_path_segment(segment: str) -> str:
    """Sanitize a path component to ensure safe, deterministic S3 key characters."""
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", segment.strip())
    return sanitized or "default"


class StorageConvention:
    """Configurable object storage key builder."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @property
    def base_prefix(self) -> str:
        prefix = self.settings.storage_base_prefix.strip().strip("/")
        return f"{prefix}/" if prefix else ""

    @property
    def bucket(self) -> str:
        return self.settings.storage_bucket

    def build_raw_key(
        self,
        source: str,
        timestamp: datetime,
        filename: str,
    ) -> str:
        """Deterministic object key for raw ingestion data.

        Format: [prefix/]raw/<source>/<YYYY>/<MM>/<DD>/<filename>
        """
        # Ensure UTC
        if timestamp.tzinfo is None:
            utc_dt = timestamp.replace(tzinfo=timezone.utc)
        else:
            utc_dt = timestamp.astimezone(timezone.utc)

        clean_source = _sanitize_path_segment(source)
        clean_file = _sanitize_path_segment(filename)
        return (
            f"{self.base_prefix}raw/{clean_source}/"
            f"{utc_dt.year:04d}/{utc_dt.month:02d}/{utc_dt.day:02d}/{clean_file}"
        )

    def build_derived_key(
        self,
        dataset_name: str,
        version: str,
        filename: str,
    ) -> str:
        """Deterministic object key for derived analytical datasets.

        Format: [prefix/]derived/<dataset>/<version>/<filename>
        """
        clean_dataset = _sanitize_path_segment(dataset_name)
        clean_version = _sanitize_path_segment(version)
        clean_file = _sanitize_path_segment(filename)
        return f"{self.base_prefix}derived/{clean_dataset}/{clean_version}/{clean_file}"

    def build_model_artifact_key(
        self,
        model_name: str,
        version: str,
        filename: str,
    ) -> str:
        """Deterministic object key for trained model weights/artifacts.

        Format: [prefix/]models/<model>/<version>/<filename>
        """
        clean_model = _sanitize_path_segment(model_name)
        clean_version = _sanitize_path_segment(version)
        clean_file = _sanitize_path_segment(filename)
        return f"{self.base_prefix}models/{clean_model}/{clean_version}/{clean_file}"

    def build_attachment_key(
        self,
        entity_type: str,
        entity_code: str,
        timestamp: datetime,
        filename: str,
    ) -> str:
        """Deterministic object key for incident or field report attachments.

        Format: [prefix/]attachments/<entity_type>/<entity_code>/<YYYY>/<MM>/<filename>
        """
        if timestamp.tzinfo is None:
            utc_dt = timestamp.replace(tzinfo=timezone.utc)
        else:
            utc_dt = timestamp.astimezone(timezone.utc)

        clean_type = _sanitize_path_segment(entity_type)
        clean_code = _sanitize_path_segment(entity_code)
        clean_file = _sanitize_path_segment(filename)
        return (
            f"{self.base_prefix}attachments/{clean_type}/{clean_code}/"
            f"{utc_dt.year:04d}/{utc_dt.month:02d}/{clean_file}"
        )

    def to_s3_uri(self, key: str) -> str:
        """Format an object key as an s3:// URI."""
        return f"s3://{self.bucket}/{key.lstrip('/')}"
