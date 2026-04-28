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

    def record_phase(self, phase_name: str) -> None:
        """Record that a phase was executed."""
        self.phases_executed.append(phase_name)

    def add_repo_result(self, result: dict[str, Any]) -> None:
        """Add a repository processing result."""
        self.repo_results.append(result)


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

    def get_model(self) -> str:
        """Return the configured LLM model name."""
        model: str = self.config.get("default_model", "claude-sonnet-4-20250514")
        return model

    def get_cost_threshold(self) -> float:
        """Return the configured cost threshold."""
        return float(self.config.get("cost_threshold", 50.0))

    # -- Result delegates (Law of Demeter) --

    def set_cost_estimate(self, estimate: dict[str, Any]) -> None:
        """Set the cost estimate on the pipeline result."""
        self.result.cost_estimate = estimate

    def add_repo_result(self, result: dict[str, Any]) -> None:
        """Add a repository processing result."""
        self.result.add_repo_result(result)

    @property
    def repo_results(self) -> list[dict[str, Any]]:
        """Return the per-repo result list."""
        return self.result.repo_results

    def set_report(self, report: dict[str, Any]) -> None:
        """Set the report artefact bundle on the result."""
        self.result.report = report

    def mark_completed(self) -> None:
        """Mark the pipeline result as completed."""
        self.result.status = "completed"


class PipelineContextBuilder:
    """Fluent builder for PipelineContext."""

    def __init__(self) -> None:
        self._run_id: str = ""
        self._run_uuid: UUID | None = None
        self._regulation_id: str = ""
        self._repo_urls: list[str] = []
        self._plugin_data: dict[str, Any] = {}
        self._config: dict[str, Any] = {}

    def with_run(self, run_id: str, run_uuid: UUID) -> PipelineContextBuilder:
        """Set the run identifier and UUID."""
        self._run_id = run_id
        self._run_uuid = run_uuid
        return self

    def with_regulation(self, regulation_id: str) -> PipelineContextBuilder:
        """Set the regulation plugin identifier."""
        self._regulation_id = regulation_id
        return self

    def with_repos(self, repo_urls: list[str]) -> PipelineContextBuilder:
        """Set the list of repository URLs to scan."""
        self._repo_urls = repo_urls
        return self

    def with_plugin_data(self, data: dict[str, Any]) -> PipelineContextBuilder:
        """Set the loaded regulation plugin data."""
        self._plugin_data = data
        return self

    def with_config(self, config: dict[str, Any]) -> PipelineContextBuilder:
        """Set pipeline configuration overrides."""
        self._config = config
        return self

    def build(
        self,
        result: LiteModeResult,
        pipeline_repo: PipelineRunStore,
        progress_repo: RepositoryProgressStore,
        audit_repo: AuditStore,
        checkpoint_repo: CheckpointStore,
    ) -> PipelineContext:
        """Build the PipelineContext, raising ValueError if run_uuid is unset."""
        if self._run_uuid is None:
            msg = "run_uuid is required"
            raise ValueError(msg)
        return PipelineContext(
            run_id=self._run_id,
            run_uuid=self._run_uuid,
            regulation_id=self._regulation_id,
            repo_urls=self._repo_urls,
            plugin_data=self._plugin_data,
            config=self._config,
            result=result,
            pipeline_repo=pipeline_repo,
            progress_repo=progress_repo,
            audit_repo=audit_repo,
            checkpoint_repo=checkpoint_repo,
        )


# ---------------------------------------------------------------------------
# Phase protocol & concrete phase implementations
# ---------------------------------------------------------------------------


class PipelinePhase(Protocol):
    """Interface for a single pipeline phase."""

    @property
    def name(self) -> str: ...

    async def execute(self, context: PipelineContext) -> None: ...


class BasePipelinePhase:
    """Template Method base — logs phase entry, delegates to ``run()``.

    Subclasses override ``run()`` to implement phase-specific logic.
    The ``execute()`` method provides the common lifecycle: log → run.
    """

    @property
    def name(self) -> str:
        msg = "Subclasses must define the name property"
        raise NotImplementedError(msg)

    async def execute(self, context: PipelineContext) -> None:
        """Template method: log phase entry then delegate to run()."""
        logger.info("[Lite] Phase: %s", self.name)
        await self.run(context)

    async def run(self, context: PipelineContext) -> None:
        """Hook method — override in subclasses."""
        msg = "Subclasses must implement run()"
        raise NotImplementedError(msg)


