"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager

from fastapi import FastAPI

from regulatory_agent_kit.api.middleware import RakAuthMiddleware
from regulatory_agent_kit.api.routes.approvals import router as approvals_router
from regulatory_agent_kit.api.routes.events import router as events_router
from regulatory_agent_kit.api.routes.runs import router as runs_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle.

    Initialises the database pool, Temporal client, audit signer, and
    settings on ``app.state``.  Each resource is optional — the app
    degrades gracefully when services are unavailable (e.g. tests, Lite Mode).
    """
    # --- startup ---
    db_pool = None
    try:
        from regulatory_agent_kit.config import load_settings

        settings = load_settings()
        application.state.settings = settings

        if not settings.lite_mode:
            try:
                from regulatory_agent_kit.database.pool import create_pool

                db_pool = await create_pool(settings.database)
                application.state.db_pool = db_pool
                logger.info("Database pool initialised")
            except Exception:
                logger.warning("Database pool not available", exc_info=True)

            try:
                from temporalio.client import Client

                temporal_client = await Client.connect(settings.temporal.address)
                application.state.temporal_client = temporal_client
                logger.info("Temporal client connected")
            except Exception:
                logger.warning("Temporal client not available", exc_info=True)

        if settings.ed25519_private_key_path:
            try:
                from regulatory_agent_kit.util.crypto import AuditSigner

                signer = AuditSigner.load_key(settings.ed25519_private_key_path)
                application.state.audit_signer = signer
                logger.info("Audit signer loaded")
            except Exception:
                logger.warning("Audit signer not available", exc_info=True)
    except Exception:
        logger.debug("Settings not loaded — running in test mode", exc_info=True)

    yield

    # --- shutdown ---
    if db_pool is not None:
        from regulatory_agent_kit.database.pool import close_pool

        await close_pool()
        logger.info("Database pool closed")


app = FastAPI(
    title="regulatory-agent-kit",
    description="AI-powered regulatory compliance automation API",
    version="0.1.0",
    lifespan=lifespan,
)

# --- middleware ---
app.add_middleware(RakAuthMiddleware)

# --- routes ---
app.include_router(events_router)
app.include_router(approvals_router)
app.include_router(runs_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
