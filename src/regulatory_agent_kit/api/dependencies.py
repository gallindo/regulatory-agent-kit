"""FastAPI dependency injection for shared resources."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request  # noqa: TC002


async def get_db_pool(request: Request) -> Any:
    """Return the database connection pool from app state.

    Returns ``None`` when the pool has not been initialised (tests, lite mode).
    """
    return getattr(request.app.state, "db_pool", None)


async def get_temporal_client(request: Request) -> Any:
    """Return the Temporal client from app state.

    Returns ``None`` when Temporal is unavailable (tests, lite mode).
    """
    return getattr(request.app.state, "temporal_client", None)


async def get_audit_signer(request: Request) -> Any:
    """Return the Ed25519 audit signer from app state.

    Returns ``None`` when the signer is not configured.
    """
    return getattr(request.app.state, "audit_signer", None)


async def get_settings(request: Request) -> Any:
    """Return application settings from app state."""
    return getattr(request.app.state, "settings", None)
