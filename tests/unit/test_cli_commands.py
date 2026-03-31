"""Tests for CLI commands: cancel, retry-failures, and resume."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from regulatory_agent_kit.cli import app

runner = CliRunner()

VALID_UUID = str(uuid.uuid4())


# ======================================================================
# Helpers
# ======================================================================


async def _create_test_run(
    db_path: Path,
    run_id: str,
    status: str = "running",
    regulation_id: str = "test-reg",
    config_snapshot: dict | None = None,
) -> None:
    """Insert a pipeline run into the test database."""
    from regulatory_agent_kit.database.lite import LitePipelineRunRepository, create_tables

    await create_tables(db_path)
    LitePipelineRunRepository(db_path)
    # Insert with known run_id
    import aiosqlite

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            """
            INSERT INTO pipeline_runs
                (run_id, regulation_id, status, total_repos, config_snapshot)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                regulation_id,
                status,
                2,
                json.dumps(config_snapshot or {}),
            ),
        )
        await db.commit()


async def _create_test_progress(
    db_path: Path,
    run_id: str,
    repo_url: str,
    status: str = "pending",
    error: str = "",
) -> None:
    """Insert a repository progress entry into the test database."""
    import aiosqlite

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            """
            INSERT INTO repository_progress (id, run_id, repo_url, status, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), run_id, repo_url, status, error),
        )
        await db.commit()


# ======================================================================
# rak cancel
# ======================================================================


class TestCancelCommand:
    def test_cancel_not_found(self) -> None:
        result = runner.invoke(app, ["cancel", "--run-id", VALID_UUID])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_cancel_invalid_uuid(self) -> None:
        result = runner.invoke(app, ["cancel", "--run-id", "not-a-uuid"])
        assert result.exit_code != 0

    def test_cancel_updates_status(self, tmp_path: Path) -> None:
        """Cancel should update SQLite status to cancelled."""
        import asyncio

        from regulatory_agent_kit.database.lite import LitePipelineRunRepository

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        asyncio.run(_create_test_run(db_path, run_id, status="running"))

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["cancel", "--run-id", run_id])

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

        # Verify status in DB
        run_data = asyncio.run(LitePipelineRunRepository(db_path).get(uuid.UUID(run_id)))
        assert run_data is not None
        assert run_data["status"] == "cancelled"

    def test_cancel_already_terminal(self, tmp_path: Path) -> None:
        """Cancel should report already terminal for completed runs."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        asyncio.run(_create_test_run(db_path, run_id, status="completed"))

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["cancel", "--run-id", run_id])

        assert result.exit_code == 0
        assert "terminal" in result.output.lower()


# ======================================================================
# rak retry-failures
# ======================================================================


class TestRetryFailuresCommand:
    def test_retry_failures_not_found(self) -> None:
        result = runner.invoke(app, ["retry-failures", "--run-id", VALID_UUID])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_retry_failures_no_failed_repos(self, tmp_path: Path) -> None:
        """Should report no failures when all repos completed."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        asyncio.run(_create_test_run(db_path, run_id, status="completed"))
        asyncio.run(
            _create_test_progress(db_path, run_id, "https://github.com/a/b", "completed")
        )

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["retry-failures", "--run-id", run_id])

        assert result.exit_code == 0
        assert "no failed" in result.output.lower()

    def test_retry_failures_redispatches(self, tmp_path: Path) -> None:
        """Should re-dispatch failed repos through executor."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        config = {"default_model": "test-model", "plugin_data": {}}
        asyncio.run(
            _create_test_run(
                db_path, run_id, status="failed", config_snapshot=config
            )
        )
        asyncio.run(
            _create_test_progress(
                db_path, run_id, "https://github.com/a/repo1", "failed", "timeout"
            )
        )
        asyncio.run(
            _create_test_progress(
                db_path, run_id, "https://github.com/a/repo2", "completed"
            )
        )

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["retry-failures", "--run-id", run_id])

        assert result.exit_code == 0
        assert "re-dispatching" in result.output.lower()
        assert "1" in result.output  # 1 failed repo
        assert "new run id" in result.output.lower()


# ======================================================================
# rak resume
# ======================================================================


class TestResumeCommand:
    def test_resume_not_found(self) -> None:
        result = runner.invoke(app, ["resume", "--run-id", VALID_UUID])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_resume_terminal_state(self, tmp_path: Path) -> None:
        """Should refuse to resume a completed run."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        asyncio.run(_create_test_run(db_path, run_id, status="completed"))

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["resume", "--run-id", run_id])

        assert result.exit_code == 1
        assert "cannot resume" in result.output.lower()

    def test_resume_with_no_pending_repos(self, tmp_path: Path) -> None:
        """Should report completed if all repos are in terminal state."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        config = {"default_model": "test-model", "plugin_data": {}}
        asyncio.run(_create_test_run(db_path, run_id, status="running", config_snapshot=config))
        asyncio.run(
            _create_test_progress(db_path, run_id, "https://github.com/a/b", "completed")
        )

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["resume", "--run-id", run_id])

        assert result.exit_code == 0
        assert "completed" in result.output.lower()
        assert "wal entries replayed" in result.output.lower()

    def test_resume_with_pending_repos(self, tmp_path: Path) -> None:
        """Should re-run pending repos through the executor."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        config = {"default_model": "test-model", "plugin_data": {}}
        asyncio.run(_create_test_run(db_path, run_id, status="running", config_snapshot=config))
        asyncio.run(
            _create_test_progress(db_path, run_id, "https://github.com/a/repo1", "pending")
        )

        with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
            result = runner.invoke(app, ["resume", "--run-id", run_id])

        assert result.exit_code == 0
        assert "resumed run" in result.output.lower()
        assert "final status" in result.output.lower()

    def test_resume_with_wal_replay(self, tmp_path: Path) -> None:
        """Should replay WAL entries before resuming."""
        import asyncio

        db_path = tmp_path / "test.db"
        run_id = str(uuid.uuid4())
        config = {"default_model": "test-model", "plugin_data": {}}
        asyncio.run(_create_test_run(db_path, run_id, status="running", config_snapshot=config))
        asyncio.run(
            _create_test_progress(db_path, run_id, "https://github.com/a/repo1", "completed")
        )

        # Create a WAL file with an entry
        wal_dir = tmp_path / "wal"
        wal_dir.mkdir(parents=True)
        wal_path = wal_dir / f"wal-{run_id}.jsonl"
        entry = {
            "run_id": run_id,
            "event_type": "state_transition",
            "timestamp": "2026-01-01T00:00:00",
            "payload": {"phase": "TESTING"},
            "signature": "",
        }
        wal_path.write_text(json.dumps(entry) + "\n")

        with (
            patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path),
            patch(
                "regulatory_agent_kit.cli.Path.home",
                return_value=tmp_path,
            ),
            patch("regulatory_agent_kit.observability.wal.Path"),
        ):
            pass

        # Simpler approach: just set up WAL at the expected path
        wal_home_dir = Path.home() / ".rak"
        wal_home_dir.mkdir(parents=True, exist_ok=True)
        wal_file = wal_home_dir / f"wal-{run_id}.jsonl"
        wal_file.write_text(json.dumps(entry) + "\n")

        try:
            with patch("regulatory_agent_kit.cli._LITE_DB_PATH", db_path):
                result = runner.invoke(app, ["resume", "--run-id", run_id])

            assert result.exit_code == 0
            assert "wal entries replayed" in result.output.lower()
            assert "1" in result.output  # 1 WAL entry replayed
        finally:
            # Clean up WAL file
            if wal_file.exists():
                wal_file.unlink()
