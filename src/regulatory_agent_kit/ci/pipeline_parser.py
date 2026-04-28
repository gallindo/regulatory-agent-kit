"""CI/CD pipeline configuration parsers for GitHub Actions and GitLab CI.

Extracts structured representations from CI/CD config files for
compliance analysis.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
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

_SECURITY_SCAN_PATTERNS = frozenset(
    {
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
    }
)

_DEPENDENCY_SCAN_PATTERNS = frozenset(
    {
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
    }
)

_TEST_PATTERNS = frozenset(
    {
        "pytest",
        "jest",
        "mocha",
        "junit",
        "go test",
        "cargo test",
        "mvn test",
        "gradle test",
        "npm test",
        "yarn test",
        "rspec",
    }
)

_DEPLOY_PATTERNS = frozenset(
    {
        "deploy",
        "kubectl apply",
        "helm upgrade",
        "terraform apply",
        "aws ecs",
        "gcloud deploy",
        "az deployment",
    }
)

_SIGNING_PATTERNS = frozenset(
    {
        "cosign",
        "sigstore",
        "gpg --sign",
        "sign",
        "notary",
    }
)

# GitLab CI top-level keys that are not job definitions.
_GITLAB_RESERVED_KEYS = frozenset(
    {
        "stages",
        "variables",
        "default",
        "include",
        "workflow",
        "before_script",
        "after_script",
        "image",
        "services",
        "cache",
    }
)

# Feature flags accumulated by scanning CI step text.
_FEATURE_FLAG_PATTERNS: tuple[tuple[str, frozenset[str]], ...] = (
    ("has_security_scanning", _SECURITY_SCAN_PATTERNS),
    ("has_dependency_scanning", _DEPENDENCY_SCAN_PATTERNS),
    ("has_test_step", _TEST_PATTERNS),
    ("has_deployment_step", _DEPLOY_PATTERNS),
    ("has_artifact_signing", _SIGNING_PATTERNS),
)


def _new_feature_flags() -> dict[str, bool]:
    """Return a fresh dict of feature flags (all False) plus approval gate."""
    flags = {name: False for name, _ in _FEATURE_FLAG_PATTERNS}
    flags["has_approval_gate"] = False
    return flags


def _update_feature_flags(searchable: str, flags: dict[str, bool]) -> None:
    """Turn on any flag whose pattern set matches *searchable*."""
    for flag_name, patterns in _FEATURE_FLAG_PATTERNS:
        if not flags[flag_name] and _matches_any(searchable, patterns):
            flags[flag_name] = True


def _build_config(
    path: Path,
    platform: str,
    jobs: list[PipelineJob],
    secrets: list[str],
    flags: dict[str, bool],
    raw: dict[str, Any],
) -> CIPipelineConfig:
    """Assemble a CIPipelineConfig from per-parser collected state."""
    return CIPipelineConfig(
        source_file=str(path),
        platform=platform,
        jobs=jobs,
        secrets_referenced=list(set(secrets)),
        has_security_scanning=flags["has_security_scanning"],
        has_dependency_scanning=flags["has_dependency_scanning"],
        has_test_step=flags["has_test_step"],
        has_deployment_step=flags["has_deployment_step"],
        has_approval_gate=flags["has_approval_gate"],
        has_artifact_signing=flags["has_artifact_signing"],
        raw_config=raw,
    )


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
    flags = _new_feature_flags()

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
                flags["has_deployment_step"] = True
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
            for val in list(env_vars.values()) if isinstance(env_vars, dict) else []:
                val_str = str(val)
                if "${{ secrets." in val_str:
                    secret_name = val_str.split("secrets.")[1].split("}")[0].strip()
                    all_secrets.append(secret_name)

            searchable = f"{step_name} {uses} {run_cmd}".lower()
            _update_feature_flags(searchable, flags)

            steps.append(
                PipelineStep(
                    name=step_name,
                    command=run_cmd,
                    uses=uses,
                    env_vars=dict(env_vars) if isinstance(env_vars, dict) else {},
                )
            )

        # Environment protection rules imply approval
        if environment and isinstance(env_block, dict):
            needs_approval_gate = True
            flags["has_approval_gate"] = True

        jobs.append(
            PipelineJob(
                name=job_name,
                steps=steps,
                environment=environment,
                needs_approval=needs_approval_gate,
                runs_on=str(job_config.get("runs-on", "")),
            )
        )

    return _build_config(path, "github_actions", jobs, all_secrets, flags, raw)


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

    jobs: list[PipelineJob] = []
    all_secrets: list[str] = []
    flags = _new_feature_flags()

    # Extract variable references to CI/CD variables (secrets)
    variables = raw.get("variables", {})
    if isinstance(variables, dict):
        for val in variables.values():
            val_str = str(val)
            if val_str.startswith("$"):
                all_secrets.append(val_str.lstrip("$"))

    for key, value in raw.items():
        if key in _GITLAB_RESERVED_KEYS or not isinstance(value, dict):
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
                flags["has_approval_gate"] = True
        elif isinstance(env_block, str):
            environment = env_block

        if value.get("when") == "manual":
            needs_approval_gate = True
            flags["has_approval_gate"] = True

        image = str(value.get("image", ""))

        for line in script_lines:
            line_str = str(line)
            searchable = f"{key} {line_str} {image}".lower()
            _update_feature_flags(searchable, flags)

            steps.append(PipelineStep(name=key, command=line_str))

        jobs.append(
            PipelineJob(
                name=key,
                steps=steps,
                environment=environment,
                needs_approval=needs_approval_gate,
            )
        )

    return _build_config(path, "gitlab_ci", jobs, all_secrets, flags, raw)


# ---------------------------------------------------------------------------
# Parser registry (Open/Closed)
# ---------------------------------------------------------------------------


ParserFn = Callable[[Path], CIPipelineConfig]


@dataclass(frozen=True)
class PipelineParserSpec:
    """A registered CI/CD parser and how to discover its config files.

    The registry uses ``relative_dir`` + ``file_patterns`` to locate
    candidate files, or ``relative_files`` for single fixed-name files
    (e.g. ``.gitlab-ci.yml``).
    """

    platform: str
    parser: ParserFn
    relative_dir: str = ""
    file_patterns: tuple[str, ...] = ()
    relative_files: tuple[str, ...] = ()


PIPELINE_PARSERS: list[PipelineParserSpec] = [
    PipelineParserSpec(
        platform="github_actions",
        parser=parse_github_actions,
        relative_dir=".github/workflows",
        file_patterns=("*.yml", "*.yaml"),
    ),
    PipelineParserSpec(
        platform="gitlab_ci",
        parser=parse_gitlab_ci,
        relative_files=(".gitlab-ci.yml",),
    ),
]


def register_parser(spec: PipelineParserSpec) -> None:
    """Register a new CI/CD parser.

    New platforms (CircleCI, Azure Pipelines, etc.) can be added without
    modifying :func:`discover_pipeline_configs`.
    """
    PIPELINE_PARSERS.append(spec)


def _iter_candidate_paths(repo_path: Path, spec: PipelineParserSpec) -> Iterator[Path]:
    """Yield files in *repo_path* that match *spec*."""
    if spec.relative_dir and spec.file_patterns:
        target_dir = repo_path / spec.relative_dir
        if target_dir.is_dir():
            for pattern in spec.file_patterns:
                yield from sorted(target_dir.glob(pattern))
    for rel_file in spec.relative_files:
        candidate = repo_path / rel_file
        if candidate.exists():
            yield candidate


def discover_pipeline_configs(repo_path: Path) -> list[CIPipelineConfig]:
    """Discover and parse all CI/CD configs in a repository.

    Iterates over every parser registered in :data:`PIPELINE_PARSERS`.
    """
    configs: list[CIPipelineConfig] = []
    for spec in PIPELINE_PARSERS:
        for path in _iter_candidate_paths(repo_path, spec):
            try:
                configs.append(spec.parser(path))
            except Exception:
                logger.warning(
                    "Failed to parse %s config: %s",
                    spec.platform,
                    path,
                    exc_info=True,
                )
    return configs


def _matches_any(text: str, patterns: frozenset[str]) -> bool:
    """Check if text contains any of the patterns."""
    return any(p in text for p in patterns)
