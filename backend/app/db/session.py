"""Database session and engine management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.config import get_settings

# --- Async engine for application runtime ---
_async_engine = None
_async_session_maker = None


def get_async_engine():
    """Return singleton async engine."""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            echo=(settings.env == "development"),
            future=True,
        )
    return _async_engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return singleton async session factory."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_async_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        yield session


# --- Sync engine for migrations, seeding, and management scripts ---
def get_sync_engine():
    """Return synchronous engine using database_url_sync."""
    settings = get_settings()
    return create_engine(
        settings.database_url_sync,
        echo=(settings.env == "development"),
        future=True,
    )
