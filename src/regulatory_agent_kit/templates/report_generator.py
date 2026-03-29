"""Compliance report generator — renders HTML reports, audit logs, and rollback manifests.

Produces the three artefacts described in data-model.md Section 7.1:
  compliance-reports/{run_id}/report.html
  compliance-reports/{run_id}/audit-log.jsonld
  compliance-reports/{run_id}/rollback-manifest.json
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from regulatory_agent_kit.templates.engine import TemplateEngine

logger = logging.getLogger(__name__)

# Path to the built-in HTML report template relative to this file.
_TEMPLATE_DIR = Path(__file__).parent / "reports"
_DEFAULT_TEMPLATE = _TEMPLATE_DIR / "compliance_report.html.j2"

# Package version injected into reports.
_VERSION = "0.1.0"


class ComplianceReportGenerator:
    """Generates HTML compliance reports, audit log exports, and rollback manifests.

    All outputs are written to a directory following the bucket structure
    from data-model.md Section 7.1::

        {output_dir}/{run_id}/report.html
        {output_dir}/{run_id}/audit-log.jsonld
        {output_dir}/{run_id}/rollback-manifest.json
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        template_path: Path | None = None,
    ) -> None:
        self._output_dir = output_dir or Path("compliance-reports")
        self._template_path = template_path or _DEFAULT_TEMPLATE
        self._engine = TemplateEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        *,
        run_id: str,
        regulation_id: str,
        status: str,
        repos: list[dict[str, Any]],
        cost_estimate: dict[str, Any] | None = None,
        checkpoint_decisions: list[dict[str, Any]] | None = None,
        conflicts: list[dict[str, Any]] | None = None,
        pr_urls: list[str] | None = None,
        audit_entries: list[dict[str, Any]] | None = None,
    ) -> ReportArtefacts:
        """Generate all compliance artefacts for a pipeline run.

        Args:
            run_id: Pipeline run identifier.
            regulation_id: Plugin ID for the regulation.
            status: Terminal pipeline status.
            repos: Per-repository result dicts from the pipeline.
            cost_estimate: Cost estimation data (optional).
            checkpoint_decisions: Human checkpoint decisions (optional).
            conflicts: Cross-regulation conflicts (optional).
            pr_urls: Pull request URLs created (optional).
            audit_entries: Audit trail entries for export (optional).

        Returns:
            A ``ReportArtefacts`` with paths to all generated files.
        """
        run_dir = self._output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        report_path = self._render_html(
            run_dir=run_dir,
            run_id=run_id,
            regulation_id=regulation_id,
            status=status,
            repos=repos,
            cost_estimate=cost_estimate,
            checkpoint_decisions=checkpoint_decisions or [],
            conflicts=conflicts or [],
            pr_urls=pr_urls or [],
        )

        audit_log_path = self._write_audit_log(
            run_dir=run_dir,
            audit_entries=audit_entries or [],
        )

        rollback_path = self._write_rollback_manifest(
            run_dir=run_dir,
            run_id=run_id,
            repos=repos,
        )

        logger.info("Compliance report generated at %s", run_dir)
        return ReportArtefacts(
            report_path=report_path,
            audit_log_path=audit_log_path,
            rollback_manifest_path=rollback_path,
        )

    # ------------------------------------------------------------------
    # HTML report
    # ------------------------------------------------------------------

    def _render_html(
        self,
        *,
        run_dir: Path,
        run_id: str,
        regulation_id: str,
        status: str,
        repos: list[dict[str, Any]],
        cost_estimate: dict[str, Any] | None,
        checkpoint_decisions: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        pr_urls: list[str],
    ) -> Path:
        """Render the HTML compliance report from the Jinja2 template."""
        context: dict[str, Any] = {
            "run_id": run_id,
            "regulation_id": regulation_id,
            "status": status,
            "repos": repos,
            "cost_estimate": cost_estimate,
            "checkpoint_decisions": checkpoint_decisions,
            "conflicts": conflicts,
            "pr_urls": pr_urls,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "version": _VERSION,
        }
        html = self._engine.render(self._template_path, context)
        report_path = run_dir / "report.html"
        report_path.write_text(html, encoding="utf-8")
        return report_path

    # ------------------------------------------------------------------
    # Audit log export (JSONL with JSON-LD payloads)
    # ------------------------------------------------------------------

    @staticmethod
    def _write_audit_log(
        *,
        run_dir: Path,
        audit_entries: list[dict[str, Any]],
    ) -> Path:
        """Write audit entries as newline-delimited JSON (JSONL)."""
        audit_path = run_dir / "audit-log.jsonld"
        lines = [json.dumps(e, default=str) for e in audit_entries]
        audit_path.write_text(
            "\n".join(lines) + ("\n" if lines else ""),
            encoding="utf-8",
        )
        return audit_path

    # ------------------------------------------------------------------
    # Rollback manifest
    # ------------------------------------------------------------------

    @staticmethod
    def _write_rollback_manifest(
        *,
        run_dir: Path,
        run_id: str,
        repos: list[dict[str, Any]],
    ) -> Path:
        """Write the rollback manifest as JSON.

        Follows the format from cli-reference.md: each repo entry includes
        repo_url, branch_name, commit_sha, pr_url, pr_state, files_changed.
        """
        manifest_repos: list[dict[str, Any]] = []
        for repo in repos:
            cs = repo.get("change_set") or {}
            manifest_repos.append({
                "repo_url": repo.get("repo_url", ""),
                "branch_name": cs.get("branch_name", ""),
                "commit_sha": cs.get("commit_sha", ""),
                "pr_url": repo.get("pr_url", ""),
                "pr_state": repo.get("pr_state", "open"),
                "files_changed": [
                    d.get("file_path", "") for d in cs.get("diffs", [])
                ],
            })

        manifest = {
            "run_id": run_id,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "repos": manifest_repos,
        }
        manifest_path = run_dir / "rollback-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return manifest_path


class ReportArtefacts:
    """Paths to all generated compliance report artefacts."""

    def __init__(
        self,
        report_path: Path,
        audit_log_path: Path,
        rollback_manifest_path: Path,
    ) -> None:
        self.report_path = report_path
        self.audit_log_path = audit_log_path
        self.rollback_manifest_path = rollback_manifest_path

    def to_report_bundle_dict(self) -> dict[str, str]:
        """Return paths as a dict suitable for ``ReportBundle`` construction."""
        return {
            "report_path": str(self.report_path),
            "audit_log_path": str(self.audit_log_path),
            "rollback_manifest_path": str(self.rollback_manifest_path),
        }
