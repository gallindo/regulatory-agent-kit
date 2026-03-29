"""Tests for the CI compliance scanner."""

from __future__ import annotations

import json
from pathlib import Path

from regulatory_agent_kit.ci.compliance_scanner import (
    ScanResult,
    main,
    scan_files,
)

EXAMPLE_PLUGIN = Path("regulations/examples/example.yaml")


# ------------------------------------------------------------------
# scan_files
# ------------------------------------------------------------------


class TestScanFiles:
    def test_detects_matching_java_file(self, tmp_path: Path) -> None:
        java_file = tmp_path / "src" / "UserService.java"
        java_file.parent.mkdir(parents=True)
        java_file.write_text("public class UserService {}")

        result = scan_files(
            EXAMPLE_PLUGIN,
            ["src/UserService.java"],
            repo_root=tmp_path,
        )
        assert result.violation_count >= 1
        assert result.regulation_id == "example-audit-logging-2025"
        assert any(v.rule_id == "EXAMPLE-001" for v in result.violations)

    def test_no_violations_for_unmatched_files(self, tmp_path: Path) -> None:
        py_file = tmp_path / "main.py"
        py_file.write_text("x = 1\n")

        result = scan_files(
            EXAMPLE_PLUGIN,
            ["main.py"],
            repo_root=tmp_path,
        )
        # example plugin only targets **/*.java and **/*.yaml
        java_violations = [v for v in result.violations if v.rule_id == "EXAMPLE-001"]
        assert len(java_violations) == 0

    def test_scans_yaml_files(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config" / "service.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text("name: my-service\n")

        result = scan_files(
            EXAMPLE_PLUGIN,
            ["config/service.yaml"],
            repo_root=tmp_path,
        )
        yaml_violations = [v for v in result.violations if v.rule_id == "EXAMPLE-002"]
        assert len(yaml_violations) >= 1

    def test_empty_file_list(self) -> None:
        result = scan_files(EXAMPLE_PLUGIN, [])
        assert result.violation_count == 0
        assert result.files_scanned == 0

    def test_result_has_correct_metadata(self) -> None:
        result = scan_files(EXAMPLE_PLUGIN, [])
        assert result.regulation_id == "example-audit-logging-2025"
        assert result.regulation_name == "Example Audit Logging Regulation"
        assert result.rules_checked == 2

    def test_multiple_files_multiple_rules(self, tmp_path: Path) -> None:
        java = tmp_path / "Svc.java"
        java.write_text("class Svc {}")
        yaml = tmp_path / "config.yaml"
        yaml.write_text("key: val\n")

        result = scan_files(
            EXAMPLE_PLUGIN,
            ["Svc.java", "config.yaml"],
            repo_root=tmp_path,
        )
        rule_ids = {v.rule_id for v in result.violations}
        assert "EXAMPLE-001" in rule_ids
        assert "EXAMPLE-002" in rule_ids


# ------------------------------------------------------------------
# ScanResult serialisation
# ------------------------------------------------------------------


class TestScanResultSerialisation:
    def test_to_dict_structure(self) -> None:
        result = ScanResult(
            regulation_id="test",
            regulation_name="Test Reg",
            violation_count=0,
        )
        d = result.to_dict()
        assert "regulation_id" in d
        assert "violations" in d
        assert isinstance(d["violations"], list)

    def test_to_dict_with_violations(self, tmp_path: Path) -> None:
        java = tmp_path / "Main.java"
        java.write_text("class Main {}")

        result = scan_files(
            EXAMPLE_PLUGIN,
            ["Main.java"],
            repo_root=tmp_path,
        )
        d = result.to_dict()
        assert d["violation_count"] >= 1
        assert d["violations"][0]["rule_id"] == "EXAMPLE-001"


# ------------------------------------------------------------------
# CLI entry point (main)
# ------------------------------------------------------------------


class TestMainCli:
    def test_no_files_returns_zero(self) -> None:
        rc = main(["--regulation", str(EXAMPLE_PLUGIN)])
        assert rc == 0

    def test_missing_plugin_returns_two(self) -> None:
        rc = main(["--regulation", "nonexistent.yaml"])
        assert rc == 2

    def test_matching_file_returns_one(self, tmp_path: Path) -> None:
        java = tmp_path / "Svc.java"
        java.write_text("class Svc {}")

        rc = main([
            "--regulation", str(EXAMPLE_PLUGIN),
            "--files", "Svc.java",
            "--repo-root", str(tmp_path),
        ])
        assert rc == 1

    def test_nonmatching_file_returns_zero(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")

        rc = main([
            "--regulation", str(EXAMPLE_PLUGIN),
            "--files", "readme.txt",
            "--repo-root", str(tmp_path),
        ])
        assert rc == 0

    def test_changed_files_from_file(self, tmp_path: Path) -> None:
        java = tmp_path / "Svc.java"
        java.write_text("class Svc {}")

        changed = tmp_path / "changed.txt"
        changed.write_text("Svc.java\n")

        rc = main([
            "--regulation", str(EXAMPLE_PLUGIN),
            "--changed-files", str(changed),
            "--repo-root", str(tmp_path),
        ])
        assert rc == 1

    def test_output_writes_json(self, tmp_path: Path) -> None:
        java = tmp_path / "Svc.java"
        java.write_text("class Svc {}")
        output = tmp_path / "report.json"

        main([
            "--regulation", str(EXAMPLE_PLUGIN),
            "--files", "Svc.java",
            "--repo-root", str(tmp_path),
            "--output", str(output),
        ])

        assert output.exists()
        data = json.loads(output.read_text())
        assert data["regulation_id"] == "example-audit-logging-2025"
        assert data["violation_count"] >= 1
