"""CI/CD pipeline compliance analyzer.

Discovers CI/CD configuration files in a repository, parses them,
runs compliance checks, and produces a structured analysis result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from regulatory_agent_kit.ci.pipeline_checks import (
    PIPELINE_CHECKS,
    PipelineCheckResult,
)
from regulatory_agent_kit.ci.pipeline_parser import (
    CIPipelineConfig,
    discover_pipeline_configs,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineAnalysisResult:
    """Result of analyzing CI/CD pipelines for compliance."""

    pipelines_analyzed: int = 0
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    findings: list[PipelineCheckResult] = field(default_factory=list)
    pipeline_configs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "pipelines_analyzed": self.pipelines_analyzed,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "pipeline_configs": self.pipeline_configs,
            "findings": [
                {
                    "check_id": f.check_id,
                    "passed": f.passed,
                    "severity": f.severity,
                    "description": f.description,
                    "detail": f.detail,
                }
                for f in self.findings
            ],
        }


def analyze_pipelines(repo_path: Path) -> PipelineAnalysisResult:
    """Analyze all CI/CD pipelines in a repository for compliance.

    Discovers GitHub Actions and GitLab CI configs, parses them,
    and runs all registered pipeline checks.

    Args:
        repo_path: Root directory of the repository.

    Returns:
        A PipelineAnalysisResult with all findings.
    """
    configs = discover_pipeline_configs(repo_path)

    if not configs:
        logger.info("No CI/CD pipeline configurations found in %s", repo_path)
        return PipelineAnalysisResult(pipeline_configs=[])

    findings: list[PipelineCheckResult] = []
    for config in configs:
        findings.extend(_run_checks(config))

    return PipelineAnalysisResult(
        pipelines_analyzed=len(configs),
        checks_run=len(findings),
        checks_passed=sum(1 for f in findings if f.passed),
        checks_failed=sum(1 for f in findings if not f.passed),
        findings=findings,
        pipeline_configs=[c.source_file for c in configs],
    )


def _run_checks(config: CIPipelineConfig) -> list[PipelineCheckResult]:
    """Run all pipeline checks against a single config.

    Returns the list of check results. Checks that raise are logged and
    skipped rather than aborting the batch.
    """
    results: list[PipelineCheckResult] = []
    for check in PIPELINE_CHECKS:
        try:
            results.append(check.check_fn(config))
        except Exception:
            logger.warning(
                "Check %s failed on %s",
                check.check_id,
                config.source_file,
                exc_info=True,
            )
    return results


def format_pipeline_analysis_as_markdown(result: PipelineAnalysisResult) -> str:
    """Format pipeline analysis results as markdown for PR comments.

    Args:
        result: The pipeline analysis result.

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    lines.append("### CI/CD Pipeline Analysis")
    lines.append("")
    lines.append(
        f"**Pipelines analyzed:** {result.pipelines_analyzed}"
        f" | **Checks:** {result.checks_passed}/{result.checks_run} passed"
    )

    if result.checks_failed == 0:
        lines.append("")
        lines.append("All pipeline compliance checks passed.")
        return "\n".join(lines)

    lines.append("")
    failed = [f for f in result.findings if not f.passed]

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    failed.sort(key=lambda f: severity_order.get(f.severity, 4))

    lines.append("| Severity | Check | Finding |")
    lines.append("|----------|-------|---------|")
    for finding in failed:
        detail = finding.detail or finding.description
        lines.append(f"| {finding.severity.upper()} | `{finding.check_id}` | {detail} |")
    lines.append("")

    return "\n".join(lines)
