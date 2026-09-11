"""Tests for Object Storage Conventions."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.config import Settings
from backend.app.storage.convention import StorageConvention


@pytest.fixture
def storage():
    settings = Settings(
        _env_file=None,
        storage_bucket="test-resqshield-bucket",
        storage_base_prefix="",
    )
    return StorageConvention(settings=settings)


@pytest.fixture
def prefixed_storage():
    settings = Settings(
        _env_file=None,
        storage_bucket="test-resqshield-bucket",
        storage_base_prefix="dev-cluster/m4",
    )
    return StorageConvention(settings=settings)


class TestStorageConvention:
    """Verify deterministic S3/MinIO key naming patterns."""

    def test_raw_key_format(self, storage):
        dt = datetime(2026, 9, 11, 14, 30, 0, tzinfo=timezone.utc)
        key = storage.build_raw_key("telemetry_rain", dt, "readings_001.json")
        assert key == "raw/telemetry_rain/2026/09/11/readings_001.json"

    def test_raw_key_deterministic(self, storage):
        dt = datetime(2026, 9, 11, 14, 30, 0, tzinfo=timezone.utc)
        key1 = storage.build_raw_key("telemetry_rain", dt, "readings_001.json")
        key2 = storage.build_raw_key("telemetry_rain", dt, "readings_001.json")
        assert key1 == key2

    def test_raw_key_with_base_prefix(self, prefixed_storage):
        dt = datetime(2026, 9, 11, 14, 30, 0, tzinfo=timezone.utc)
        key = prefixed_storage.build_raw_key("telemetry_rain", dt, "readings_001.json")
        assert key == "dev-cluster/m4/raw/telemetry_rain/2026/09/11/readings_001.json"

    def test_derived_key_format(self, storage):
        key = storage.build_derived_key("rainfall_aggregates_1h", "v1.2", "batch_42.parquet")
        assert key == "derived/rainfall_aggregates_1h/v1.2/batch_42.parquet"

    def test_model_artifact_key_format(self, storage):
        key = storage.build_model_artifact_key("landslide_classifier", "0.2.1", "weights.onnx")
        assert key == "models/landslide_classifier/0.2.1/weights.onnx"

    def test_attachment_key_format(self, storage):
        dt = datetime(2026, 9, 11, 10, 15, 0, tzinfo=timezone.utc)
        key = storage.build_attachment_key("incident", "INC-001", dt, "site_photo.jpg")
        assert key == "attachments/incident/INC-001/2026/09/site_photo.jpg"

    def test_s3_uri_formatting(self, storage):
        key = "raw/sensors/2026/09/11/data.csv"
        uri = storage.to_s3_uri(key)
        assert uri == "s3://test-resqshield-bucket/raw/sensors/2026/09/11/data.csv"

    def test_sanitization_removes_dangerous_characters(self, storage):
        dt = datetime(2026, 9, 11, 14, 30, 0, tzinfo=timezone.utc)
        key = storage.build_raw_key("source with spaces/and..traversal", dt, "file;name*?.json")
        assert " " not in key
        assert ";" not in key
        assert "*" not in key
        assert "?" not in key
