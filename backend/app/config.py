"""Central configuration module — Pydantic Settings.

All configurable values are driven by environment variables (or .env file).
Placeholder defaults are used for development safety; production deployments
must supply real values.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    Every field maps to an env var prefixed with ``RESQ_``.
    See ``.env.example`` for the full list.
    """

    model_config = SettingsConfigDict(
        env_prefix="RESQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    env: str = "development"
    app_name: str = "ResQShield"

    # --- API Server ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # --- Database (placeholder — not connected in B01) ---
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/resqshield"
    database_url_sync: str = "postgresql+psycopg2://user:password@localhost:5432/resqshield"

    # --- MQTT Broker (placeholder — not connected in B01) ---
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_base_topic: str = "resqshield/"

    # --- Object Storage (placeholder — not connected in B01) ---
    storage_endpoint: str = "http://localhost:9000"
    storage_bucket: str = "resqshield-data"
    storage_base_prefix: str = ""

    # --- ML / Artifacts ---
    model_artifact_dir: str = "./artifacts"

    # --- Pilot Configuration ---
    # External dependencies — do NOT hard-code final geography.
    pilot_id: str = "PILOT_PLACEHOLDER"
    holdout_id: str = "HOLDOUT_PLACEHOLDER"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    The cache means environment is read once per process.  For testing,
    instantiate ``Settings()`` directly or clear the cache.
    """
    return Settings()
