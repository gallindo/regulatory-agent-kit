"""Tests for the PR review bot (ci.pr_reviewer)."""

from __future__ import annotations

import json
from http.client import HTTPResponse
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from regulatory_agent_kit.ci.compliance_scanner import ScanResult, Violation
from regulatory_agent_kit.ci.pr_reviewer import (
    COMMENT_MARKER,
    GitHubPRReviewer,
    GitLabPRReviewer,
    format_scan_as_markdown,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def passing_result() -> ScanResult:
    """A scan result with no violations."""
    return ScanResult(
        regulation_id="DORA-2025",
        regulation_name="DORA ICT Risk",
        violation_count=0,
        violations=[],
        files_scanned=5,
        rules_checked=10,
    )


@pytest.fixture()
def failing_result() -> ScanResult:
    """A scan result with violations of multiple severities."""
    return ScanResult(
        regulation_id="DORA-2025",
        regulation_name="DORA ICT Risk",
        violation_count=4,
        violations=[
            Violation(
                rule_id="DORA-001",
                severity="critical",
                description="Missing encryption at rest",
                file_path="src/db.py",
                pattern="**/*.py",
                condition="has_unencrypted_storage",
            ),
            Violation(
                rule_id="DORA-002",
                severity="high",
                description="No retry policy configured",
                file_path="src/api.py",
                pattern="**/*.py",
                condition="has_no_retry",
            ),
            Violation(
                rule_id="DORA-003",
                severity="medium",
                description="Logging PII fields",
                file_path="src/logger.py",
                pattern="**/*.py",
                condition="contains_pii_logging",
            ),
            Violation(
                rule_id="DORA-004",
                severity="low",
                description="Deprecated config format",
                file_path="config.yaml",
                pattern="**/*.yaml",
                condition="is_deprecated_format",
            ),
        ],
        files_scanned=4,
        rules_checked=8,
    )


def _mock_urlopen_response(body: dict[str, Any] | list[dict[str, Any]]) -> MagicMock:
    """Create a mock context-manager for urlopen returning *body* as JSON."""
    encoded = json.dumps(body).encode()
    mock_resp = MagicMock(spec=HTTPResponse)
    mock_resp.read.return_value = encoded
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# format_scan_as_markdown
# ---------------------------------------------------------------------------


class TestFormatScanAsMarkdown:
    """Tests for format_scan_as_markdown."""

    def test_marker_present_in_passing(self, passing_result: ScanResult) -> None:
        md = format_scan_as_markdown(passing_result)
        assert COMMENT_MARKER in md

    def test_marker_present_in_failing(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        assert COMMENT_MARKER in md

    def test_passing_shows_passed(self, passing_result: ScanResult) -> None:
        md = format_scan_as_markdown(passing_result)
        assert "Compliance Scan Passed" in md
        assert "No violations found." in md

    def test_passing_shows_regulation(self, passing_result: ScanResult) -> None:
        md = format_scan_as_markdown(passing_result)
        assert "DORA ICT Risk" in md
        assert "`DORA-2025`" in md

    def test_passing_shows_stats(self, passing_result: ScanResult) -> None:
        md = format_scan_as_markdown(passing_result)
        assert "**Files scanned:** 5" in md
        assert "**Rules checked:** 10" in md

    def test_failing_shows_violations_header(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        assert "Compliance Violations Found" in md

    def test_failing_shows_violation_count(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        assert "**Violations:** 4" in md

    def test_failing_groups_by_severity(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        assert "Critical (1)" in md
        assert "High (1)" in md
        assert "Medium (1)" in md
        assert "Low (1)" in md

    def test_failing_severity_order(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        crit_pos = md.index("Critical")
        high_pos = md.index("High")
        med_pos = md.index("Medium")
        low_pos = md.index("Low")
        assert crit_pos < high_pos < med_pos < low_pos

    def test_failing_shows_violation_details(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        assert "`src/db.py`" in md
        assert "`DORA-001`" in md
        assert "Missing encryption at rest" in md

    def test_failing_contains_table_headers(self, failing_result: ScanResult) -> None:
        md = format_scan_as_markdown(failing_result)
        assert "| File | Rule | Description |" in md


# ---------------------------------------------------------------------------
# GitHubPRReviewer
# ---------------------------------------------------------------------------


class TestGitHubPRReviewer:
    """Tests for GitHubPRReviewer."""

    def test_creates_new_comment(self, passing_result: ScanResult) -> None:
        reviewer = GitHubPRReviewer(token="gh-token-123")  # noqa: S106

        # No existing comments
        empty_comments_resp = _mock_urlopen_response([])
        created_resp = _mock_urlopen_response({"id": 999, "body": "ok"})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [empty_comments_resp, created_resp]
            result = reviewer.post_review("owner", "repo", 42, passing_result)

        assert result == {"id": 999, "body": "ok"}
        assert mock_urlopen.call_count == 2

        # Verify the POST request
        post_call = mock_urlopen.call_args_list[1]
        req = post_call[0][0]
        assert req.method == "POST"
        assert "/issues/42/comments" in req.full_url
        body = json.loads(req.data.decode())
        assert COMMENT_MARKER in body["body"]

    def test_updates_existing_comment(self, failing_result: ScanResult) -> None:
        reviewer = GitHubPRReviewer(token="gh-token-123")  # noqa: S106

        existing_comments = [
            {"id": 100, "body": "unrelated comment"},
            {"id": 200, "body": f"old scan {COMMENT_MARKER}"},
        ]
        existing_resp = _mock_urlopen_response(existing_comments)
        updated_resp = _mock_urlopen_response({"id": 200, "body": "updated"})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [existing_resp, updated_resp]
            result = reviewer.post_review("owner", "repo", 7, failing_result)

        assert result == {"id": 200, "body": "updated"}

        # Verify the PATCH request targets the existing comment
        patch_call = mock_urlopen.call_args_list[1]
        req = patch_call[0][0]
        assert req.method == "PATCH"
        assert "/issues/comments/200" in req.full_url

    def test_auth_header(self, passing_result: ScanResult) -> None:
        reviewer = GitHubPRReviewer(token="my-secret-token")  # noqa: S106

        empty_resp = _mock_urlopen_response([])
        created_resp = _mock_urlopen_response({"id": 1})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [empty_resp, created_resp]
            reviewer.post_review("o", "r", 1, passing_result)

        req = mock_urlopen.call_args_list[0][0][0]
        assert req.get_header("Authorization") == "token my-secret-token"

    def test_custom_api_url(self, passing_result: ScanResult) -> None:
        reviewer = GitHubPRReviewer(
            token="t",  # noqa: S106
            api_url="https://github.example.com/api/v3",
        )

        empty_resp = _mock_urlopen_response([])
        created_resp = _mock_urlopen_response({"id": 1})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [empty_resp, created_resp]
            reviewer.post_review("o", "r", 1, passing_result)

        req = mock_urlopen.call_args_list[0][0][0]
        assert req.full_url.startswith("https://github.example.com/api/v3")


# ---------------------------------------------------------------------------
# GitLabPRReviewer
# ---------------------------------------------------------------------------


class TestGitLabPRReviewer:
    """Tests for GitLabPRReviewer."""

    def test_creates_new_note(self, passing_result: ScanResult) -> None:
        reviewer = GitLabPRReviewer(token="gl-token-456")  # noqa: S106

        empty_notes_resp = _mock_urlopen_response([])
        created_resp = _mock_urlopen_response({"id": 888, "body": "created"})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [empty_notes_resp, created_resp]
            result = reviewer.post_review("my%2Fproject", 10, passing_result)

        assert result == {"id": 888, "body": "created"}
        assert mock_urlopen.call_count == 2

        post_call = mock_urlopen.call_args_list[1]
        req = post_call[0][0]
        assert req.method == "POST"
        assert "/merge_requests/10/notes" in req.full_url

    def test_updates_existing_note(self, failing_result: ScanResult) -> None:
        reviewer = GitLabPRReviewer(token="gl-token-456")  # noqa: S106

        existing_notes = [
            {"id": 300, "body": f"previous {COMMENT_MARKER}"},
        ]
        existing_resp = _mock_urlopen_response(existing_notes)
        updated_resp = _mock_urlopen_response({"id": 300, "body": "updated"})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [existing_resp, updated_resp]
            result = reviewer.post_review("proj", 5, failing_result)

        assert result == {"id": 300, "body": "updated"}

        put_call = mock_urlopen.call_args_list[1]
        req = put_call[0][0]
        assert req.method == "PUT"
        assert "/notes/300" in req.full_url

    def test_auth_header(self, passing_result: ScanResult) -> None:
        reviewer = GitLabPRReviewer(token="private-token-xyz")  # noqa: S106

        empty_resp = _mock_urlopen_response([])
        created_resp = _mock_urlopen_response({"id": 1})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [empty_resp, created_resp]
            reviewer.post_review("p", 1, passing_result)

        req = mock_urlopen.call_args_list[0][0][0]
        assert req.get_header("Private-token") == "private-token-xyz"

    def test_custom_api_url(self, passing_result: ScanResult) -> None:
        reviewer = GitLabPRReviewer(
            token="t",  # noqa: S106
            api_url="https://gitlab.internal.com/api/v4",
        )

        empty_resp = _mock_urlopen_response([])
        created_resp = _mock_urlopen_response({"id": 1})

        with patch(
            "regulatory_agent_kit.ci.pr_reviewer.urlopen",
        ) as mock_urlopen:
            mock_urlopen.side_effect = [empty_resp, created_resp]
            reviewer.post_review("p", 1, passing_result)

        req = mock_urlopen.call_args_list[0][0][0]
        assert req.full_url.startswith("https://gitlab.internal.com/api/v4")
