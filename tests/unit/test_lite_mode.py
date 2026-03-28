"""Unit tests for Lite Mode sequential executor."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from regulatory_agent_kit.orchestration.lite import LITE_PHASES, LiteModeExecutor, LiteModeResult


@pytest.fixture
def lite_db(tmp_path: Path) -> Path:
    """Return a temporary database path for the Lite Mode executor."""
    return tmp_path / "lite_test.db"


class TestLiteModeExecutor:
    """Test that LiteModeExecutor runs pipeline phases in order."""

    async def test_run_completes_successfully(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id="dora-ict-risk-2025",
            repo_urls=["https://github.com/example/repo1"],
            plugin_data={"id": "dora-ict-risk-2025"},
        )
        assert result.status == "completed"
        assert isinstance(result, LiteModeResult)

    async def test_all_phases_executed_in_order(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id="dora-ict-risk-2025",
            repo_urls=["https://github.com/example/repo1"],
            plugin_data={},
        )
        assert result.phases_executed == list(LITE_PHASES)

    async def test_cost_estimate_populated(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id="test-reg",
            repo_urls=["https://github.com/a/b", "https://github.com/c/d"],
            plugin_data={},
        )
        assert result.cost_estimate["estimated_total_cost"] == 3.0
        assert len(result.cost_estimate["per_repo_cost"]) == 2

    async def test_repo_results_populated(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id="test-reg",
            repo_urls=["https://github.com/a/b"],
            plugin_data={},
        )
        assert len(result.repo_results) == 1
        repo = result.repo_results[0]
        assert repo["repo_url"] == "https://github.com/a/b"
        assert "impact_map" in repo
        assert "change_set" in repo
        assert "test_result" in repo

    async def test_report_populated(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id="test-reg",
            repo_urls=["https://github.com/a/b"],
            plugin_data={},
        )
        assert "audit_log_path" in result.report
        assert "report_path" in result.report
        assert "rollback_manifest_path" in result.report

    async def test_multiple_repos_processed_sequentially(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        repos = [
            "https://github.com/org/repo1",
            "https://github.com/org/repo2",
            "https://github.com/org/repo3",
        ]
        result = await executor.run(
            regulation_id="test-reg",
            repo_urls=repos,
            plugin_data={},
        )
        assert len(result.repo_results) == 3
        assert result.status == "completed"

    async def test_run_id_is_set(self, lite_db: Path) -> None:
        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id="test-reg",
            repo_urls=["https://github.com/a/b"],
            plugin_data={},
        )
        assert result.run_id != ""
        # Should be a valid UUID format
        assert len(result.run_id) == 36
