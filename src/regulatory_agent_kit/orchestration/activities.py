"""Temporal activity definitions for the compliance pipeline.

Each activity wraps a corresponding agent. Currently stubbed with placeholder
implementations that will be replaced when agents are fully integrated.
"""

from __future__ import annotations

import logging
from collections.abc import Callable  # noqa: TC003
from dataclasses import dataclass
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants for stub / placeholder values
# ---------------------------------------------------------------------------

ESTIMATED_COST_PER_REPO_USD: float = 1.50
ESTIMATED_TOKENS_PER_REPO: int = 10_000
DEFAULT_ANALYSIS_CONFIDENCE: float = 0.85
MOCK_TOTAL_TESTS: int = 5
MOCK_PASS_RATE: float = 1.0


@dataclass
class ActivityContext:
    """Shared context passed to all activities."""

    model: str = "claude-sonnet-4-20250514"
    litellm_url: str = "http://localhost:4000"


@activity.defn
async def estimate_cost(
    repo_urls: list[str],
    regulation_id: str,
    model: str,
) -> dict[str, Any]:
    """Estimate LLM cost for processing the given repositories.

    Wraps the cost estimation logic (stub for now).
    """
    activity.logger.info(
        "Estimating cost for %d repos with regulation %s",
        len(repo_urls),
        regulation_id,
    )
    per_repo = {url: ESTIMATED_COST_PER_REPO_USD for url in repo_urls}
    total = sum(per_repo.values())
    return {
        "estimated_total_cost": total,
        "per_repo_cost": per_repo,
        "estimated_total_tokens": len(repo_urls) * ESTIMATED_TOKENS_PER_REPO,
        "model_used": model,
        "exceeds_threshold": False,
    }


@activity.defn
async def analyze_repository(
    repo_url: str,
    regulation_id: str,
    plugin_data: dict[str, Any],
) -> dict[str, Any]:
    """Analyze a repository for regulatory compliance violations.

    Wraps the Analyzer agent (stub for now).
    """
    activity.logger.info("Analyzing repository %s", repo_url)
    return {
        "files": [],
        "conflicts": [],
        "analysis_confidence": DEFAULT_ANALYSIS_CONFIDENCE,
    }


@activity.defn
async def refactor_repository(
    repo_url: str,
    impact_map: dict[str, Any],
    plugin_data: dict[str, Any],
) -> dict[str, Any]:
    """Apply compliance fixes to a repository based on impact analysis.

    Wraps the Refactor agent (stub for now).
    """
    activity.logger.info("Refactoring repository %s", repo_url)
    return {
        "branch_name": f"rak/fix-{repo_url.split('/')[-1]}",
        "diffs": [],
        "confidence_scores": [],
        "commit_sha": "abcdef1234567890",
    }


@activity.defn
async def test_repository(
    repo_url: str,
    change_set: dict[str, Any],
) -> dict[str, Any]:
    """Generate and run tests for remediation changes.

    Wraps the TestGenerator agent (stub for now).
    """
    activity.logger.info("Testing repository %s", repo_url)
    return {
        "pass_rate": MOCK_PASS_RATE,
        "total_tests": MOCK_TOTAL_TESTS,
        "passed": MOCK_TOTAL_TESTS,
        "failed": 0,
        "failures": [],
        "test_files_created": [],
    }


@activity.defn
async def report_results(
    run_id: str,
    repo_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate compliance report and audit log export.

    Wraps the Reporter agent (stub for now).
    """
    activity.logger.info("Generating report for run %s", run_id)
    return {
        "pr_urls": [],
        "audit_log_path": f"/tmp/rak/{run_id}/audit.jsonl",  # noqa: S108
        "report_path": f"/tmp/rak/{run_id}/report.html",  # noqa: S108
        "rollback_manifest_path": f"/tmp/rak/{run_id}/rollback.yaml",  # noqa: S108
    }


ALL_ACTIVITIES: list[Callable[..., Any]] = [
    estimate_cost,
    analyze_repository,
    refactor_repository,
    test_repository,
    report_results,
]
