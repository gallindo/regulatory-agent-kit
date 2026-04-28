"""PR review bot -- posts compliance scan results as PR comments.

Formats ``ScanResult`` objects from the compliance scanner as readable
markdown and posts them to GitHub PRs or GitLab MRs via their REST APIs.
Supports both creating new comments and updating existing ones (identified
by a hidden HTML marker).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from regulatory_agent_kit.ci.compliance_scanner import ScanResult

logger = logging.getLogger(__name__)

COMMENT_MARKER = "<!-- rak-compliance-scan -->"

_SEVERITY_ORDER = ["critical", "high", "medium", "low"]
_SEVERITY_ICONS: dict[str, str] = {
    "critical": "\U0001f534",
    "high": "\U0001f7e0",
    "medium": "\U0001f7e1",
    "low": "\U0001f535",
}


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------


def format_scan_as_markdown(result: ScanResult) -> str:
    """Format a ScanResult as a markdown PR comment.

    Args:
        result: The compliance scan result to format.

    Returns:
        A markdown string suitable for posting as a PR/MR comment.
    """
    lines: list[str] = [COMMENT_MARKER]

    if result.violation_count == 0:
        lines.append("## \u2705 Compliance Scan Passed")
        lines.append("")
        lines.append(f"**Regulation:** {result.regulation_name} (`{result.regulation_id}`)")
        lines.append(
            f"**Files scanned:** {result.files_scanned}"
            f" | **Rules checked:** {result.rules_checked}"
        )
        lines.append("")
        lines.append("No violations found.")
        return "\n".join(lines)

    lines.append("\u26a0\ufe0f Compliance Violations Found")
    lines.append("")
    lines.append(f"**Regulation:** {result.regulation_name} (`{result.regulation_id}`)")
    lines.append(
        f"**Files scanned:** {result.files_scanned}"
        f" | **Rules checked:** {result.rules_checked}"
        f" | **Violations:** {result.violation_count}"
    )
    lines.append("")

    # Group violations by severity
    by_severity: dict[str, list[Any]] = {}
    for v in result.violations:
        by_severity.setdefault(v.severity, []).append(v)

    for sev in _SEVERITY_ORDER:
        violations = by_severity.get(sev, [])
        if not violations:
            continue
        icon = _SEVERITY_ICONS.get(sev, "\u26aa")
        lines.append(f"### {icon} {sev.capitalize()} ({len(violations)})")
        lines.append("")
        lines.append("| File | Rule | Description |")
        lines.append("|------|------|-------------|")
        for v in violations:
            lines.append(f"| `{v.file_path}` | `{v.rule_id}` | {v.description} |")
        lines.append("")

    return "\n".join(lines)


def format_combined_markdown(
    result: ScanResult,
    pipeline_result: Any | None = None,
) -> str:
    """Format combined compliance scan + pipeline analysis as markdown.

    Args:
        result: The compliance scan result.
        pipeline_result: Optional PipelineAnalysisResult.

    Returns:
        Combined markdown string.
    """
    markdown = format_scan_as_markdown(result)

    if pipeline_result is not None:
        from regulatory_agent_kit.ci.pipeline_analyzer import (
            format_pipeline_analysis_as_markdown,
        )

        markdown += "\n\n---\n\n"
        markdown += format_pipeline_analysis_as_markdown(pipeline_result)

    return markdown


# ---------------------------------------------------------------------------
# Shared HTTP request helper
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT_SECONDS = 30


def _http_request(
    method: str,
    url: str,
    auth_headers: dict[str, str],
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated HTTP request returning parsed JSON.

    Used by both GitHub and GitLab reviewers — the only per-provider
    difference is the authentication header, which is supplied by the
    caller.
    """
    headers = {
        "Content-Type": "application/json",
        **auth_headers,
    }
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method=method)  # noqa: S310
    with urlopen(req, timeout=_REQUEST_TIMEOUT_SECONDS) as resp:  # noqa: S310
        result: dict[str, Any] = json.loads(resp.read().decode())
        return result


# ---------------------------------------------------------------------------
# GitHub PR reviewer
# ---------------------------------------------------------------------------


@dataclass
class GitHubPRReviewer:
    """Post compliance results as GitHub PR comments."""

    token: str = field(repr=False)
    api_url: str = "https://api.github.com"

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated GitHub API request."""
        return _http_request(
            method,
            url,
            auth_headers={
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
            },
            body=body,
        )

    def _find_existing_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> int | None:
        """Find an existing RAK comment on a PR.

        Returns:
            The comment ID if found, otherwise ``None``.
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        try:
            comments: list[dict[str, Any]] = self._request("GET", url)  # type: ignore[assignment]
        except HTTPError:
            return None
        for comment in comments:
            if COMMENT_MARKER in comment.get("body", ""):
                comment_id: int = comment["id"]
                return comment_id
        return None

    def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        result: ScanResult,
    ) -> dict[str, Any]:
        """Post or update a compliance scan comment on a GitHub PR.

        If a comment with the RAK marker already exists it is updated
        in-place; otherwise a new comment is created.

        Args:
            owner: Repository owner (user or organisation).
            repo: Repository name.
            pr_number: Pull request number.
            result: The compliance scan result.

        Returns:
            The GitHub API response dict for the created/updated comment.
        """
        body = format_scan_as_markdown(result)
        existing_id = self._find_existing_comment(owner, repo, pr_number)

        if existing_id is not None:
            url = f"{self.api_url}/repos/{owner}/{repo}/issues/comments/{existing_id}"
            return self._request("PATCH", url, {"body": body})

        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        return self._request("POST", url, {"body": body})


# ---------------------------------------------------------------------------
# GitLab MR reviewer
# ---------------------------------------------------------------------------


@dataclass
class GitLabPRReviewer:
    """Post compliance results as GitLab MR notes (comments)."""

    token: str = field(repr=False)
    api_url: str = "https://gitlab.com/api/v4"

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated GitLab API request."""
        return _http_request(
            method,
            url,
            auth_headers={"PRIVATE-TOKEN": self.token},
            body=body,
        )

    def _find_existing_note(
        self,
        project_id: str,
        mr_iid: int,
    ) -> int | None:
        """Find an existing RAK note on a MR.

        Returns:
            The note ID if found, otherwise ``None``.
        """
        url = f"{self.api_url}/projects/{project_id}/merge_requests/{mr_iid}/notes"
        try:
            notes: list[dict[str, Any]] = self._request("GET", url)  # type: ignore[assignment]
        except HTTPError:
            return None
        for note in notes:
            if COMMENT_MARKER in note.get("body", ""):
                note_id: int = note["id"]
                return note_id
        return None

    def post_review(
        self,
        project_id: str,
        mr_iid: int,
        result: ScanResult,
    ) -> dict[str, Any]:
        """Post or update a compliance scan note on a GitLab MR.

        If a note with the RAK marker already exists it is updated
        in-place; otherwise a new note is created.

        Args:
            project_id: URL-encoded GitLab project path or numeric ID.
            mr_iid: Merge request internal ID.
            result: The compliance scan result.

        Returns:
            The GitLab API response dict for the created/updated note.
        """
        body = format_scan_as_markdown(result)
        existing_id = self._find_existing_note(project_id, mr_iid)

        if existing_id is not None:
            url = (
                f"{self.api_url}/projects/{project_id}/merge_requests/{mr_iid}/notes/{existing_id}"
            )
            return self._request("PUT", url, {"body": body})

        url = f"{self.api_url}/projects/{project_id}/merge_requests/{mr_iid}/notes"
        return self._request("POST", url, {"body": body})
