"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager

from fastapi import FastAPI

from regulatory_agent_kit.api.middleware import RakAuthMiddleware
from regulatory_agent_kit.api.routes.approvals import router as approvals_router
from regulatory_agent_kit.api.routes.events import router as events_router
from regulatory_agent_kit.api.routes.runs import router as runs_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle.

    In production this would initialise the database pool, Temporal
    client, audit signer, and settings on ``app.state``.  For now it
    is a no-op placeholder that keeps the wiring in place.
    """
    # --- startup ---
    # application.state.db_pool = ...
    # application.state.temporal_client = ...
    # application.state.audit_signer = ...
    # application.state.settings = ...
    yield
    # --- shutdown ---
    # await application.state.db_pool.close()


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
