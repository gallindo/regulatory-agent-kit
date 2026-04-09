"""Tests for CI/CD pipeline analysis — parser, checks, and analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.ci.pipeline_analyzer import (
    analyze_pipelines,
    format_pipeline_analysis_as_markdown,
)
from regulatory_agent_kit.ci.pipeline_checks import PIPELINE_CHECKS
from regulatory_agent_kit.ci.pipeline_parser import (
    parse_github_actions,
    parse_gitlab_ci,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ci"


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestGitHubActionsParser:
    def test_parse_good_workflow(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_good.yml")
        assert config.platform == "github_actions"
        assert len(config.jobs) == 2
        assert config.has_test_step
        assert config.has_security_scanning
        assert config.has_dependency_scanning
        assert config.has_deployment_step
        assert config.has_approval_gate
        assert config.has_artifact_signing

    def test_parse_bad_workflow(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_bad.yml")
        assert config.platform == "github_actions"
        assert len(config.jobs) == 1
        assert not config.has_test_step
        assert not config.has_security_scanning
        assert not config.has_dependency_scanning
        assert not config.has_deployment_step

    def test_extracts_secrets(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_good.yml")
        assert len(config.secrets_referenced) > 0
        assert "KUBE_TOKEN" in config.secrets_referenced

    def test_job_names(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_good.yml")
        job_names = [j.name for j in config.jobs]
        assert "test" in job_names
        assert "deploy" in job_names


class TestGitLabCIParser:
    def test_parse_good_config(self) -> None:
        config = parse_gitlab_ci(FIXTURES / "gitlab_ci_good.yml")
        assert config.platform == "gitlab_ci"
        assert len(config.jobs) >= 2
        assert config.has_test_step
        assert config.has_security_scanning
        assert config.has_dependency_scanning
        assert config.has_approval_gate

    def test_parse_bad_config(self) -> None:
        config = parse_gitlab_ci(FIXTURES / "gitlab_ci_bad.yml")
        assert config.platform == "gitlab_ci"
        assert not config.has_test_step
        assert not config.has_security_scanning


# ---------------------------------------------------------------------------
# Check tests
# ---------------------------------------------------------------------------


class TestPipelineChecks:
    def test_all_checks_pass_on_good_workflow(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_good.yml")
        results = [check.check_fn(config) for check in PIPELINE_CHECKS]
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0, f"Unexpected failures: {[f.check_id for f in failed]}"

    def test_checks_fail_on_bad_workflow(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_bad.yml")
        results = [check.check_fn(config) for check in PIPELINE_CHECKS]
        failed = [r for r in results if not r.passed]
        assert len(failed) >= 3  # No tests, no security scan, no dep scan

    def test_hardcoded_secrets_check(self) -> None:
        config = parse_github_actions(FIXTURES / "github_actions_good.yml")
        secrets_check = next(c for c in PIPELINE_CHECKS if c.check_id == "PIPE-005")
        result = secrets_check.check_fn(config)
        assert result.passed  # Good workflow uses ${{ secrets.* }}

    def test_check_count(self) -> None:
        assert len(PIPELINE_CHECKS) == 6


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------


class TestPipelineAnalyzer:
    def test_analyze_repo_with_gha(self, tmp_path: Path) -> None:
        """Analyze a repo with a GitHub Actions workflow."""
        gha_dir = tmp_path / ".github" / "workflows"
        gha_dir.mkdir(parents=True)

        good_wf = FIXTURES / "github_actions_good.yml"
        (gha_dir / "ci.yml").write_text(good_wf.read_text())

        result = analyze_pipelines(tmp_path)
        assert result.pipelines_analyzed == 1
        assert result.checks_run >= 6
        assert result.checks_failed == 0

    def test_analyze_repo_without_ci(self, tmp_path: Path) -> None:
        """Analyze a repo with no CI/CD configs."""
        result = analyze_pipelines(tmp_path)
        assert result.pipelines_analyzed == 0
        assert result.checks_run == 0

    def test_analyze_repo_with_bad_ci(self, tmp_path: Path) -> None:
        """Analyze a repo with a minimal (bad) workflow."""
        gha_dir = tmp_path / ".github" / "workflows"
        gha_dir.mkdir(parents=True)

        bad_wf = FIXTURES / "github_actions_bad.yml"
        (gha_dir / "ci.yml").write_text(bad_wf.read_text())

        result = analyze_pipelines(tmp_path)
        assert result.pipelines_analyzed == 1
        assert result.checks_failed >= 3

    def test_to_dict(self, tmp_path: Path) -> None:
        result = analyze_pipelines(tmp_path)
        d = result.to_dict()
        assert "pipelines_analyzed" in d
        assert "findings" in d
        assert isinstance(d["findings"], list)


# ---------------------------------------------------------------------------
# Markdown formatting tests
# ---------------------------------------------------------------------------


class TestMarkdownFormatting:
    def test_format_passing_result(self, tmp_path: Path) -> None:
        gha_dir = tmp_path / ".github" / "workflows"
        gha_dir.mkdir(parents=True)
        good_wf = FIXTURES / "github_actions_good.yml"
        (gha_dir / "ci.yml").write_text(good_wf.read_text())

        result = analyze_pipelines(tmp_path)
        md = format_pipeline_analysis_as_markdown(result)
        assert "CI/CD Pipeline Analysis" in md
        assert "passed" in md

    def test_format_failing_result(self, tmp_path: Path) -> None:
        gha_dir = tmp_path / ".github" / "workflows"
        gha_dir.mkdir(parents=True)
        bad_wf = FIXTURES / "github_actions_bad.yml"
        (gha_dir / "ci.yml").write_text(bad_wf.read_text())

        result = analyze_pipelines(tmp_path)
        md = format_pipeline_analysis_as_markdown(result)
        assert "PIPE-" in md
        assert "HIGH" in md
