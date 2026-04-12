"""CI/CD pipeline configuration parsers for GitHub Actions and GitLab CI.

Extracts structured representations from CI/CD config files for
compliance analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineStep:
    """A single step/command in a CI/CD job."""

    name: str = ""
    command: str = ""
    uses: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineJob:
    """A single job in a CI/CD pipeline."""

    name: str
    steps: list[PipelineStep] = field(default_factory=list)
    environment: str = ""
    needs_approval: bool = False
    runs_on: str = ""


@dataclass(frozen=True)
class CIPipelineConfig:
    """Structured representation of a CI/CD pipeline configuration."""

    source_file: str
    platform: str  # "github_actions" or "gitlab_ci"
    jobs: list[PipelineJob] = field(default_factory=list)
    secrets_referenced: list[str] = field(default_factory=list)
    has_security_scanning: bool = False
    has_dependency_scanning: bool = False
    has_test_step: bool = False
    has_deployment_step: bool = False
    has_approval_gate: bool = False
    has_artifact_signing: bool = False
    raw_config: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Security-related action/image patterns
# ---------------------------------------------------------------------------

_SECURITY_SCAN_PATTERNS = frozenset({
    "github/codeql-action",
    "aquasecurity/trivy-action",
    "snyk/actions",
    "securego/gosec",
    "bandit",
    "semgrep",
    "sonarqube",
    "sonar-scanner",
    "checkov",
    "tfsec",
    "sast",
    "dast",
})

_DEPENDENCY_SCAN_PATTERNS = frozenset({
    "dependency-check",
    "dependabot",
    "renovate",
    "pip-audit",
    "safety check",
    "npm audit",
    "yarn audit",
    "snyk test",
    "owasp",
    "grype",
})

_TEST_PATTERNS = frozenset({
    "pytest", "jest", "mocha", "junit", "go test", "cargo test",
    "mvn test", "gradle test", "npm test", "yarn test", "rspec",
})

_DEPLOY_PATTERNS = frozenset({
    "deploy", "kubectl apply", "helm upgrade", "terraform apply",
    "aws ecs", "gcloud deploy", "az deployment",
})

_SIGNING_PATTERNS = frozenset({
    "cosign", "sigstore", "gpg --sign", "sign", "notary",
})


# ---------------------------------------------------------------------------
# GitHub Actions parser
# ---------------------------------------------------------------------------


def parse_github_actions(path: Path) -> CIPipelineConfig:
    """Parse a GitHub Actions workflow YAML file.

    Args:
        path: Path to the workflow file (e.g. .github/workflows/ci.yml).

    Returns:
        A structured CIPipelineConfig.
    """
    yaml = YAML(typ="safe")
    raw: dict[str, Any] = yaml.load(path) or {}

    jobs: list[PipelineJob] = []
    all_secrets: list[str] = []
    has_security = False
    has_deps = False
    has_tests = False
    has_deploy = False
    has_approval = False
    has_signing = False

    for job_name, job_config in raw.get("jobs", {}).items():
        if not isinstance(job_config, dict):
            continue

        steps: list[PipelineStep] = []
        environment = ""
        needs_approval_gate = False

        env_block = job_config.get("environment", "")
        if isinstance(env_block, dict):
            environment = env_block.get("name", "")
            if env_block.get("url"):
                has_deploy = True
        elif isinstance(env_block, str):
            environment = env_block

        for step in job_config.get("steps", []):
            if not isinstance(step, dict):
                continue

            step_name = str(step.get("name", ""))
            uses = str(step.get("uses", ""))
            run_cmd = str(step.get("run", ""))
            env_vars = step.get("env", {}) or {}

            # Extract secret references
            for val in (list(env_vars.values()) if isinstance(env_vars, dict) else []):
                val_str = str(val)
                if "${{ secrets." in val_str:
                    secret_name = val_str.split("secrets.")[1].split("}")[0].strip()
                    all_secrets.append(secret_name)

            searchable = f"{step_name} {uses} {run_cmd}".lower()

            if _matches_any(searchable, _SECURITY_SCAN_PATTERNS):
                has_security = True
            if _matches_any(searchable, _DEPENDENCY_SCAN_PATTERNS):
                has_deps = True
            if _matches_any(searchable, _TEST_PATTERNS):
                has_tests = True
            if _matches_any(searchable, _DEPLOY_PATTERNS):
                has_deploy = True
            if _matches_any(searchable, _SIGNING_PATTERNS):
                has_signing = True

            steps.append(PipelineStep(
                name=step_name,
                command=run_cmd,
                uses=uses,
                env_vars=dict(env_vars) if isinstance(env_vars, dict) else {},
            ))

        # Environment protection rules imply approval
        if environment and isinstance(env_block, dict):
            needs_approval_gate = True
            has_approval = True

        jobs.append(PipelineJob(
            name=job_name,
            steps=steps,
            environment=environment,
            needs_approval=needs_approval_gate,
            runs_on=str(job_config.get("runs-on", "")),
        ))

    return CIPipelineConfig(
        source_file=str(path),
        platform="github_actions",
        jobs=jobs,
        secrets_referenced=list(set(all_secrets)),
        has_security_scanning=has_security,
        has_dependency_scanning=has_deps,
        has_test_step=has_tests,
        has_deployment_step=has_deploy,
        has_approval_gate=has_approval,
        has_artifact_signing=has_signing,
        raw_config=raw,
    )


# ---------------------------------------------------------------------------
# GitLab CI parser
# ---------------------------------------------------------------------------


def parse_gitlab_ci(path: Path) -> CIPipelineConfig:
    """Parse a GitLab CI YAML configuration file.

    Args:
        path: Path to .gitlab-ci.yml.

    Returns:
        A structured CIPipelineConfig.
    """
    yaml = YAML(typ="safe")
    raw: dict[str, Any] = yaml.load(path) or {}

    # Reserved GitLab CI keys (not job definitions)
    reserved_keys = frozenset({
        "stages", "variables", "default", "include", "workflow",
        "before_script", "after_script", "image", "services", "cache",
    })

    jobs: list[PipelineJob] = []
    all_secrets: list[str] = []
    has_security = False
    has_deps = False
    has_tests = False
    has_deploy = False
    has_approval = False
    has_signing = False

    # Extract variable references to CI/CD variables (secrets)
    variables = raw.get("variables", {})
    if isinstance(variables, dict):
        for val in variables.values():
            val_str = str(val)
            if val_str.startswith("$"):
                all_secrets.append(val_str.lstrip("$"))

    for key, value in raw.items():
        if key in reserved_keys or not isinstance(value, dict):
            continue
        if key.startswith("."):
            continue  # hidden/template jobs

        script_lines = value.get("script", [])
        if not isinstance(script_lines, list):
            script_lines = [str(script_lines)] if script_lines else []

        steps: list[PipelineStep] = []
        environment = ""
        needs_approval_gate = False

        env_block = value.get("environment", "")
        if isinstance(env_block, dict):
            environment = env_block.get("name", "")
            if env_block.get("action") == "manual" or value.get("when") == "manual":
                needs_approval_gate = True
                has_approval = True
        elif isinstance(env_block, str):
            environment = env_block

        if value.get("when") == "manual":
            needs_approval_gate = True
            has_approval = True

        image = str(value.get("image", ""))

        for line in script_lines:
            line_str = str(line)
            searchable = f"{key} {line_str} {image}".lower()

            if _matches_any(searchable, _SECURITY_SCAN_PATTERNS):
                has_security = True
            if _matches_any(searchable, _DEPENDENCY_SCAN_PATTERNS):
                has_deps = True
            if _matches_any(searchable, _TEST_PATTERNS):
                has_tests = True
            if _matches_any(searchable, _DEPLOY_PATTERNS):
                has_deploy = True
            if _matches_any(searchable, _SIGNING_PATTERNS):
                has_signing = True

            steps.append(PipelineStep(name=key, command=line_str))

        jobs.append(PipelineJob(
            name=key,
            steps=steps,
            environment=environment,
            needs_approval=needs_approval_gate,
        ))

    return CIPipelineConfig(
        source_file=str(path),
        platform="gitlab_ci",
        jobs=jobs,
        secrets_referenced=list(set(all_secrets)),
        has_security_scanning=has_security,
        has_dependency_scanning=has_deps,
        has_test_step=has_tests,
        has_deployment_step=has_deploy,
        has_approval_gate=has_approval,
        has_artifact_signing=has_signing,
        raw_config=raw,
    )


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def discover_pipeline_configs(repo_path: Path) -> list[CIPipelineConfig]:
    """Discover and parse all CI/CD configs in a repository.

    Args:
        repo_path: Root path of the repository.

    Returns:
        List of parsed pipeline configurations.
    """
    configs: list[CIPipelineConfig] = []

    # GitHub Actions
    gha_dir = repo_path / ".github" / "workflows"
    if gha_dir.is_dir():
        for pattern in ("*.yml", "*.yaml"):
            for wf in sorted(gha_dir.glob(pattern)):
                try:
                    configs.append(parse_github_actions(wf))
                except Exception:
                    logger.warning("Failed to parse GHA workflow: %s", wf, exc_info=True)

    # GitLab CI
    gitlab_ci = repo_path / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        try:
            configs.append(parse_gitlab_ci(gitlab_ci))
        except Exception:
            logger.warning("Failed to parse GitLab CI: %s", gitlab_ci, exc_info=True)

    return configs


def _matches_any(text: str, patterns: frozenset[str]) -> bool:
    """Check if text contains any of the patterns."""
    return any(p in text for p in patterns)
