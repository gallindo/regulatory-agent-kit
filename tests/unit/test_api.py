"""Unit tests for the FastAPI application (Phase 12)."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from regulatory_agent_kit.api.main import app
from regulatory_agent_kit.api.routes.approvals import clear_runs as clear_approval_runs
from regulatory_agent_kit.api.routes.approvals import register_run
from regulatory_agent_kit.api.routes.runs import (
    clear_runs as clear_pipeline_runs,
)
from regulatory_agent_kit.api.routes.runs import seed_run
from regulatory_agent_kit.models.pipeline import PipelineStatus


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    """Clear in-memory stores before each test."""
    clear_approval_runs()
    clear_pipeline_runs()


# ---------------------------------------------------------------------------
# Transport helper
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> httpx.AsyncClient:
    """Async test client wired to the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /events
# ---------------------------------------------------------------------------


async def test_post_event_valid_returns_202(client: httpx.AsyncClient) -> None:
    payload = {
        "regulation_id": "dora-ict-risk-2025",
        "change_type": "new_requirement",
        "source": "webhook",
    }
    resp = await client.post("/events", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert "workflow_id" in body
    assert body["workflow_id"].startswith("rak-pipeline-")
    assert "event_id" in body


async def test_post_event_invalid_returns_422(client: httpx.AsyncClient) -> None:
    resp = await client.post("/events", json={})
    assert resp.status_code == 422


async def test_post_event_bad_change_type_returns_422(client: httpx.AsyncClient) -> None:
    payload = {
        "regulation_id": "dora-ict-risk-2025",
        "change_type": "invalid_type",
        "source": "webhook",
    }
    resp = await client.post("/events", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /approvals/{run_id}
# ---------------------------------------------------------------------------


async def test_post_approval_valid_returns_200(client: httpx.AsyncClient) -> None:
    run_id = uuid4()
    register_run(run_id)
    decision = {
        "checkpoint_type": "impact_review",
        "actor": "alice@example.com",
        "decision": "approved",
    }
    resp = await client.post(f"/approvals/{run_id}", json=decision)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == str(run_id)
    assert body["status"] == "recorded"


async def test_post_approval_unknown_run_returns_404(client: httpx.AsyncClient) -> None:
    unknown_id = uuid4()
    decision = {
        "checkpoint_type": "merge_review",
        "actor": "bob@example.com",
        "decision": "rejected",
    }
    resp = await client.post(f"/approvals/{unknown_id}", json=decision)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /runs/{run_id}
# ---------------------------------------------------------------------------


async def test_get_run_returns_200(client: httpx.AsyncClient) -> None:
    run_id = uuid4()
    run = PipelineStatus(run_id=run_id, status="running", phase="ANALYZING")
    seed_run(run)
    resp = await client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["phase"] == "ANALYZING"


async def test_get_run_unknown_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.get(f"/runs/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /runs
# ---------------------------------------------------------------------------


async def test_list_runs_empty(client: httpx.AsyncClient) -> None:
    resp = await client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_runs_with_status_filter(client: httpx.AsyncClient) -> None:
    run_a = PipelineStatus(run_id=uuid4(), status="running", phase="ANALYZING")
    run_b = PipelineStatus(run_id=uuid4(), status="completed", phase="DONE")
    seed_run(run_a)
    seed_run(run_b)

    resp = await client.get("/runs", params={"status_filter": "running"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "running"


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_TEST_TOKEN = "test-tok-" + "abc123"


def _make_auth_app() -> FastAPI:
    """Create a standalone FastAPI app with bearer auth middleware for auth tests."""
    from regulatory_agent_kit.api.middleware import RakAuthMiddleware
    from regulatory_agent_kit.api.routes.runs import router as runs_router_local

    auth_app = FastAPI()
    auth_app.add_middleware(RakAuthMiddleware)
    auth_app.state.api_token = _TEST_TOKEN
    auth_app.include_router(runs_router_local)

    @auth_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return auth_app


async def test_auth_middleware_rejects_missing_token() -> None:
    """When api_token is set, requests without Authorization are rejected."""
    auth_app = _make_auth_app()
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get("/runs")
        assert resp.status_code == 401


async def test_auth_middleware_rejects_wrong_token() -> None:
    """When api_token is set, requests with the wrong token get 403."""
    auth_app = _make_auth_app()
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get(
            "/runs",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403


async def test_auth_middleware_allows_valid_token() -> None:
    """When api_token is set, requests with the correct token succeed."""
    auth_app = _make_auth_app()
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get(
            "/runs",
            headers={"Authorization": f"Bearer {_TEST_TOKEN}"},
        )
        assert resp.status_code == 200


async def test_health_bypasses_auth() -> None:
    """The /health endpoint is accessible even with auth enabled."""
    auth_app = _make_auth_app()
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
