"""E2E tests against the full Docker Compose stack.

These tests are skipped unless the RAK_E2E_DOCKER=1 environment variable
is set, indicating the Docker Compose stack is running.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RAK_E2E_DOCKER") != "1",
        reason="Docker Compose stack not running (set RAK_E2E_DOCKER=1)",
    ),
]

# Base URL for the RAK API running in Docker Compose.
_API_BASE = "http://localhost:8000"

# PostgreSQL connection string for the Docker Compose database.
_PG_DSN = "postgresql://rak:rak@localhost:5432/rak"


class TestE2EDockerCompose:
    """End-to-end tests that exercise the full Docker Compose stack."""

    async def test_submit_event_via_api(self) -> None:
        """POST /events to the running API returns 202."""
        # httpx.AsyncClient to POST http://localhost:8000/events
        # payload = {"regulation_id": "example-audit-logging-2025", ...}
        # async with httpx.AsyncClient(base_url=_API_BASE) as client:
        #     resp = await client.post("/events", json=payload)
        # assert resp.status_code == 202
        # assert "run_id" in resp.json()
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_health_endpoint(self) -> None:
        """GET /health returns 200."""
        # async with httpx.AsyncClient(base_url=_API_BASE) as client:
        #     resp = await client.get("/health")
        # assert resp.status_code == 200
        # assert resp.json()["status"] == "ok"
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_pipeline_reaches_awaiting_review(self) -> None:
        """Submit event -> poll status -> reaches AWAITING_IMPACT_REVIEW."""
        # 1. POST /events to create a pipeline run
        # 2. Poll GET /runs/{run_id} in a loop (max 60s, 2s interval)
        # 3. Assert status transitions through:
        #    INITIALIZING -> ANALYZING -> AWAITING_IMPACT_REVIEW
        # assert run_status["phase"] == "AWAITING_IMPACT_REVIEW"
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_approval_resumes_pipeline(self) -> None:
        """Submit event -> approve -> verify pipeline proceeds."""
        # 1. POST /events -> get run_id
        # 2. Poll until AWAITING_IMPACT_REVIEW
        # 3. POST /runs/{run_id}/approve with decision="approved"
        # 4. Poll until next phase (REFACTORING or AWAITING_MERGE_REVIEW)
        # assert run_status["phase"] != "AWAITING_IMPACT_REVIEW"
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_rejection_terminates_pipeline(self) -> None:
        """Submit event -> reject -> verify status=rejected."""
        # 1. POST /events -> get run_id
        # 2. Poll until AWAITING_IMPACT_REVIEW
        # 3. POST /runs/{run_id}/approve with decision="rejected"
        # 4. Poll until terminal state
        # assert run_status["status"] == "rejected"
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_audit_entries_in_postgresql(self) -> None:
        """After pipeline, query audit_entries via API or DB."""
        # 1. Run a pipeline to completion (or at least past first phase)
        # 2. Connect to PostgreSQL via psycopg AsyncConnection
        # 3. SELECT * FROM rak.audit_entries WHERE run_id = %s
        # assert len(rows) >= 1
        # assert all(row["signature"] is not None for row in rows)
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_checkpoint_decisions_in_postgresql(self) -> None:
        """Verify checkpoint_decisions table has records."""
        # 1. Run a pipeline through at least one checkpoint
        # 2. SELECT * FROM rak.checkpoint_decisions WHERE run_id = %s
        # assert len(rows) >= 1
        # assert rows[0]["checkpoint_type"] in ("impact_review", "merge_review")
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_cancel_running_pipeline(self) -> None:
        """Cancel a pipeline mid-execution."""
        # 1. POST /events -> get run_id
        # 2. Immediately POST /runs/{run_id}/cancel
        # 3. Poll until terminal state
        # assert run_status["status"] == "cancelled"
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_multiple_concurrent_pipelines(self) -> None:
        """Submit 2 events -> both run independently."""
        # 1. POST /events twice with different regulation configs
        # 2. Collect both run_ids
        # 3. Poll both until they reach a non-initial phase
        # assert run1["run_id"] != run2["run_id"]
        # assert run1["status"] in ("running", "completed")
        # assert run2["status"] in ("running", "completed")
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_alembic_migration_applied(self) -> None:
        """Verify all 6 tables exist in rak schema."""
        # Connect to PostgreSQL and query information_schema.tables
        # expected_tables = {
        #     "pipeline_runs", "repository_progress", "audit_entries",
        #     "checkpoint_decisions", "alembic_version", "regulation_plugins",
        # }
        # async with await psycopg.AsyncConnection.connect(_PG_DSN) as conn:
        #     rows = await conn.execute(
        #         "SELECT table_name FROM information_schema.tables "
        #         "WHERE table_schema = 'rak'"
        #     )
        #     actual = {r[0] for r in await rows.fetchall()}
        # assert expected_tables.issubset(actual)
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_audit_entries_partitioned(self) -> None:
        """Verify audit_entries has partition children."""
        # Query pg_catalog.pg_inherits to confirm partitioning
        # async with await psycopg.AsyncConnection.connect(_PG_DSN) as conn:
        #     rows = await conn.execute(
        #         "SELECT inhrelid::regclass FROM pg_catalog.pg_inherits "
        #         "WHERE inhparent = 'rak.audit_entries'::regclass"
        #     )
        #     partitions = await rows.fetchall()
        # assert len(partitions) >= 1, "audit_entries should be partitioned"
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")

    async def test_rak_app_role_audit_restriction(self) -> None:
        """rak_app role cannot UPDATE/DELETE audit_entries."""
        # Connect as rak_app user and attempt forbidden operations
        # rak_app_dsn = "postgresql://rak_app:rak_app@localhost:5432/rak"
        # async with await psycopg.AsyncConnection.connect(rak_app_dsn) as conn:
        #     with pytest.raises(psycopg.errors.InsufficientPrivilege):
        #         await conn.execute(
        #             "UPDATE rak.audit_entries SET event_type = 'hacked' "
        #             "WHERE TRUE"
        #         )
        #     with pytest.raises(psycopg.errors.InsufficientPrivilege):
        #         await conn.execute(
        #             "DELETE FROM rak.audit_entries WHERE TRUE"
        #         )
        pytest.skip("Requires running Docker Compose stack -- implement when infra is available")
