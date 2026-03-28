"""Lite Mode sequential executor — runs the pipeline without Temporal.

Provides ``LiteModeExecutor`` that executes the same compliance pipeline
logic sequentially in-process, backed by SQLite for persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from regulatory_agent_kit.database.lite import (
    LiteAuditRepository,
    LiteCheckpointDecisionRepository,
    LitePipelineRunRepository,
    LiteRepositoryProgressRepository,
    create_tables,
)
from regulatory_agent_kit.database.protocols import (  # noqa: TC001
    AuditStore,
    CheckpointStore,
    PipelineRunStore,
    RepositoryProgressStore,
)

logger = logging.getLogger(__name__)

# The phases the executor walks through, in order.
LITE_PHASES = (
    "COST_ESTIMATION",
    "ANALYZING",
    "AWAITING_IMPACT_REVIEW",
    "REFACTORING",
    "TESTING",
    "AWAITING_MERGE_REVIEW",
    "REPORTING",
    "COMPLETED",
)


@dataclass
class LiteModeResult:
    """Result returned by a Lite Mode pipeline execution."""

    run_id: str
    status: str
    phases_executed: list[str] = field(default_factory=list)
    cost_estimate: dict[str, Any] = field(default_factory=dict)
    repo_results: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pipeline context — shared state passed between phases
# ---------------------------------------------------------------------------


@dataclass
class PipelineContext:
    """Shared state passed between pipeline phases."""

    run_id: str
    run_uuid: UUID
    regulation_id: str
    repo_urls: list[str]
    plugin_data: dict[str, Any]
    config: dict[str, Any]
    result: LiteModeResult
    pipeline_repo: PipelineRunStore
    progress_repo: RepositoryProgressStore
    audit_repo: AuditStore
    checkpoint_repo: CheckpointStore


# ---------------------------------------------------------------------------
# Phase protocol & concrete phase implementations
# ---------------------------------------------------------------------------


class PipelinePhase(Protocol):
    """Interface for a single pipeline phase."""

    @property
    def name(self) -> str: ...

    async def execute(self, context: PipelineContext) -> None: ...


class CostEstimationPhase:
    """Estimate per-repo costs for the pipeline run."""

    @property
    def name(self) -> str:
        return "COST_ESTIMATION"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: COST_ESTIMATION")
        model = context.config.get("default_model", "claude-sonnet-4-20250514")
        per_repo = {url: 1.50 for url in context.repo_urls}
        context.result.cost_estimate = {
            "estimated_total_cost": sum(per_repo.values()),
            "per_repo_cost": per_repo,
            "estimated_total_tokens": len(context.repo_urls) * 10_000,
            "model_used": model,
            "exceeds_threshold": False,
        }


class AnalysisPhase:
    """Run stub analysis on each repository."""

    @property
    def name(self) -> str:
        return "ANALYZING"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: ANALYZING")
        for repo_url in context.repo_urls:
            entry_id = await context.progress_repo.create(context.run_uuid, repo_url)
            await context.progress_repo.update_status(entry_id, "in_progress")
            analysis = {
                "files": [],
                "conflicts": [],
                "analysis_confidence": 0.85,
            }
            context.result.repo_results.append(
                {
                    "repo_url": repo_url,
                    "impact_map": analysis,
                    "change_set": {},
                    "test_result": {},
                }
            )


class ImpactReviewPhase:
    """Auto-approve impact review checkpoint in Lite Mode."""

    @property
    def name(self) -> str:
        return "AWAITING_IMPACT_REVIEW"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: AWAITING_IMPACT_REVIEW (auto-approved)")
        await context.checkpoint_repo.create(
            run_id=context.run_uuid,
            checkpoint_type="impact_review",
            actor="lite-mode-auto",
            decision="approved",
            signature="",
            rationale="Auto-approved in Lite Mode",
        )


class RefactoringPhase:
    """Generate stub change-sets for each repository."""

    @property
    def name(self) -> str:
        return "REFACTORING"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: REFACTORING")
        for repo_result in context.result.repo_results:
            repo_result["change_set"] = {
                "branch_name": (f"rak/fix-{repo_result['repo_url'].split('/')[-1]}"),
                "diffs": [],
                "confidence_scores": [],
                "commit_sha": "abcdef1234567890",
            }


class TestingPhase:
    """Generate stub test results for each repository."""

    @property
    def name(self) -> str:
        return "TESTING"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: TESTING")
        for repo_result in context.result.repo_results:
            repo_result["test_result"] = {
                "pass_rate": 1.0,
                "total_tests": 5,
                "passed": 5,
                "failed": 0,
                "failures": [],
                "test_files_created": [],
            }


class MergeReviewPhase:
    """Auto-approve merge review checkpoint in Lite Mode."""

    @property
    def name(self) -> str:
        return "AWAITING_MERGE_REVIEW"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: AWAITING_MERGE_REVIEW (auto-approved)")
        await context.checkpoint_repo.create(
            run_id=context.run_uuid,
            checkpoint_type="merge_review",
            actor="lite-mode-auto",
            decision="approved",
            signature="",
            rationale="Auto-approved in Lite Mode",
        )


class ReportingPhase:
    """Generate stub report artefact paths."""

    @property
    def name(self) -> str:
        return "REPORTING"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("[Lite] Phase: REPORTING")
        run_id = context.run_id
        context.result.report = {
            "pr_urls": [],
            "audit_log_path": f"/tmp/rak/{run_id}/audit.jsonl",  # noqa: S108
            "report_path": f"/tmp/rak/{run_id}/report.html",  # noqa: S108
            "rollback_manifest_path": f"/tmp/rak/{run_id}/rollback.yaml",  # noqa: S108
        }


class CompletionPhase:
    """Mark the pipeline run as completed and log an audit entry."""

    @property
    def name(self) -> str:
        return "COMPLETED"

    async def execute(self, context: PipelineContext) -> None:
        context.result.status = "completed"
        await context.pipeline_repo.update_status(context.run_uuid, "completed")
        await context.audit_repo.insert(
            run_id=context.run_uuid,
            event_type="state_transition",
            timestamp=datetime.now(UTC),
            payload={"phase": "COMPLETED", "status": "completed"},
            signature="",
        )
        logger.info("[Lite] Pipeline %s completed successfully", context.run_id)


# ---------------------------------------------------------------------------
# Default phase ordering
# ---------------------------------------------------------------------------

_DEFAULT_PHASES: tuple[PipelinePhase, ...] = (
    CostEstimationPhase(),
    AnalysisPhase(),
    ImpactReviewPhase(),
    RefactoringPhase(),
    TestingPhase(),
    MergeReviewPhase(),
    ReportingPhase(),
    CompletionPhase(),
)


# ---------------------------------------------------------------------------
# Repository factory type
# ---------------------------------------------------------------------------


class RepoFactory(Protocol):
    """Callable that produces the four repository stores."""

    def __call__(
        self, db_path: Path
    ) -> tuple[
        PipelineRunStore,
        RepositoryProgressStore,
        AuditStore,
        CheckpointStore,
    ]: ...


def _default_repo_factory(
    db_path: Path,
) -> tuple[
    PipelineRunStore,
    RepositoryProgressStore,
    AuditStore,
    CheckpointStore,
]:
    """Create the default Lite SQLite-backed repositories."""
    return (
        LitePipelineRunRepository(db_path),
        LiteRepositoryProgressRepository(db_path),
        LiteAuditRepository(db_path),
        LiteCheckpointDecisionRepository(db_path),
    )


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------


class LiteModeExecutor:
    """Sequential pipeline executor for Lite Mode (no Temporal required).

    Runs all pipeline phases in order, using SQLite for state tracking
    and auto-approving checkpoints (real terminal prompts are Phase 13).
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        repo_factory: RepoFactory | None = None,
    ) -> None:
        if db_path is None:
            db_path = Path.home() / ".rak" / "lite.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._repo_factory: RepoFactory = repo_factory or _default_repo_factory

    async def run(
        self,
        regulation_id: str,
        repo_urls: list[str],
        plugin_data: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> LiteModeResult:
        """Execute the full compliance pipeline sequentially.

        Args:
            regulation_id: Plugin ID for the target regulation.
            repo_urls: List of repository URLs to scan.
            plugin_data: Loaded regulation plugin data.
            config: Pipeline configuration overrides.

        Returns:
            A ``LiteModeResult`` with the pipeline outcome.
        """
        config = config or {}
        run_id = str(uuid4())
        run_uuid = UUID(run_id)
        result = LiteModeResult(run_id=run_id, status="running")

        # Ensure tables exist
        await create_tables(self._db_path)

        # Initialise repositories via injected factory
        pipeline_repo, progress_repo, audit_repo, checkpoint_repo = self._repo_factory(
            self._db_path
        )

        # Persist the run
        await pipeline_repo.create(
            regulation_id=regulation_id,
            total_repos=len(repo_urls),
            config_snapshot=config,
        )

        context = PipelineContext(
            run_id=run_id,
            run_uuid=run_uuid,
            regulation_id=regulation_id,
            repo_urls=repo_urls,
            plugin_data=plugin_data,
            config=config,
            result=result,
            pipeline_repo=pipeline_repo,
            progress_repo=progress_repo,
            audit_repo=audit_repo,
            checkpoint_repo=checkpoint_repo,
        )

        for phase in _DEFAULT_PHASES:
            await phase.execute(context)
            result.phases_executed.append(phase.name)

        return result
