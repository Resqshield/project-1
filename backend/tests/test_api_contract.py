"""Acceptance tests for the B06 REST + live API contract."""

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import create_app


def _fresh_client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


class TestAPIContract:
    def setup_method(self):
        get_settings.cache_clear()

    def test_contract_returns_200(self):
        client = _fresh_client()
        settings = get_settings()

        response = client.get(
            f"{settings.api_prefix}/contract"
        )

        assert response.status_code == 200
        assert response.json()["contract_version"] == "1.0"
        assert response.json()["api_version"] == "v1"

    def test_contract_lists_only_real_foundation_paths(self):
        client = _fresh_client()
        settings = get_settings()

        body = client.get(
            f"{settings.api_prefix}/contract"
        ).json()

        assert body["implemented_rest_paths"] == [
            f"{settings.api_prefix}/health",
            f"{settings.api_prefix}/contract",
            f"{settings.api_prefix}/live/status",
        ]

        assert "hazards" in body["extension_points"]
        assert "routes" in body["extension_points"]
        assert "alerts" in body["extension_points"]

    def test_live_status_is_contract_only(self):
        client = _fresh_client()
        settings = get_settings()

        response = client.get(
            f"{settings.api_prefix}/live/status"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["transport"] == "websocket"
        assert body["transport_status"] == "ready"
        assert body["data_mode"] == "contract_only"
        assert body["endpoint"] == (
            f"{settings.api_prefix}/ws/live"
        )

    def test_openapi_exposes_rest_contract_paths(self):
        client = _fresh_client()
        settings = get_settings()

        schema = client.get(
            f"{settings.api_prefix}/openapi.json"
        ).json()

        paths = schema["paths"]

        assert f"{settings.api_prefix}/health" in paths
        assert f"{settings.api_prefix}/contract" in paths
        assert f"{settings.api_prefix}/live/status" in paths

    def test_existing_health_endpoint_still_works(self):
        client = _fresh_client()
        settings = get_settings()

        response = client.get(
            f"{settings.api_prefix}/health"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_websocket_ping_returns_pong(self):
        client = _fresh_client()
        settings = get_settings()

        with client.websocket_connect(
            f"{settings.api_prefix}/ws/live"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "ping",
                    "request_id": "test-001",
                }
            )

            response = websocket.receive_json()

            assert response == {
                "type": "pong",
                "protocol_version": "1",
                "request_id": "test-001",
            }

    def test_unknown_websocket_message_returns_structured_error(self):
        client = _fresh_client()
        settings = get_settings()

        with client.websocket_connect(
            f"{settings.api_prefix}/ws/live"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "not-supported",
                }
            )

            response = websocket.receive_json()

            assert response["type"] == "error"
            assert (
                response["code"]
                == "UNKNOWN_MESSAGE_TYPE"
            )
            assert (
                response["received_type"]
                == "not-supported"
            )

    def test_websocket_remains_usable_after_unknown_message(self):
        client = _fresh_client()
        settings = get_settings()

        with client.websocket_connect(
            f"{settings.api_prefix}/ws/live"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "unknown",
                }
            )

            error = websocket.receive_json()
            assert error["type"] == "error"

            websocket.send_json(
                {
                    "type": "ping",
                }
            )

            pong = websocket.receive_json()

            assert pong["type"] == "pong"
            assert pong["protocol_version"] == "1"
