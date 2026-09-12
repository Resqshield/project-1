"""B06 versioned REST and live WebSocket API contract."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.api.schemas import (
    APIContractResponse,
    APITransports,
    LiveStatusResponse,
)
from backend.app.config import get_settings


router = APIRouter(tags=["contract"])

CONTRACT_VERSION = "1.0"
LIVE_PROTOCOL_VERSION = "1"


@router.get(
    "/contract",
    response_model=APIContractResponse,
)
def api_contract() -> APIContractResponse:
    """Return the currently implemented backend API foundation."""

    settings = get_settings()
    prefix = settings.api_prefix

    return APIContractResponse(
        contract_version=CONTRACT_VERSION,
        api_version="v1",
        transports=APITransports(
            rest_base_path=prefix,
            websocket_path=f"{prefix}/ws/live",
        ),
        implemented_rest_paths=[
            f"{prefix}/health",
            f"{prefix}/contract",
            f"{prefix}/live/status",
        ],
        supported_client_messages=[
            "ping",
        ],
        extension_points=[
            "events",
            "source_health",
            "hazards",
            "routes",
            "shelters",
            "alerts",
        ],
    )


@router.get(
    "/live/status",
    response_model=LiveStatusResponse,
)
def live_status() -> LiveStatusResponse:
    """Report transport capability without claiming live hazard data."""

    settings = get_settings()

    return LiveStatusResponse(
        transport="websocket",
        transport_status="ready",
        data_mode="contract_only",
        endpoint=f"{settings.api_prefix}/ws/live",
        protocol_version=LIVE_PROTOCOL_VERSION,
        supported_client_messages=[
            "ping",
        ],
    )


@router.websocket("/ws/live")
async def live_websocket(
    websocket: WebSocket,
) -> None:
    """Minimal live transport contract.

    Domain event subscriptions are intentionally deferred to later
    backend tasks. B06 proves connection and structured messaging only.
    """

    await websocket.accept()

    try:
        while True:
            payload = await websocket.receive_json()

            if not isinstance(payload, dict):
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "INVALID_MESSAGE",
                        "message": (
                            "WebSocket message must be a JSON object."
                        ),
                    }
                )
                continue

            message_type = payload.get("type")

            if message_type == "ping":
                response = {
                    "type": "pong",
                    "protocol_version": LIVE_PROTOCOL_VERSION,
                }

                if "request_id" in payload:
                    response["request_id"] = payload["request_id"]

                await websocket.send_json(response)
                continue

            await websocket.send_json(
                {
                    "type": "error",
                    "code": "UNKNOWN_MESSAGE_TYPE",
                    "message": (
                        "Supported client message types: ping"
                    ),
                    "received_type": message_type,
                }
            )

    except WebSocketDisconnect:
        return
