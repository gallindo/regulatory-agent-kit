"""Temporal workflow definitions for the compliance pipeline.

Provides ``CompliancePipeline`` (top-level orchestrator) and
``RepositoryProcessor`` (child workflow for per-repo processing).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from regulatory_agent_kit.orchestration.activities import (
        analyze_repository,
        estimate_cost,
        refactor_repository,
        report_results,
        test_repository,
    )


# ---------------------------------------------------------------------------
# Pipeline phases (state machine)
# ---------------------------------------------------------------------------

PHASES = (
    "PENDING",
    "COST_ESTIMATION",
    "ANALYZING",
    "AWAITING_IMPACT_REVIEW",
    "REFACTORING",
    "TESTING",
    "AWAITING_MERGE_REVIEW",
    "REPORTING",
    "COMPLETED",
)


# ---------------------------------------------------------------------------
# Child workflow: per-repository processing
# ---------------------------------------------------------------------------


@workflow.defn
class RepositoryProcessor:
    """Child workflow that processes a single repository: analyze -> refactor -> test."""

    @workflow.run
    async def run(
        self,
        repo_url: str,
        regulation_id: str,
        plugin_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the per-repo pipeline stages sequentially."""
        # 1. Analyze
        impact_map: dict[str, Any] = await workflow.execute_activity(
            analyze_repository,
            args=[repo_url, regulation_id, plugin_data],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # 2. Refactor
        change_set: dict[str, Any] = await workflow.execute_activity(
            refactor_repository,
            args=[repo_url, impact_map, plugin_data],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # 3. Test
        test_result: dict[str, Any] = await workflow.execute_activity(
            test_repository,
            args=[repo_url, change_set],
            start_to_close_timeout=timedelta(minutes=10),
        )

        return {
            "repo_url": repo_url,
            "impact_map": impact_map,
            "change_set": change_set,
            "test_result": test_result,
        }


# ---------------------------------------------------------------------------
# Top-level workflow: CompliancePipeline
# ---------------------------------------------------------------------------


@workflow.defn
class CompliancePipeline:
    """Top-level compliance pipeline workflow with human checkpoint gates.

    State machine: PENDING -> COST_ESTIMATION -> ANALYZING ->
    AWAITING_IMPACT_REVIEW -> REFACTORING -> TESTING ->
    AWAITING_MERGE_REVIEW -> REPORTING -> COMPLETED
    """

    def __init__(self) -> None:
        self._run_id: str = ""
        self._phase: str = "PENDING"
        self._status: str = "pending"
        self._impact_approved: bool = False
        self._merge_approved: bool = False
        self._impact_rejected: bool = False
        self._merge_rejected: bool = False
        self._repo_results: list[dict[str, Any]] = []
        self._cost_estimate: dict[str, Any] = {}

    # -- Signal handlers --------------------------------------------------

    @workflow.signal
    async def approve_impact_review(self, approved: bool) -> None:
        """Signal handler for impact review checkpoint."""
        if approved:
            self._impact_approved = True
        else:
            self._impact_rejected = True

    @workflow.signal
    async def approve_merge_review(self, approved: bool) -> None:
        """Signal handler for merge review checkpoint."""
        if approved:
            self._merge_approved = True
        else:
            self._merge_rejected = True

    # -- Query handler ----------------------------------------------------

    @workflow.query
    def query_status(self) -> dict[str, Any]:
        """Return current pipeline status for external queries."""
        return {
            "run_id": self._run_id,
            "status": self._status,
            "phase": self._phase,
            "repo_counts": {},
            "cost_summary": self._cost_estimate,
        }

    # -- Main workflow run ------------------------------------------------

    @workflow.run
    async def run(
        self,
        regulation_id: str,
        repo_urls: list[str],
        plugin_data: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the full compliance pipeline."""
        self._run_id = str(uuid4())
        self._status = "running"

        model = config.get("default_model", "claude-sonnet-4-20250514")

        # Phase 1: Cost Estimation
        self._phase = "COST_ESTIMATION"
        self._cost_estimate = await workflow.execute_activity(
            estimate_cost,
            args=[repo_urls, regulation_id, model],
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Phase 2: Analyze (fan-out via child workflows — analysis only)
        self._phase = "ANALYZING"
        analysis_handles = []
        for repo_url in repo_urls:
            handle = await workflow.start_child_workflow(
                RepositoryProcessor.run,
                args=[repo_url, regulation_id, plugin_data],
                id=f"repo-{self._run_id}-{repo_url.split('/')[-1]}",
            )
            analysis_handles.append(handle)

        # Fan-in: collect all child workflow results
        self._repo_results = []
        for handle in analysis_handles:
            result: dict[str, Any] = await handle
            self._repo_results.append(result)

        # Phase 3: Await impact review
        self._phase = "AWAITING_IMPACT_REVIEW"
        await workflow.wait_condition(
            lambda: self._impact_approved or self._impact_rejected,
        )

        if self._impact_rejected:
            self._status = "rejected"
            self._phase = "COMPLETED"
            return {
                "run_id": self._run_id,
                "status": "rejected",
                "phase": "impact_review",
            }

        # Phases 4-5 already done in child workflows (refactor + test)
        self._phase = "REFACTORING"
        self._phase = "TESTING"

        # Phase 6: Await merge review
        self._phase = "AWAITING_MERGE_REVIEW"
        await workflow.wait_condition(
            lambda: self._merge_approved or self._merge_rejected,
        )

        if self._merge_rejected:
            self._status = "rejected"
            self._phase = "COMPLETED"
            return {
                "run_id": self._run_id,
                "status": "rejected",
                "phase": "merge_review",
            }

        # Phase 7: Reporting
        self._phase = "REPORTING"
        report: dict[str, Any] = await workflow.execute_activity(
            report_results,
            args=[self._run_id, self._repo_results],
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Done
        self._phase = "COMPLETED"
        self._status = "completed"
        return {
            "run_id": self._run_id,
            "status": "completed",
            "report": report,
            "cost_estimate": self._cost_estimate,
            "repo_results": self._repo_results,
        }


ALL_WORKFLOWS = [CompliancePipeline, RepositoryProcessor]
