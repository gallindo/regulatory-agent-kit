"""Tests for PDF report generation in ComplianceReportGenerator."""

from __future__ import annotations

import sys
from pathlib import Path  # noqa: TC003
from typing import Any
from unittest.mock import MagicMock, patch

from regulatory_agent_kit.templates.report_generator import (
    ComplianceReportGenerator,
    _write_text_pdf,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_RUN_ID = "pdf-test-run-0001"
_REGULATION_ID = "example-regulation-2025"


def _minimal_html(tmp_path: Path) -> Path:
    """Write a small HTML file and return its path."""
    html_path = tmp_path / "report.html"
    html_path.write_text(
        "<!DOCTYPE html><html><body>"
        "<h1>Compliance Report</h1>"
        "<p>Status: completed</p>"
        "</body></html>",
        encoding="utf-8",
    )
    return html_path


def _sample_repos() -> list[dict[str, Any]]:
    return [
        {
            "repo_url": "https://github.com/org/service-a",
            "status": "completed",
            "impact_map": {
                "files": [],
                "conflicts": [],
                "analysis_confidence": 0.9,
            },
            "change_set": {
                "branch_name": "rak/reg/R-001",
                "diffs": [
                    {
                        "file_path": "src/Main.java",
                        "rule_id": "R-001",
                        "diff_content": "+@Audit",
                        "confidence": 0.95,
                        "strategy_used": "add_annotation",
                    },
                ],
                "confidence_scores": [0.95],
                "commit_sha": "deadbeef",
            },
            "test_result": {},
        },
    ]


# ------------------------------------------------------------------
# _write_text_pdf  — low-level PDF creation
# ------------------------------------------------------------------


class TestWriteTextPdf:
    def test_creates_valid_pdf_header(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "out.pdf"
        _write_text_pdf(pdf_path, ["Hello, world!"])
        data = pdf_path.read_bytes()
        assert data.startswith(b"%PDF-1.4")

    def test_creates_valid_pdf_trailer(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "out.pdf"
        _write_text_pdf(pdf_path, ["line one"])
        data = pdf_path.read_bytes()
        assert data.rstrip().endswith(b"%%EOF")

    def test_empty_content_produces_valid_pdf(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "empty.pdf"
        _write_text_pdf(pdf_path, [])
        data = pdf_path.read_bytes()
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")

    def test_long_lines_are_truncated(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "long.pdf"
        long_line = "A" * 200
        _write_text_pdf(pdf_path, [long_line])
        data = pdf_path.read_bytes()
        # The raw PDF stream should contain "..." where the line was cut.
        assert b"..." in data

    def test_special_characters_are_escaped(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "special.pdf"
        _write_text_pdf(pdf_path, ["cost = $10 (estimated)"])
        data = pdf_path.read_bytes()
        # Parentheses must be escaped inside PDF text objects.
        assert b"\\(" in data
        assert b"\\)" in data

    def test_multi_page_output(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "multi.pdf"
        # 50 lines per page (approx) -> 200 lines should create multiple pages.
        many_lines = [f"Line {i}" for i in range(200)]
        _write_text_pdf(pdf_path, many_lines)
        data = pdf_path.read_bytes()
        # The Pages object should have Count > 1.
        assert b"/Count 1" not in data
        assert b"/Kids [" in data

    def test_pdf_contains_text_content(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "content.pdf"
        _write_text_pdf(pdf_path, ["Regulatory Compliance Report"])
        data = pdf_path.read_bytes()
        assert b"Regulatory Compliance Report" in data

    def test_xref_table_present(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "xref.pdf"
        _write_text_pdf(pdf_path, ["test"])
        data = pdf_path.read_bytes()
        assert b"xref" in data
        assert b"startxref" in data


# ------------------------------------------------------------------
# _generate_basic_pdf — HTML stripping + PDF creation
# ------------------------------------------------------------------


class TestGenerateBasicPdf:
    def test_strips_html_and_creates_pdf(self, tmp_path: Path) -> None:
        html_path = _minimal_html(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        result = gen._generate_basic_pdf(html_path, pdf_path)
        assert result == pdf_path
        assert pdf_path.exists()
        data = pdf_path.read_bytes()
        assert data.startswith(b"%PDF-1.4")
        # The plain-text content should appear inside the PDF.
        assert b"Compliance Report" in data

    def test_html_tags_removed(self, tmp_path: Path) -> None:
        html_path = _minimal_html(tmp_path)
        pdf_path = tmp_path / "stripped.pdf"
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        gen._generate_basic_pdf(html_path, pdf_path)
        data = pdf_path.read_bytes()
        # No raw HTML tags should survive in the PDF stream.
        assert b"<h1>" not in data
        assert b"<body>" not in data


# ------------------------------------------------------------------
# _render_pdf — weasyprint vs. fallback
# ------------------------------------------------------------------


class TestRenderPdf:
    def test_fallback_when_weasyprint_unavailable(self, tmp_path: Path) -> None:
        html_path = _minimal_html(tmp_path)
        pdf_path = tmp_path / "fallback.pdf"
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        # weasyprint is not installed in the test environment, so fallback
        # should be used automatically.
        result = gen._render_pdf(html_path, pdf_path)
        assert result == pdf_path
        assert pdf_path.exists()
        data = pdf_path.read_bytes()
        assert data.startswith(b"%PDF-1.4")

    def test_uses_weasyprint_when_available(self, tmp_path: Path) -> None:
        html_path = _minimal_html(tmp_path)
        pdf_path = tmp_path / "weasy.pdf"

        mock_weasyprint = MagicMock()
        mock_html_instance = MagicMock()
        mock_weasyprint.HTML.return_value = mock_html_instance

        with patch.dict(sys.modules, {"weasyprint": mock_weasyprint}):
            gen = ComplianceReportGenerator(output_dir=tmp_path)
            gen._render_pdf(html_path, pdf_path)

        mock_weasyprint.HTML.assert_called_once_with(filename=str(html_path))
        mock_html_instance.write_pdf.assert_called_once_with(str(pdf_path))


# ------------------------------------------------------------------
# Integration with generate()
# ------------------------------------------------------------------


class TestGenerateWithPdf:
    def test_generate_produces_pdf(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        assert artefacts.pdf_report_path is not None
        assert artefacts.pdf_report_path.exists()
        assert artefacts.pdf_report_path.name == "report.pdf"

    def test_pdf_report_path_in_bundle_dict(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=[],
        )
        bundle = artefacts.to_report_bundle_dict()
        assert "pdf_report_path" in bundle
        assert bundle["pdf_report_path"].endswith("report.pdf")

    def test_pdf_is_valid(self, tmp_path: Path) -> None:
        gen = ComplianceReportGenerator(output_dir=tmp_path)
        artefacts = gen.generate(
            run_id=_RUN_ID,
            regulation_id=_REGULATION_ID,
            status="completed",
            repos=_sample_repos(),
        )
        assert artefacts.pdf_report_path is not None
        data = artefacts.pdf_report_path.read_bytes()
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")
