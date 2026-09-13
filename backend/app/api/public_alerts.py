"""Public warning-access API.

B03 establishes unauthenticated access to active public warnings.
The later alert-service task can populate this stable endpoint with live alerts.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/public", tags=["public-alerts"])


@router.get("/alerts")
async def list_public_alerts() -> dict[str, object]:
    """Return public warnings without requiring authentication."""

    return {
        "access": "public",
        "alerts": [],
    }
