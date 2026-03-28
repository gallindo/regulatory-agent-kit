"""End-to-end smoke test for Lite Mode pipeline.

Loads the example regulation plugin, creates a temporary fixture repo
with a Java file, runs LiteModeExecutor against it, and verifies the
pipeline completes with audit entries and populated results.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from regulatory_agent_kit.database.lite import (
    LiteAuditRepository,
    LiteCheckpointDecisionRepository,
    create_tables,
)
from regulatory_agent_kit.orchestration.lite import LITE_PHASES, LiteModeExecutor, LiteModeResult
from regulatory_agent_kit.plugins.loader import PluginLoader

# Path to the example regulation plugin (relative to project root).
_EXAMPLE_PLUGIN = Path(__file__).resolve().parents[2] / "regulations" / "examples" / "example.yaml"

_SAMPLE_JAVA = """\
package com.example.service;

public class PaymentService implements Service {

    public void processPayment(double amount) {
        // business logic
    }
}
"""


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """Create a minimal fixture repository with a Java source file."""
    repo_dir = tmp_path / "fixture-repo"
    repo_dir.mkdir()
    src_dir = repo_dir / "src" / "main" / "java" / "com" / "example" / "service"
    src_dir.mkdir(parents=True)
    (src_dir / "PaymentService.java").write_text(_SAMPLE_JAVA)
    return repo_dir


@pytest.fixture
def lite_db(tmp_path: Path) -> Path:
    """Return a temporary SQLite database path."""
    return tmp_path / "e2e_test.db"


@pytest.mark.integration
class TestE2ELiteMode:
    """End-to-end smoke tests for the Lite Mode pipeline."""

    async def test_plugin_loads_successfully(self) -> None:
        """The example plugin can be loaded and validated."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)
        assert plugin.id == "example-audit-logging-2025"
        assert len(plugin.rules) >= 1

    async def test_pipeline_completes(self, lite_db: Path, fixture_repo: Path) -> None:
        """Run the full pipeline and verify it completes."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        assert isinstance(result, LiteModeResult)
        assert result.status == "completed"
        assert result.run_id  # non-empty

    async def test_all_phases_executed(self, lite_db: Path, fixture_repo: Path) -> None:
        """All expected pipeline phases are executed in order."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        assert result.phases_executed == list(LITE_PHASES)

    async def test_audit_entries_created(self, lite_db: Path, fixture_repo: Path) -> None:
        """At least one audit entry is persisted after a pipeline run."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        audit_repo = LiteAuditRepository(lite_db)
        entries = await audit_repo.get_by_run(UUID(result.run_id))
        assert len(entries) >= 1
        assert entries[-1]["event_type"] == "state_transition"

    async def test_checkpoint_decisions_created(self, lite_db: Path, fixture_repo: Path) -> None:
        """Both impact_review and merge_review checkpoints are recorded."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        # Ensure tables are available for querying
        await create_tables(lite_db)
        checkpoint_repo = LiteCheckpointDecisionRepository(lite_db)
        decisions = await checkpoint_repo.get_by_run(UUID(result.run_id))

        types = {d["checkpoint_type"] for d in decisions}
        assert "impact_review" in types
        assert "merge_review" in types
        assert all(d["decision"] == "approved" for d in decisions)

    async def test_results_populated(self, lite_db: Path, fixture_repo: Path) -> None:
        """Cost estimate, repo results, and report are populated."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        # Cost estimate
        assert result.cost_estimate["estimated_total_cost"] > 0
        assert "per_repo_cost" in result.cost_estimate

        # Repo results
        assert len(result.repo_results) == 1
        repo = result.repo_results[0]
        assert "impact_map" in repo
        assert "change_set" in repo
        assert "test_result" in repo

        # Report
        assert "audit_log_path" in result.report
        assert "report_path" in result.report
