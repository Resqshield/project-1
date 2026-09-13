"""ResQShield FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.auth import router as auth_router
from backend.app.api.contract import router as contract_router
from backend.app.api.public_alerts import router as public_alerts_router
from backend.app.api.health import router as health_router
from backend.app.config import get_settings


def create_app() -> FastAPI:
    """Application factory — builds and returns a configured FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # --- Routers ---
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(contract_router, prefix=settings.api_prefix)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(public_alerts_router, prefix=settings.api_prefix)

    return app


app = create_app()
