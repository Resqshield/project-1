"""Tests for the central Settings configuration."""

from __future__ import annotations

import os

from backend.app.config import Settings


class TestSettingsDefaults:
    """Verify that default values load correctly without any env vars."""

    def test_default_env(self):
        settings = Settings(_env_file=None)
        assert settings.env == "development"

    def test_default_app_name(self):
        settings = Settings(_env_file=None)
        assert settings.app_name == "ResQShield"

    def test_default_api_host(self):
        settings = Settings(_env_file=None)
        assert settings.api_host == "127.0.0.1"

    def test_default_api_port(self):
        settings = Settings(_env_file=None)
        assert settings.api_port == 8000

    def test_default_api_prefix(self):
        settings = Settings(_env_file=None)
        assert settings.api_prefix == "/api/v1"

    def test_default_database_url_is_placeholder(self):
        settings = Settings(_env_file=None)
        assert "localhost" in settings.database_url

    def test_default_database_url_sync_is_placeholder(self):
        settings = Settings(_env_file=None)
        assert "localhost" in settings.database_url_sync

    def test_default_mqtt_broker_host(self):
        settings = Settings(_env_file=None)
        assert settings.mqtt_broker_host == "localhost"

    def test_default_mqtt_broker_port(self):
        settings = Settings(_env_file=None)
        assert settings.mqtt_broker_port == 1883

    def test_default_mqtt_base_topic(self):
        settings = Settings(_env_file=None)
        assert settings.mqtt_base_topic == "resqshield/"

    def test_default_storage_endpoint(self):
        settings = Settings(_env_file=None)
        assert "localhost" in settings.storage_endpoint

    def test_default_storage_bucket(self):
        settings = Settings(_env_file=None)
        assert settings.storage_bucket == "resqshield-data"

    def test_default_storage_base_prefix_is_empty(self):
        settings = Settings(_env_file=None)
        assert settings.storage_base_prefix == ""

    def test_default_model_artifact_dir_is_relative(self):
        settings = Settings(_env_file=None)
        assert settings.model_artifact_dir == "./artifacts"
        # Must not contain machine-specific absolute paths
        assert "C:\\" not in settings.model_artifact_dir
        assert "/home/" not in settings.model_artifact_dir

    def test_default_pilot_id_is_placeholder(self):
        settings = Settings(_env_file=None)
        assert settings.pilot_id == "PILOT_PLACEHOLDER"

    def test_default_holdout_id_is_placeholder(self):
        settings = Settings(_env_file=None)
        assert settings.holdout_id == "HOLDOUT_PLACEHOLDER"


class TestSettingsOverride:
    """Verify that environment variables override defaults."""

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_ENV", "production")
        settings = Settings(_env_file=None)
        assert settings.env == "production"

    def test_app_name_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_APP_NAME", "ResQNet-Custom")
        settings = Settings(_env_file=None)
        assert settings.app_name == "ResQNet-Custom"

    def test_api_port_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_API_PORT", "9090")
        settings = Settings(_env_file=None)
        assert settings.api_port == 9090

    def test_pilot_id_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_PILOT_ID", "DISTRICT_XYZ_001")
        settings = Settings(_env_file=None)
        assert settings.pilot_id == "DISTRICT_XYZ_001"

    def test_holdout_id_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_HOLDOUT_ID", "HOLDOUT_REGION_42")
        settings = Settings(_env_file=None)
        assert settings.holdout_id == "HOLDOUT_REGION_42"

    def test_database_url_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_DATABASE_URL", "postgresql+asyncpg://prod:secret@db:5432/prod")
        settings = Settings(_env_file=None)
        assert settings.database_url == "postgresql+asyncpg://prod:secret@db:5432/prod"

    def test_database_url_sync_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_DATABASE_URL_SYNC", "postgresql+psycopg2://prod:secret@db:5432/prod")
        settings = Settings(_env_file=None)
        assert settings.database_url_sync == "postgresql+psycopg2://prod:secret@db:5432/prod"

    def test_mqtt_broker_host_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_MQTT_BROKER_HOST", "mqtt.example.com")
        settings = Settings(_env_file=None)
        assert settings.mqtt_broker_host == "mqtt.example.com"

    def test_storage_bucket_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_STORAGE_BUCKET", "my-custom-bucket")
        settings = Settings(_env_file=None)
        assert settings.storage_bucket == "my-custom-bucket"

    def test_storage_base_prefix_override(self, monkeypatch):
        monkeypatch.setenv("RESQ_STORAGE_BASE_PREFIX", "deployments/pilot1")
        settings = Settings(_env_file=None)
        assert settings.storage_base_prefix == "deployments/pilot1"


class TestNoHardcodedPaths:
    """Ensure no machine-specific absolute paths leak into defaults."""

    def test_no_absolute_windows_paths_in_defaults(self):
        settings = Settings(_env_file=None)
        for field_name in Settings.model_fields:
            value = getattr(settings, field_name)
            if isinstance(value, str):
                assert not value.startswith("C:\\"), (
                    f"Field '{field_name}' contains a Windows absolute path: {value}"
                )

    def test_no_absolute_unix_home_paths_in_defaults(self):
        settings = Settings(_env_file=None)
        for field_name in Settings.model_fields:
            value = getattr(settings, field_name)
            if isinstance(value, str):
                assert "/home/" not in value, (
                    f"Field '{field_name}' contains a Unix home path: {value}"
                )
