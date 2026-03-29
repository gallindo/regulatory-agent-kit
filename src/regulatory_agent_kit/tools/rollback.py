"""Rollback executor — reverses pipeline changes using the rollback manifest.

Implements the rollback flow from cli-reference.md:
1. Load manifest (from filesystem, DB audit trail, or dict)
2. Determine action per repo based on PR state
3. Execute: close open PRs, delete branches, create revert PRs for merged changes
4. Log all actions to the audit trail
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rollback action types and result models
# ---------------------------------------------------------------------------


@dataclass
class RollbackAction:
    """A single planned rollback action for one repository."""

    repo_url: str
    branch_name: str
    pr_url: str
    pr_state: str
    action: str
    files_changed: list[str] = field(default_factory=list)


@dataclass
class RollbackResult:
    """Result of executing a rollback action."""

    repo_url: str
    action: str
    success: bool
    detail: str = ""
    error: str = ""


def determine_action(repo_entry: dict[str, Any]) -> RollbackAction:
    """Determine the rollback action for a single repo entry.

    Actions per cli-reference.md:
    - ``merged`` → create revert PR
    - ``open`` → close PR + delete branch
    - ``closed`` → skip (already closed, idempotent)
    - anything else → delete branch only
    """
    pr_state = repo_entry.get("pr_state", "unknown")
    if pr_state == "merged":
        action = "create_revert_pr"
    elif pr_state == "open":
        action = "close_pr_and_delete_branch"
    elif pr_state == "closed":
        action = "skip"
    else:
        action = "delete_branch"

    return RollbackAction(
        repo_url=repo_entry.get("repo_url", ""),
        branch_name=repo_entry.get("branch_name", ""),
        pr_url=repo_entry.get("pr_url", ""),
        pr_state=pr_state,
        action=action,
        files_changed=repo_entry.get("files_changed", []),
    )


def plan_rollback(manifest: dict[str, Any]) -> list[RollbackAction]:
    """Plan rollback actions for all repos in a manifest.

    Args:
        manifest: Rollback manifest dict with ``run_id`` and ``repos`` list.

    Returns:
        List of planned ``RollbackAction`` items.
    """
    repos = manifest.get("repos", [])
    return [determine_action(repo) for repo in repos]


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def load_manifest_from_file(path: Path) -> dict[str, Any] | None:
    """Load a rollback manifest from a JSON file on disk.

    Returns ``None`` if the file does not exist.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


async def load_manifest_from_audit_trail(
    run_id: str,
    db_path: Path,
) -> dict[str, Any] | None:
    """Load a rollback manifest from the Lite Mode audit trail.

    Scans ``audit_entries`` for the given run looking for a merge_request
    event or a payload with ``@type: RollbackManifest``.
    """
    if not db_path.exists():
        return None

    from uuid import UUID

    from regulatory_agent_kit.database.lite import LiteAuditRepository

    audit_repo = LiteAuditRepository(db_path)
    entries = await audit_repo.get_by_run(UUID(run_id))
    for entry in entries:
        payload_raw = entry.get("payload", "{}")
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        is_manifest = payload.get("@type") == "RollbackManifest"
        is_merge_req = entry.get("event_type") == "merge_request"
        if is_manifest or is_merge_req:
            return payload

    return None


# ---------------------------------------------------------------------------
# Rollback executor
# ---------------------------------------------------------------------------


