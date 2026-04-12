"""E2E tests for the FastAPI application."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from regulatory_agent_kit.api.main import app
from regulatory_agent_kit.api.routes.approvals import (
    clear_runs as clear_approval_runs,
)
from regulatory_agent_kit.api.routes.approvals import (
    register_run,
)
from regulatory_agent_kit.api.routes.runs import (
    clear_runs as clear_status_runs,
)
from regulatory_agent_kit.api.routes.runs import (
    seed_run,
)
from regulatory_agent_kit.models.pipeline import PipelineStatus


@pytest.mark.integration
class TestE2EAPI:
    """End-to-end tests for the FastAPI application routes and middleware."""

    async def test_event_to_approval_flow(self) -> None:
        """POST /events -> register run -> POST /approvals/{id} -> 200."""
        try:
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # Submit a regulatory event
                event_payload = {
                    "regulation_id": "example-regulation-2025",
                    "change_type": "new_requirement",
                    "source": "webhook",
                    "payload": {},
                }
                resp = await client.post("/events", json=event_payload)
                assert resp.status_code == 202
                data = resp.json()
                assert "workflow_id" in data
                assert "event_id" in data

                # Register a run_id for approval, then submit an approval
                run_id = uuid4()
                register_run(run_id)

                decision_payload = {
                    "checkpoint_type": "impact_review",
                    "actor": "test@example.com",
                    "decision": "approved",
                }
                resp = await client.post(f"/approvals/{run_id}", json=decision_payload)
                assert resp.status_code == 200
                ack = resp.json()
                assert ack["run_id"] == str(run_id)
                assert ack["status"] == "recorded"
        finally:
            clear_approval_runs()
            clear_status_runs()

    async def test_list_runs_with_status_filter(self) -> None:
        """Seed multiple runs, filter by status."""
        try:
            run_running = PipelineStatus(run_id=uuid4(), status="running", phase="ANALYZING")
            run_completed = PipelineStatus(run_id=uuid4(), status="completed", phase="DONE")
            seed_run(run_running)
            seed_run(run_completed)

            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # Filter by running
                resp = await client.get("/runs", params={"status_filter": "running"})
                assert resp.status_code == 200
                runs = resp.json()
                assert len(runs) == 1
                assert runs[0]["status"] == "running"

                # Filter by completed
                resp = await client.get("/runs", params={"status_filter": "completed"})
                assert resp.status_code == 200
                runs = resp.json()
                assert len(runs) == 1
                assert runs[0]["status"] == "completed"

                # No filter returns all
                resp = await client.get("/runs")
                assert resp.status_code == 200
                assert len(resp.json()) == 2
        finally:
            clear_status_runs()
            clear_approval_runs()

    async def test_auth_middleware_blocks_unauthenticated(self) -> None:
        """When api_token is set, missing Authorization -> 401."""
        try:
            app.state.api_token = "secret-test-token"  # noqa: S105
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/runs")
                assert resp.status_code == 401
                assert "Authorization" in resp.json()["detail"]
        finally:
            app.state.api_token = None
            clear_status_runs()
            clear_approval_runs()

    async def test_auth_middleware_allows_health(self) -> None:
        """Health endpoint bypasses auth even when token is configured."""
        try:
            app.state.api_token = "secret-test-token"  # noqa: S105
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")
                assert resp.status_code == 200
                assert resp.json() == {"status": "ok"}
        finally:
            app.state.api_token = None
            clear_status_runs()
            clear_approval_runs()

    async def test_invalid_event_returns_422(self) -> None:
        """POST /events with missing regulation_id -> 422."""
        try:
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # Missing required fields
                resp = await client.post("/events", json={"payload": {}})
                assert resp.status_code == 422
        finally:
            clear_status_runs()
            clear_approval_runs()

    async def test_approval_for_unknown_run_returns_404(self) -> None:
        """POST /approvals/{random_uuid} -> 404."""
        try:
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                random_id = uuid4()
                decision_payload = {
                    "checkpoint_type": "merge_review",
                    "actor": "admin@example.com",
                    "decision": "rejected",
                }
                resp = await client.post(f"/approvals/{random_id}", json=decision_payload)
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()
        finally:
            clear_status_runs()
            clear_approval_runs()
