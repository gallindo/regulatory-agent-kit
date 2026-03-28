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
    LiteRepositoryProgressRepository,
    create_tables,
)
from regulatory_agent_kit.orchestration.lite import LITE_PHASES, LiteModeExecutor, LiteModeResult
from regulatory_agent_kit.plugins.loader import PluginLoader
from tests.helpers import EXAMPLE_PLUGIN_PATH as _EXAMPLE_PLUGIN


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

    async def test_pipeline_with_multiple_repos(
        self, lite_db: Path, fixture_repo: Path, tmp_path: Path
    ) -> None:
        """Multiple repos each get separate progress entries and results."""
        repos: list[Path] = []
        for i in range(3):
            repo_dir = tmp_path / f"repo-{i}"
            repo_dir.mkdir()
            src_dir = repo_dir / "src"
            src_dir.mkdir()
            (src_dir / "Main.java").write_text(f"// repo {i}\n")
            repos.append(repo_dir)

        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(r) for r in repos],
            plugin_data=plugin.model_dump(),
        )

        assert result.status == "completed"
        assert len(result.repo_results) == 3
        for repo in result.repo_results:
            assert "impact_map" in repo
            assert "change_set" in repo
            assert "test_result" in repo

    async def test_pipeline_with_empty_repo_list(self, lite_db: Path) -> None:
        """Graceful handling when repo_urls=[]."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[],
            plugin_data=plugin.model_dump(),
        )

        assert result.status == "completed"
        assert result.repo_results == []

    async def test_pipeline_with_python_fixture(self, lite_db: Path, tmp_path: Path) -> None:
        """Pipeline works with .py fixture files (language-agnostic)."""
        repo_dir = tmp_path / "py-repo"
        repo_dir.mkdir()
        (repo_dir / "app.py").write_text("def main() -> None:\n    pass\n")

        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(repo_dir)],
            plugin_data=plugin.model_dump(),
        )

        assert result.status == "completed"
        assert len(result.repo_results) == 1

    async def test_pipeline_config_overrides(self, lite_db: Path, fixture_repo: Path) -> None:
        """Custom config propagates to cost estimate."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
            config={"default_model": "gpt-4o"},
        )

        assert result.cost_estimate["model_used"] == "gpt-4o"

    async def test_audit_entries_include_state_transition(
        self, lite_db: Path, fixture_repo: Path
    ) -> None:
        """Audit trail contains state_transition events."""
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
        event_types = {e["event_type"] for e in entries}
        assert "state_transition" in event_types

    async def test_pipeline_run_persisted_in_db(self, lite_db: Path, fixture_repo: Path) -> None:
        """Pipeline run record exists in SQLite after completion."""
        import aiosqlite

        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        # The executor persists a pipeline_runs row via the repository.
        # Note: the repository's create() generates its own run_id, so we
        # query by regulation_id to locate the persisted row.
        async with aiosqlite.connect(str(lite_db)) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM pipeline_runs WHERE regulation_id = ?",
                (plugin.id,),
            ) as cursor:
                row = await cursor.fetchone()

        assert row is not None
        assert row["regulation_id"] == plugin.id
        assert result.status == "completed"

    async def test_repo_progress_created_for_each_repo(
        self, lite_db: Path, fixture_repo: Path
    ) -> None:
        """Each repo has a progress entry in the database."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        progress_repo = LiteRepositoryProgressRepository(lite_db)
        entries = await progress_repo.get_by_run(UUID(result.run_id))
        assert len(entries) == 1
        assert entries[0]["repo_url"] == str(fixture_repo)

    async def test_idempotent_rerun(self, lite_db: Path, fixture_repo: Path) -> None:
        """Two runs produce different run_ids and independent state."""
        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result1 = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )
        result2 = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(fixture_repo)],
            plugin_data=plugin.model_dump(),
        )

        assert result1.run_id != result2.run_id
        assert result1.status == "completed"
        assert result2.status == "completed"

    async def test_cost_estimate_scales_with_repos(self, lite_db: Path, tmp_path: Path) -> None:
        """Cost estimate total equals $1.50 per repo."""
        repos: list[Path] = []
        for i in range(4):
            repo_dir = tmp_path / f"cost-repo-{i}"
            repo_dir.mkdir()
            (repo_dir / "App.java").write_text(f"// {i}\n")
            repos.append(repo_dir)

        loader = PluginLoader()
        plugin = loader.load(_EXAMPLE_PLUGIN)

        executor = LiteModeExecutor(db_path=lite_db)
        result = await executor.run(
            regulation_id=plugin.id,
            repo_urls=[str(r) for r in repos],
            plugin_data=plugin.model_dump(),
        )

        assert result.cost_estimate["estimated_total_cost"] == 6.0
