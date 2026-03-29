"""Tests for ComplianceReportGenerator."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Any

from regulatory_agent_kit.templates.report_generator import (
    ComplianceReportGenerator,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_RUN_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_REGULATION_ID = "example-regulation-2025"


def _sample_repos() -> list[dict[str, Any]]:
    return [
        {
            "repo_url": "https://github.com/org/service-a",
            "status": "completed",
            "impact_map": {
                "files": [
                    {"file_path": "src/Main.java", "matched_rules": [{"rule_id": "EX-001"}]},
                ],
                "conflicts": [],
                "analysis_confidence": 0.9,
            },
            "change_set": {
                "branch_name": "rak/example-regulation-2025/EX-001",
                "diffs": [
                    {"file_path": "src/Main.java", "rule_id": "EX-001",
                     "diff_content": "+@AuditLog", "confidence": 0.95,
                     "strategy_used": "add_annotation"},
                ],
                "confidence_scores": [0.95],
                "commit_sha": "abc123def456",
            },
            "test_result": {
                "pass_rate": 1.0,
                "total_tests": 3,
                "passed": 3,
                "failed": 0,
                "failures": [],
                "test_files_created": ["tests/test_audit.java"],
            },
            "pr_url": "https://github.com/org/service-a/pull/42",
        },
        {
            "repo_url": "https://github.com/org/service-b",
            "status": "failed",
            "impact_map": {"files": [], "conflicts": [], "analysis_confidence": 0.85},
            "change_set": {},
            "test_result": {},
        },
    ]


def _sample_decisions() -> list[dict[str, Any]]:
    return [
        {
            "checkpoint_type": "impact_review",
            "decision": "approved",
            "actor": "alice@example.com",
            "rationale": "LGTM",
        },
        {
            "checkpoint_type": "merge_review",
            "decision": "approved",
            "actor": "bob@example.com",
            "rationale": None,
        },
    ]


def _sample_audit_entries() -> list[dict[str, Any]]:
    return [
        {"@context": "https://schema.org", "@type": "LLMCall", "model": "claude"},
        {"@context": "https://schema.org", "@type": "StateTransition", "phase": "ANALYZING"},
    ]


# ------------------------------------------------------------------
# HTML report
# ------------------------------------------------------------------


class TestHtmlReport:
    def test_generates_html_file(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        assert artefacts.report_path.exists()
        assert artefacts.report_path.name == "report.html"

    def test_html_contains_run_id(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert _RUN_ID in html

    def test_html_contains_regulation_id(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert _REGULATION_ID in html

    def test_html_contains_repo_urls(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert "service-a" in html
        assert "service-b" in html

    def test_html_contains_status_badges(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert "badge-ok" in html  # completed status
        assert "badge-err" in html  # failed repo

    def test_html_contains_checkpoint_decisions(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
            checkpoint_decisions=_sample_decisions(),
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert "alice@example.com" in html
        assert "impact_review" in html

    def test_html_contains_cost_estimate(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
            cost_estimate={"estimated_total_cost": 3.0},
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert "$3.0000" in html

    def test_html_contains_pr_urls(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
            pr_urls=["https://github.com/org/service-a/pull/42"],
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert "https://github.com/org/service-a/pull/42" in html

    def test_html_is_valid_document(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_html_contains_conflict_section(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        conflicts = [
            {
                "conflicting_rule_ids": ["DORA-001", "GDPR-003"],
                "description": "Conflicting logging requirements",
                "resolution": None,
            },
        ]
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
            conflicts=conflicts,
        )
        html = artefacts.report_path.read_text(encoding="utf-8")
        assert "DORA-001" in html
        assert "GDPR-003" in html


# ------------------------------------------------------------------
# Audit log export
# ------------------------------------------------------------------


class TestAuditLogExport:
    def test_generates_jsonld_file(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
            audit_entries=_sample_audit_entries(),
        )
        assert artefacts.audit_log_path.exists()
        assert artefacts.audit_log_path.name == "audit-log.jsonld"

    def test_audit_log_is_jsonl(self, tmp_path: Path) -> None:
        entries = _sample_audit_entries()
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
            audit_entries=entries,
        )
        lines = artefacts.audit_log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == len(entries)
        for line in lines:
            parsed = json.loads(line)
            assert "@context" in parsed

    def test_empty_audit_log(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
        )
        assert artefacts.audit_log_path.exists()
        content = artefacts.audit_log_path.read_text(encoding="utf-8")
        assert content == ""


# ------------------------------------------------------------------
# Rollback manifest
# ------------------------------------------------------------------


class TestRollbackManifest:
    def test_generates_manifest_file(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        assert artefacts.rollback_manifest_path.exists()
        assert artefacts.rollback_manifest_path.name == "rollback-manifest.json"

    def test_manifest_contains_run_id(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        manifest = json.loads(
            artefacts.rollback_manifest_path.read_text(encoding="utf-8")
        )
        assert manifest["run_id"] == _RUN_ID

    def test_manifest_repos_match_input(self, tmp_path: Path) -> None:
        repos = _sample_repos()
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=repos,
        )
        manifest = json.loads(
            artefacts.rollback_manifest_path.read_text(encoding="utf-8")
        )
        assert len(manifest["repos"]) == len(repos)
        assert manifest["repos"][0]["repo_url"] == repos[0]["repo_url"]

    def test_manifest_includes_branch_and_commit(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        manifest = json.loads(
            artefacts.rollback_manifest_path.read_text(encoding="utf-8")
        )
        first_repo = manifest["repos"][0]
        assert first_repo["branch_name"] == "rak/example-regulation-2025/EX-001"
        assert first_repo["commit_sha"] == "abc123def456"

    def test_manifest_includes_files_changed(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        manifest = json.loads(
            artefacts.rollback_manifest_path.read_text(encoding="utf-8")
        )
        assert manifest["repos"][0]["files_changed"] == ["src/Main.java"]


# ------------------------------------------------------------------
# Directory structure
# ------------------------------------------------------------------


class TestDirectoryStructure:
    def test_creates_run_subdirectory(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
        )
        run_dir = tmp_path / _RUN_ID
        assert run_dir.is_dir()
        assert (run_dir / "report.html").exists()
        assert (run_dir / "audit-log.jsonld").exists()
        assert (run_dir / "rollback-manifest.json").exists()


# ------------------------------------------------------------------
# ReportArtefacts
# ------------------------------------------------------------------


class TestReportArtefacts:
    def test_to_report_bundle_dict(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
        )
        bundle = artefacts.to_report_bundle_dict()
        assert "report_path" in bundle
        assert "audit_log_path" in bundle
        assert "rollback_manifest_path" in bundle
        assert bundle["report_path"].endswith("report.html")
