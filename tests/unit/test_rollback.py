"""Tests for the rollback executor and manifest handling."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Any
from unittest.mock import AsyncMock, patch

from regulatory_agent_kit.tools.rollback import (
    RollbackExecutor,
    determine_action,
    format_rollback_summary,
    load_manifest_from_file,
    plan_rollback,
)

# ------------------------------------------------------------------
# Manifest fixtures
# ------------------------------------------------------------------


def _manifest(pr_states: list[str] | None = None) -> dict[str, Any]:
    """Build a sample rollback manifest with given PR states."""
    states = pr_states or ["open", "merged", "closed"]
    return {
        "run_id": "test-run-id",
        "repos": [
            {
                "repo_url": f"https://github.com/org/service-{i}",
                "branch_name": f"rak/regulation/rule-{i}",
                "commit_sha": f"sha{i}",
                "pr_url": f"https://github.com/org/service-{i}/pull/{i + 1}",
                "pr_state": state,
                "files_changed": [f"src/file{i}.py"],
            }
            for i, state in enumerate(states)
        ],
    }


# ------------------------------------------------------------------
# determine_action
# ------------------------------------------------------------------


class TestDetermineAction:
    def test_open_pr_closes_and_deletes(self) -> None:
        action = determine_action({"pr_state": "open", "repo_url": "r", "branch_name": "b"})
        assert action.action == "close_pr_and_delete_branch"

    def test_merged_pr_creates_revert(self) -> None:
        action = determine_action({"pr_state": "merged", "repo_url": "r"})
        assert action.action == "create_revert_pr"

    def test_closed_pr_skips(self) -> None:
        action = determine_action({"pr_state": "closed", "repo_url": "r"})
        assert action.action == "skip"

    def test_unknown_state_deletes_branch(self) -> None:
        action = determine_action({"pr_state": "unknown", "repo_url": "r", "branch_name": "b"})
        assert action.action == "delete_branch"

    def test_missing_state_deletes_branch(self) -> None:
        action = determine_action({"repo_url": "r", "branch_name": "b"})
        assert action.action == "delete_branch"

    def test_preserves_repo_fields(self) -> None:
        entry = {
            "repo_url": "https://github.com/org/svc",
            "branch_name": "rak/fix",
            "pr_url": "https://github.com/org/svc/pull/1",
            "pr_state": "open",
            "files_changed": ["a.py", "b.py"],
        }
        action = determine_action(entry)
        assert action.repo_url == "https://github.com/org/svc"
        assert action.branch_name == "rak/fix"
        assert action.files_changed == ["a.py", "b.py"]


# ------------------------------------------------------------------
# plan_rollback
# ------------------------------------------------------------------


class TestPlanRollback:
    def test_plans_actions_for_all_repos(self) -> None:
        manifest = _manifest(["open", "merged", "closed"])
        actions = plan_rollback(manifest)
        assert len(actions) == 3
        assert actions[0].action == "close_pr_and_delete_branch"
        assert actions[1].action == "create_revert_pr"
        assert actions[2].action == "skip"

    def test_empty_manifest(self) -> None:
        actions = plan_rollback({"run_id": "x", "repos": []})
        assert actions == []


# ------------------------------------------------------------------
# load_manifest_from_file
# ------------------------------------------------------------------


class TestLoadManifestFromFile:
    def test_loads_json_file(self, tmp_path: Path) -> None:
        manifest = _manifest(["open"])
        path = tmp_path / "rollback-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        loaded = load_manifest_from_file(path)
        assert loaded is not None
        assert loaded["run_id"] == "test-run-id"
        assert len(loaded["repos"]) == 1

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        result = load_manifest_from_file(tmp_path / "nonexistent.json")
        assert result is None


# ------------------------------------------------------------------
# RollbackExecutor — dry run
# ------------------------------------------------------------------


class TestRollbackExecutorDryRun:
    async def test_dry_run_returns_all_success(self) -> None:
        actions = plan_rollback(_manifest(["open", "merged", "closed"]))
        executor = RollbackExecutor()
        results = await executor.execute(actions, dry_run=True)
        assert len(results) == 3
        assert all(r.success for r in results)

    async def test_dry_run_labels_actions(self) -> None:
        actions = plan_rollback(_manifest(["open"]))
        executor = RollbackExecutor()
        results = await executor.execute(actions, dry_run=True)
        assert "[DRY RUN]" in results[0].detail
        assert "close PR" in results[0].detail

    async def test_skip_action_succeeds(self) -> None:
        actions = plan_rollback(_manifest(["closed"]))
        executor = RollbackExecutor()
        results = await executor.execute(actions, dry_run=False)
        assert results[0].success
        assert results[0].action == "skip"


# ------------------------------------------------------------------
# RollbackExecutor — execution (no token)
# ------------------------------------------------------------------


class TestRollbackExecutorNoToken:
    async def test_close_pr_without_token_fails(self) -> None:
        actions = plan_rollback(_manifest(["open"]))
        executor = RollbackExecutor(git_token="")
        results = await executor.execute(actions, dry_run=False)
        assert not results[0].success
        assert "token required" in results[0].error.lower()

    async def test_revert_pr_without_token_fails(self) -> None:
        actions = plan_rollback(_manifest(["merged"]))
        executor = RollbackExecutor(git_token="")
        results = await executor.execute(actions, dry_run=False)
        assert not results[0].success
        assert "token required" in results[0].error.lower()

    async def test_delete_branch_succeeds_without_token(self) -> None:
        actions = plan_rollback(_manifest(["unknown"]))
        executor = RollbackExecutor()
        results = await executor.execute(actions, dry_run=False)
        assert results[0].success
        assert "marked for deletion" in results[0].detail


# ------------------------------------------------------------------
# RollbackExecutor — execution (with mocked provider)
# ------------------------------------------------------------------


class TestRollbackExecutorWithProvider:
    async def test_close_pr_calls_add_comment(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.add_comment = AsyncMock(return_value={})

        with patch(
            "regulatory_agent_kit.tools.git_provider.create_git_provider",
            return_value=mock_provider,
        ):
            actions = plan_rollback(_manifest(["open"]))
            executor = RollbackExecutor(git_token="test-token")  # noqa: S106
            results = await executor.execute(actions, dry_run=False)

        assert results[0].success
        mock_provider.add_comment.assert_awaited_once()

    async def test_revert_pr_calls_create_pull_request(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.create_pull_request = AsyncMock(
            return_value={"html_url": "https://github.com/org/svc/pull/99"}
        )

        with patch(
            "regulatory_agent_kit.tools.git_provider.create_git_provider",
            return_value=mock_provider,
        ):
            actions = plan_rollback(_manifest(["merged"]))
            executor = RollbackExecutor(git_token="test-token")  # noqa: S106
            results = await executor.execute(actions, dry_run=False)

        assert results[0].success
        assert "pull/99" in results[0].detail
        mock_provider.create_pull_request.assert_awaited_once()


# ------------------------------------------------------------------
# format_rollback_summary
# ------------------------------------------------------------------


class TestFormatRollbackSummary:
    def test_summary_has_jsonld_fields(self) -> None:
        from regulatory_agent_kit.tools.rollback import RollbackResult

        results = [
            RollbackResult(repo_url="r1", action="skip", success=True, detail="done"),
            RollbackResult(
                repo_url="r2", action="close_pr_and_delete_branch", success=False, error="no token"
            ),
        ]
        summary = format_rollback_summary(results)
        assert summary["@context"] == "https://schema.org"
        assert summary["@type"] == "RollbackExecution"
        assert summary["total_actions"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1
        assert len(summary["actions"]) == 2