class CostEstimationPhase(BasePipelinePhase):
    """Estimate per-repo costs for the pipeline run."""

    @property
    def name(self) -> str:
        return "COST_ESTIMATION"

    async def run(self, context: PipelineContext) -> None:
        from regulatory_agent_kit.tools.cost_estimator import CostEstimator

        estimator = CostEstimator(
            model=context.get_model(),
            cost_threshold=context.get_cost_threshold(),
        )
        context.set_cost_estimate(estimator.estimate_for_repos(context.repo_urls))


class AnalysisPhase(BasePipelinePhase):
    """Analyze each repository against plugin rules."""

    @property
    def name(self) -> str:
        return "ANALYZING"

    async def run(self, context: PipelineContext) -> None:
        from regulatory_agent_kit.orchestration.activities import (
            analyze_repository,
        )

        for repo_url in context.repo_urls:
            entry_id = await context.progress_repo.create(context.run_uuid, repo_url)
            await context.progress_repo.update_status(entry_id, "in_progress")
            analysis = await analyze_repository(
                repo_url, context.regulation_id, context.plugin_data
            )
            context.add_repo_result(
                {
                    "repo_url": repo_url,
                    "impact_map": analysis,
                    "change_set": {},
                    "test_result": {},
                }
            )


async def _auto_approve_checkpoint(context: PipelineContext, checkpoint_type: str) -> None:
    """Record an auto-approved checkpoint decision in Lite Mode."""
    await context.checkpoint_repo.create(
        run_id=context.run_uuid,
        checkpoint_type=checkpoint_type,
        actor="lite-mode-auto",
        decision="approved",
        signature="",
        rationale="Auto-approved in Lite Mode",
    )


class ImpactReviewPhase(BasePipelinePhase):
    """Auto-approve impact review checkpoint in Lite Mode."""

    @property
    def name(self) -> str:
        return "AWAITING_IMPACT_REVIEW"

    async def run(self, context: PipelineContext) -> None:
        await _auto_approve_checkpoint(context, "impact_review")


class RefactoringPhase(BasePipelinePhase):
    """Apply compliance fixes for each repository."""

    @property
    def name(self) -> str:
        return "REFACTORING"

    async def run(self, context: PipelineContext) -> None:
        from regulatory_agent_kit.orchestration.activities import (
            refactor_repository,
        )

        for repo_result in context.repo_results:
            change_set = await refactor_repository(
                repo_result["repo_url"],
                repo_result.get("impact_map", {}),
                context.plugin_data,
            )
            repo_result["change_set"] = change_set


class TestingPhase(BasePipelinePhase):
    """Generate and validate tests for each repository."""

    @property
    def name(self) -> str:
        return "TESTING"

    async def run(self, context: PipelineContext) -> None:
        from regulatory_agent_kit.orchestration.activities import (
            test_repository,
        )

        for repo_result in context.repo_results:
            test_result = await test_repository(
                repo_result["repo_url"],
                repo_result.get("change_set", {}),
            )
            repo_result["test_result"] = test_result


class MergeReviewPhase(BasePipelinePhase):
    """Auto-approve merge review checkpoint in Lite Mode."""

    @property
    def name(self) -> str:
        return "AWAITING_MERGE_REVIEW"

    async def run(self, context: PipelineContext) -> None:
        await _auto_approve_checkpoint(context, "merge_review")


class ReportingPhase(BasePipelinePhase):
    """Generate compliance report artefacts."""

    @property
    def name(self) -> str:
        return "REPORTING"

    async def run(self, context: PipelineContext) -> None:
        from regulatory_agent_kit.orchestration.activities import report_results

        report = await report_results(
            context.run_id,
            context.repo_results,
            regulation_id=context.regulation_id,
        )
        context.set_report(report)


class CompletionPhase(BasePipelinePhase):
    """Mark the pipeline run as completed and log an audit entry."""

    @property
    def name(self) -> str:
        return "COMPLETED"

    async def run(self, context: PipelineContext) -> None:
        context.mark_completed()
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

        context = (
            PipelineContextBuilder()
            .with_run(run_id, run_uuid)
            .with_regulation(regulation_id)
            .with_repos(repo_urls)
            .with_plugin_data(plugin_data)
            .with_config(config)
            .build(
                result,
                pipeline_repo,
                progress_repo,
                audit_repo,
                checkpoint_repo,
            )
        )

        for phase in _DEFAULT_PHASES:
            await phase.execute(context)
            result.record_phase(phase.name)

        return result
