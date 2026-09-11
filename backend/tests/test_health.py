"""Tests for the /health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import create_app


def _fresh_client(**env_overrides: str) -> TestClient:
    """Build a TestClient with optional settings overrides.

    We bypass the module-level ``app`` and call ``create_app()`` directly
    so each test gets a clean FastAPI instance.
    """
    # Clear the lru_cache so overrides take effect
    get_settings.cache_clear()
    application = create_app()
    return TestClient(application)


class TestHealthEndpoint:
    """Verify the health-check route."""

    def setup_method(self):
        get_settings.cache_clear()

    def test_health_returns_200(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        assert resp.status_code == 200

    def test_health_body_contains_status_ok(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body = resp.json()
        assert body["status"] == "ok"

    def test_health_body_contains_app_name(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body = resp.json()
        assert body["app_name"] == settings.app_name

    def test_health_body_contains_environment(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body = resp.json()
        assert body["environment"] == settings.env

    def test_health_body_contains_pilot_id(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body = resp.json()
        assert body["pilot_id"] == settings.pilot_id

    def test_health_with_overridden_env(self, monkeypatch):
        monkeypatch.setenv("RESQ_ENV", "staging")
        monkeypatch.setenv("RESQ_APP_NAME", "ResQNet-Test")
        get_settings.cache_clear()
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body = resp.json()
        assert body["environment"] == "staging"
        assert body["app_name"] == "ResQNet-Test"

    def test_health_does_not_expose_database_url(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body = resp.json()
        assert "database_url" not in body

    def test_health_does_not_expose_secrets(self):
        client = _fresh_client()
        settings = get_settings()
        resp = client.get(f"{settings.api_prefix}/health")
        body_text = resp.text
        assert "password" not in body_text.lower()
