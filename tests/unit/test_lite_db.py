"""Unit tests for Lite Mode SQLite adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from uuid import uuid4

import pytest

from regulatory_agent_kit.database.lite import (
    LiteAuditRepository,
    LiteCheckpointDecisionRepository,
    LitePipelineRunRepository,
    LiteRepositoryProgressRepository,
    create_tables,
)


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with schema applied."""
    path = tmp_path / "test_lite.db"
    await create_tables(path)
    return path


class TestCreateTables:
    """Test that create_tables creates all required tables."""

    async def test_creates_pipeline_runs_table(self, db_path: Path) -> None:
        import aiosqlite

        async with (
            aiosqlite.connect(str(db_path)) as db,
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
            ) as cursor,
        ):
            row = await cursor.fetchone()
            assert row is not None

    async def test_creates_repository_progress_table(self, db_path: Path) -> None:
        import aiosqlite

        async with (
            aiosqlite.connect(str(db_path)) as db,
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='repository_progress'"
            ) as cursor,
        ):
            row = await cursor.fetchone()
            assert row is not None

    async def test_creates_audit_entries_table(self, db_path: Path) -> None:
        import aiosqlite

        async with (
            aiosqlite.connect(str(db_path)) as db,
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_entries'"
            ) as cursor,
        ):
            row = await cursor.fetchone()
            assert row is not None

    async def test_creates_checkpoint_decisions_table(self, db_path: Path) -> None:
        import aiosqlite

        async with (
            aiosqlite.connect(str(db_path)) as db,
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoint_decisions'"
            ) as cursor,
        ):
            row = await cursor.fetchone()
            assert row is not None


class TestLitePipelineRunRepository:
    """Test CRUD operations for LitePipelineRunRepository."""

    async def test_create_and_get(self, db_path: Path) -> None:
        repo = LitePipelineRunRepository(db_path)
        run_id = await repo.create(
            regulation_id="example-regulation-2025",
            total_repos=2,
            config_snapshot={"model": "test"},
        )
        row = await repo.get(run_id)
        assert row is not None
        assert row["regulation_id"] == "example-regulation-2025"
        assert row["status"] == "pending"

    async def test_update_status(self, db_path: Path) -> None:
        repo = LitePipelineRunRepository(db_path)
        run_id = await repo.create("example-plugin", 1, {})
        await repo.update_status(run_id, "running")
        row = await repo.get(run_id)
        assert row is not None
        assert row["status"] == "running"

    async def test_get_nonexistent_returns_none(self, db_path: Path) -> None:
        repo = LitePipelineRunRepository(db_path)
        result = await repo.get(uuid4())
        assert result is None


class TestLiteRepositoryProgressRepository:
    """Test CRUD operations for LiteRepositoryProgressRepository."""

    async def test_create_and_get_by_run(self, db_path: Path) -> None:
        pipeline_repo = LitePipelineRunRepository(db_path)
        run_id = await pipeline_repo.create("example-plugin", 1, {})

        repo = LiteRepositoryProgressRepository(db_path)
        entry_id = await repo.create(run_id, "https://github.com/example/repo")
        rows = await repo.get_by_run(run_id)
        assert len(rows) == 1
        assert rows[0]["repo_url"] == "https://github.com/example/repo"
        assert rows[0]["id"] == str(entry_id)

    async def test_update_status(self, db_path: Path) -> None:
        pipeline_repo = LitePipelineRunRepository(db_path)
        run_id = await pipeline_repo.create("example-plugin", 1, {})

        repo = LiteRepositoryProgressRepository(db_path)
        entry_id = await repo.create(run_id, "https://github.com/example/repo")
        await repo.update_status(entry_id, "completed")
        rows = await repo.get_by_run(run_id)
        assert rows[0]["status"] == "completed"


class TestLiteAuditRepository:
    """Test CRUD operations for LiteAuditRepository."""

    async def test_insert_and_get_by_run(self, db_path: Path) -> None:
        pipeline_repo = LitePipelineRunRepository(db_path)
        run_id = await pipeline_repo.create("example-plugin", 1, {})

        repo = LiteAuditRepository(db_path)
        entry_id = await repo.insert(
            run_id=run_id,
            event_type="state_transition",
            timestamp=datetime.now(UTC),
            payload={"phase": "ANALYZING"},
            signature="test-sig",
        )
        rows = await repo.get_by_run(run_id)
        assert len(rows) == 1
        assert rows[0]["entry_id"] == str(entry_id)
        assert rows[0]["event_type"] == "state_transition"


class TestLiteCheckpointDecisionRepository:
    """Test CRUD operations for LiteCheckpointDecisionRepository."""

    async def test_create_and_get_by_run(self, db_path: Path) -> None:
        pipeline_repo = LitePipelineRunRepository(db_path)
        run_id = await pipeline_repo.create("example-plugin", 1, {})

        repo = LiteCheckpointDecisionRepository(db_path)
        decision_id = await repo.create(
            run_id=run_id,
            checkpoint_type="impact_review",
            actor="test-user",
            decision="approved",
            signature="sig",
            rationale="Looks good",
        )
        rows = await repo.get_by_run(run_id)
        assert len(rows) == 1
        assert rows[0]["id"] == str(decision_id)
        assert rows[0]["decision"] == "approved"

    async def test_get_latest(self, db_path: Path) -> None:
        pipeline_repo = LitePipelineRunRepository(db_path)
        run_id = await pipeline_repo.create("example-plugin", 1, {})

        repo = LiteCheckpointDecisionRepository(db_path)
        await repo.create(
            run_id=run_id,
            checkpoint_type="impact_review",
            actor="user1",
            decision="rejected",
            signature="sig1",
        )
        await repo.create(
            run_id=run_id,
            checkpoint_type="impact_review",
            actor="user2",
            decision="approved",
            signature="sig2",
        )
        latest = await repo.get_latest(run_id, "impact_review")
        assert latest is not None
        assert latest["decision"] == "approved"

    async def test_get_latest_nonexistent_returns_none(self, db_path: Path) -> None:
        repo = LiteCheckpointDecisionRepository(db_path)
        result = await repo.get_latest(uuid4(), "merge_review")
        assert result is None