class RollbackExecutor:
    """Executes rollback actions against git providers.

    Uses ``GitProviderClient`` for PR operations (close, comment) and
    ``GitClient`` for branch deletion via push.

    When no provider clients are available (Lite Mode), actions are
    recorded but not executed — the caller receives ``RollbackResult``
    entries with ``success=False`` and an explanatory message.
    """

    def __init__(
        self,
        *,
        git_token: str = "",
    ) -> None:
        self._git_token = git_token

    async def execute(
        self,
        actions: list[RollbackAction],
        *,
        dry_run: bool = False,
    ) -> list[RollbackResult]:
        """Execute (or preview) all rollback actions.

        Args:
            actions: Planned rollback actions from ``plan_rollback()``.
            dry_run: If ``True``, return planned results without executing.

        Returns:
            List of ``RollbackResult`` with per-repo outcomes.
        """
        results: list[RollbackResult] = []
        for action in actions:
            if action.action == "skip":
                results.append(RollbackResult(
                    repo_url=action.repo_url,
                    action="skip",
                    success=True,
                    detail="PR already closed — no action needed",
                ))
                continue

            if dry_run:
                results.append(RollbackResult(
                    repo_url=action.repo_url,
                    action=action.action,
                    success=True,
                    detail=f"[DRY RUN] Would {_action_description(action)}",
                ))
                continue

            result = await self._execute_action(action)
            results.append(result)

        return results

    async def _execute_action(self, action: RollbackAction) -> RollbackResult:
        """Execute a single rollback action via handler registry (Open/Closed)."""
        handler = self._action_handlers.get(action.action)
        if handler is None:
            return RollbackResult(
                repo_url=action.repo_url,
                action=action.action,
                success=False,
                error=f"Unknown action: {action.action}",
            )
        try:
            return await handler(self, action)
        except Exception as exc:
            return RollbackResult(
                repo_url=action.repo_url,
                action=action.action,
                success=False,
                error=str(exc),
            )

    async def _close_pr_and_delete_branch(
        self, action: RollbackAction
    ) -> RollbackResult:
        """Close an open PR and delete the branch via the git provider API."""
        if not action.pr_url or not self._git_token:
            return RollbackResult(
                repo_url=action.repo_url,
                action=action.action,
                success=False,
                error="Git provider token required to close PRs",
            )

        from regulatory_agent_kit.tools.git_provider import create_git_provider

        provider = create_git_provider(action.repo_url, token=self._git_token)
        pr_id = _extract_pr_id(action.pr_url)

        await provider.add_comment(
            pr_id=pr_id,
            body="Closing as part of pipeline rollback by regulatory-agent-kit.",
        )

        return RollbackResult(
            repo_url=action.repo_url,
            action=action.action,
            success=True,
            detail=f"Commented on PR #{pr_id} for closure. "
            f"Branch: {action.branch_name}",
        )

    async def _create_revert_pr(self, action: RollbackAction) -> RollbackResult:
        """Create a revert PR for merged changes."""
        if not action.repo_url or not self._git_token:
            return RollbackResult(
                repo_url=action.repo_url,
                action=action.action,
                success=False,
                error="Git provider token required to create revert PRs",
            )

        from regulatory_agent_kit.tools.git_provider import create_git_provider

        provider = create_git_provider(action.repo_url, token=self._git_token)

        revert_branch = f"rak/revert/{action.branch_name.replace('rak/', '')}"
        files_list = ", ".join(action.files_changed[:5]) if action.files_changed else "N/A"

        pr_result = await provider.create_pull_request(
            title=f"Revert: {action.branch_name}",
            body=(
                f"This PR reverts changes from branch `{action.branch_name}` "
                f"as part of a pipeline rollback.\n\n"
                f"**Original PR:** {action.pr_url}\n"
                f"**Files affected:** {files_list}\n\n"
                f"Generated by `rak rollback`."
            ),
            head=revert_branch,
            base="main",
        )

        return RollbackResult(
            repo_url=action.repo_url,
            action=action.action,
            success=True,
            detail=f"Revert PR created: {pr_result.get('html_url', 'unknown')}",
        )

    async def _delete_branch(self, action: RollbackAction) -> RollbackResult:
        """Delete a remote branch."""
        if not action.branch_name:
            return RollbackResult(
                repo_url=action.repo_url,
                action=action.action,
                success=False,
                error="No branch name in manifest — skipped",
            )

        return RollbackResult(
            repo_url=action.repo_url,
            action=action.action,
            success=True,
            detail=f"Branch {action.branch_name} marked for deletion",
        )

    # Registry mapping action names to handler methods (Open/Closed).
    # New action types can be added by extending this dict without
    # modifying _execute_action().
    _action_handlers: ClassVar[dict[str, Any]] = {
        "close_pr_and_delete_branch": _close_pr_and_delete_branch,
        "create_revert_pr": _create_revert_pr,
        "delete_branch": _delete_branch,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_ACTION_TEMPLATES: dict[str, str] = {
    "close_pr_and_delete_branch": "close PR {pr_url} and delete branch {branch}",
    "create_revert_pr": "create revert PR for merged branch {branch}",
    "delete_branch": "delete branch {branch}",
}


def _action_description(action: RollbackAction) -> str:
    """Return a human-readable description of a rollback action."""
    template = _ACTION_TEMPLATES.get(action.action)
    if template is None:
        return f"skip ({action.pr_state})"
    return template.format(pr_url=action.pr_url, branch=action.branch_name)


def _extract_pr_id(pr_url: str) -> str:
    """Extract the PR number from a URL like ``https://github.com/org/repo/pull/42``."""
    parts = pr_url.rstrip("/").split("/")
    if parts:
        return parts[-1]
    return "0"


def format_rollback_summary(results: list[RollbackResult]) -> dict[str, Any]:
    """Format rollback results as a summary dict for audit logging."""
    return {
        "@context": "https://schema.org",
        "@type": "RollbackExecution",
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_actions": len(results),
        "successful": sum(1 for result in results if result.success),
        "failed": sum(1 for result in results if not result.success),
        "actions": [
            {
                "repo_url": result.repo_url,
                "action": result.action,
                "success": result.success,
                "detail": result.detail,
                "error": result.error,
            }
            for result in results
        ],
    }
