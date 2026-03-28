"""FastAPI dependency injection stubs for shared resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import Request


async def get_db_pool(request: Request) -> Any:
    """Return the database connection pool from app state.

    In production this yields a ``psycopg.AsyncConnectionPool``.
    During tests or before startup it returns ``None``.
    """
    return getattr(request.app.state, "db_pool", None)


async def get_temporal_client(request: Request) -> Any:
    """Return the Temporal client from app state.

    In production this yields a ``temporalio.client.Client``.
    During tests or before startup it returns ``None``.
    """
    return getattr(request.app.state, "temporal_client", None)


async def get_audit_signer(request: Request) -> Any:
    """Return the Ed25519 audit signer from app state.

    In production this yields an ``AuditSigner`` instance.
    During tests or before startup it returns ``None``.
    """
    return getattr(request.app.state, "audit_signer", None)


async def get_settings(request: Request) -> Any:
    """Return application settings from app state.

    Returns the ``Settings`` instance stored during startup.
    """
    return getattr(request.app.state, "settings", None)
