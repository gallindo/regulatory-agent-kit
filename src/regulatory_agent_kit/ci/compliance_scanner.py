"""Compliance scanner for CI/CD shift-left integration.

Scans files against a regulation plugin's rule patterns and reports
violations.  Used by:

- GitHub Action (``.github/workflows/compliance-check.yml``)
- GitLab CI (``.gitlab/compliance-check.yml``)
- Pre-commit hook (``.pre-commit-hooks.yaml``)
- Direct CLI: ``python -m regulatory_agent_kit.ci.compliance_scanner``

Exit codes:
- 0: No violations found
- 1: Violations found (blocks merge/commit)
- 2: Configuration error (bad plugin path, etc.)
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Violation model
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """A single compliance violation detected by the scanner."""

    rule_id: str
    severity: str
    description: str
    file_path: str
    pattern: str
    condition: str


@dataclass
class ScanResult:
    """Result of a compliance scan across multiple files."""

    regulation_id: str
    regulation_name: str
    violation_count: int = 0
    violations: list[Violation] = field(default_factory=list)
    files_scanned: int = 0
    rules_checked: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "regulation_id": self.regulation_id,
            "regulation_name": self.regulation_name,
            "violation_count": self.violation_count,
            "files_scanned": self.files_scanned,
            "rules_checked": self.rules_checked,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "description": v.description,
                    "file_path": v.file_path,
                    "pattern": v.pattern,
                    "condition": v.condition,
                }
                for v in self.violations
            ],
        }


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def scan_files(
    plugin_path: Path,
    files: list[str],
    *,
    repo_root: Path | None = None,
) -> ScanResult:
    """Scan a list of files against a regulation plugin's rules.

    For each rule, checks whether any of the given files match the rule's
    glob patterns.  Matching files are flagged as potential violations
    (the condition DSL evaluation is delegated to the Analyzer agent at
    full-pipeline time; the CI scanner checks pattern matches only).

    Args:
        plugin_path: Path to the regulation YAML plugin file.
        files: List of file paths to scan (relative or absolute).
        repo_root: Repository root for resolving relative paths.

    Returns:
        A ``ScanResult`` with all detected violations.
    """
    from regulatory_agent_kit.plugins.loader import PluginLoader

    loader = PluginLoader()
    plugin = loader.load(plugin_path)
    root = repo_root or Path.cwd()

    result = ScanResult(
        regulation_id=plugin.id,
        regulation_name=plugin.name,
        rules_checked=len(plugin.rules),
    )

    scanned_files: set[str] = set()

    for rule in plugin.rules:
        for affects in rule.affects:
            for file_str in files:
                file_path = Path(file_str)
                if not file_path.is_absolute():
                    file_path = root / file_path

                # Check if the file matches the rule's glob pattern
                if _matches_pattern(file_path, affects.pattern, root):
                    scanned_files.add(file_str)
                    result.violations.append(
                        Violation(
                            rule_id=rule.id,
                            severity=rule.severity,
                            description=rule.description.strip(),
                            file_path=file_str,
                            pattern=affects.pattern,
                            condition=affects.condition,
                        )
                    )

    result.files_scanned = len(scanned_files)
    result.violation_count = len(result.violations)
    return result


def _matches_pattern(file_path: Path, pattern: str, root: Path) -> bool:
    """Check if *file_path* matches a glob *pattern* relative to *root*.

    The pattern uses the same syntax as plugin ``affects.pattern`` fields
    (e.g. ``**/*.java``).  Handles the edge case where ``Path.match``
    with ``**/`` requires at least one directory component — files at
    the repo root are matched against a stripped pattern too.
    """
    try:
        relative = file_path.relative_to(root)
    except ValueError:
        relative = file_path

    if relative.match(pattern):
        return True

    # **/*.ext should also match files at the root (no subdirectory)
    if pattern.startswith("**/"):
        stripped = pattern.removeprefix("**/")
        return relative.match(stripped)

    return False


# ---------------------------------------------------------------------------
# CLI entry point (python -m regulatory_agent_kit.ci.compliance_scanner)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the compliance scanner.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 = clean, 1 = violations, 2 = error.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan files for regulation compliance violations"
    )
    parser.add_argument(
        "--regulation",
        required=True,
        help="Path to regulation plugin YAML file",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="File paths to scan",
    )
    parser.add_argument(
        "--changed-files",
        help="Path to a file containing changed file paths (one per line)",
    )
    parser.add_argument(
        "--output",
        help="Path to write JSON report",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory",
    )

    args = parser.parse_args(argv)

    # Collect files
    files: list[str] = list(args.files)
    if args.changed_files:
        changed_path = Path(args.changed_files)
        if changed_path.exists():
            lines = changed_path.read_text(encoding="utf-8").strip().splitlines()
            files.extend(line.strip() for line in lines if line.strip())

    # Validate plugin exists first
    plugin_path = Path(args.regulation)
    if not plugin_path.exists():
        _print(f"ERROR: Plugin not found: {plugin_path}")
        return 2

    if not files:
        _print("No files to scan.")
        return 0

    try:
        result = scan_files(
            plugin_path, files, repo_root=Path(args.repo_root)
        )
    except Exception as exc:
        _print(f"ERROR: Scan failed: {exc}")
        return 2

    # Write JSON report
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(result.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )

    # Print summary
    _print(f"Regulation: {result.regulation_name} ({result.regulation_id})")
    _print(f"Files scanned: {result.files_scanned}")
    _print(f"Rules checked: {result.rules_checked}")
    _print(f"Violations: {result.violation_count}")

    if result.violations:
        _print("")
        for v in result.violations:
            _print(f"  [{v.severity.upper()}] {v.rule_id}: {v.file_path}")
            _print(f"    {v.description}")
        _print("")
        _print("FAILED: Compliance violations detected.")
        return 1

    _print("PASSED: No compliance violations found.")
    return 0


def _print(msg: str) -> None:
    """Print to stderr (avoids mixing with piped stdout)."""
    sys.stderr.write(msg + "\n")


if __name__ == "__main__":
    sys.exit(main())
