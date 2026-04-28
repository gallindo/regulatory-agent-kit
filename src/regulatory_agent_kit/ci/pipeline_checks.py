"""Data-driven compliance checks for CI/CD pipeline configurations.

Each check is defined as a dataclass with a check function that receives
a CIPipelineConfig and returns a pass/fail result. No regulatory logic
is hardcoded — checks are generic pipeline security best practices that
map to regulation rule requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from regulatory_agent_kit.ci.pipeline_parser import CIPipelineConfig


@dataclass(frozen=True)
class PipelineCheckResult:
    """Result of a single pipeline compliance check."""

    check_id: str
    passed: bool
    severity: str
    description: str
    detail: str = ""


@dataclass(frozen=True)
class PipelineCheck:
    """A single compliance check definition for CI/CD pipelines."""

    check_id: str
    description: str
    severity: str  # critical, high, medium, low
    check_fn: Callable[[CIPipelineConfig], PipelineCheckResult]


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def _check_security_scanning(config: CIPipelineConfig) -> PipelineCheckResult:
    """Verify that security scanning (SAST/DAST) is present."""
    return PipelineCheckResult(
        check_id="PIPE-001",
        passed=config.has_security_scanning,
        severity="high",
        description="Security scanning (SAST/DAST) must be present in CI pipeline.",
        detail=""
        if config.has_security_scanning
        else f"No security scanning step found in {config.source_file}.",
    )


def _check_dependency_scanning(config: CIPipelineConfig) -> PipelineCheckResult:
    """Verify that dependency vulnerability scanning is present."""
    return PipelineCheckResult(
        check_id="PIPE-002",
        passed=config.has_dependency_scanning,
        severity="high",
        description="Dependency vulnerability scanning must be present.",
        detail=""
        if config.has_dependency_scanning
        else f"No dependency scanning step found in {config.source_file}.",
    )


def _check_test_step(config: CIPipelineConfig) -> PipelineCheckResult:
    """Verify that a test execution step is present."""
    return PipelineCheckResult(
        check_id="PIPE-003",
        passed=config.has_test_step,
        severity="high",
        description="Test execution step must be present in CI pipeline.",
        detail="" if config.has_test_step else f"No test step found in {config.source_file}.",
    )


def _check_deployment_approval(config: CIPipelineConfig) -> PipelineCheckResult:
    """Verify that deployment steps have approval gates."""
    if not config.has_deployment_step:
        return PipelineCheckResult(
            check_id="PIPE-004",
            passed=True,
            severity="medium",
            description="Deployment steps should have approval gates.",
            detail="No deployment step found — check not applicable.",
        )
    return PipelineCheckResult(
        check_id="PIPE-004",
        passed=config.has_approval_gate,
        severity="medium",
        description="Deployment steps should have approval gates.",
        detail=""
        if config.has_approval_gate
        else f"Deployment found without approval gate in {config.source_file}.",
    )


def _check_no_hardcoded_secrets(config: CIPipelineConfig) -> PipelineCheckResult:
    """Verify that secrets are referenced, not hardcoded."""
    hardcoded: list[str] = []
    for job in config.jobs:
        for step in job.steps:
            for key, val in step.env_vars.items():
                val_str = str(val)
                # Check for patterns that suggest hardcoded secrets
                if (
                    any(k in key.upper() for k in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
                    and "${{" not in val_str
                    and val_str
                    and not val_str.startswith("$")
                ):
                    hardcoded.append(f"{job.name}/{step.name}: {key}")

    return PipelineCheckResult(
        check_id="PIPE-005",
        passed=not hardcoded,
        severity="critical",
        description="Secrets must not be hardcoded in pipeline configuration.",
        detail=f"Potentially hardcoded secrets: {', '.join(hardcoded)}" if hardcoded else "",
    )


def _check_artifact_signing(config: CIPipelineConfig) -> PipelineCheckResult:
    """Verify that artifacts/containers are signed."""
    if not config.has_deployment_step:
        return PipelineCheckResult(
            check_id="PIPE-006",
            passed=True,
            severity="low",
            description="Artifacts should be signed before deployment.",
            detail="No deployment step found — check not applicable.",
        )
    return PipelineCheckResult(
        check_id="PIPE-006",
        passed=config.has_artifact_signing,
        severity="low",
        description="Artifacts should be signed before deployment.",
        detail=""
        if config.has_artifact_signing
        else f"No artifact signing step found in {config.source_file}.",
    )


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

PIPELINE_CHECKS: list[PipelineCheck] = [
    PipelineCheck(
        check_id="PIPE-001",
        description="Security scanning (SAST/DAST) must be present",
        severity="high",
        check_fn=_check_security_scanning,
    ),
    PipelineCheck(
        check_id="PIPE-002",
        description="Dependency vulnerability scanning must be present",
        severity="high",
        check_fn=_check_dependency_scanning,
    ),
    PipelineCheck(
        check_id="PIPE-003",
        description="Test execution step must be present",
        severity="high",
        check_fn=_check_test_step,
    ),
    PipelineCheck(
        check_id="PIPE-004",
        description="Deployment steps should have approval gates",
        severity="medium",
        check_fn=_check_deployment_approval,
    ),
    PipelineCheck(
        check_id="PIPE-005",
        description="Secrets must not be hardcoded",
        severity="critical",
        check_fn=_check_no_hardcoded_secrets,
    ),
    PipelineCheck(
        check_id="PIPE-006",
        description="Artifacts should be signed before deployment",
        severity="low",
        check_fn=_check_artifact_signing,
    ),
]
