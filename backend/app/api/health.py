"""Health-check API router."""

from __future__ import annotations

from fastapi import APIRouter, status

from backend.app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict:
    """Return application health status and basic configuration metadata.

    This endpoint is intentionally public and lightweight — suitable for
    load-balancer probes, smoke tests, and deployment verification.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.env,
        "pilot_id": settings.pilot_id,
    }
