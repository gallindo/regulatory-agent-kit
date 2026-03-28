"""Tests for CLI commands (Phase 13)."""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from regulatory_agent_kit.cli import app

runner = CliRunner()

EXAMPLE_PLUGIN = Path("regulations/examples/example.yaml")
VALID_UUID = str(uuid.uuid4())


# ======================================================================
# Top-level help
# ======================================================================


class TestTopLevelHelp:
    def test_help_lists_all_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Core commands
        for cmd in ("run", "status", "retry-failures", "rollback", "resume", "cancel"):
            assert cmd in result.output
        # Sub-groups
        assert "plugin" in result.output
        assert "db" in result.output


# ======================================================================
# rak run
# ======================================================================


class TestRunCommand:
    def test_run_help_shows_options(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--regulation" in result.output
        assert "--repos" in result.output
        assert "--lite" in result.output
        assert "--config" in result.output
        assert "--checkpoint-mode" in result.output

    def test_run_with_valid_plugin(self) -> None:
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                str(EXAMPLE_PLUGIN),
                "--repos",
                "https://github.com/example/repo",
            ],
        )
        assert result.exit_code == 0
        assert "Pipeline starting" in result.output
        assert "Example Audit Logging Regulation" in result.output

    def test_run_lite_mode(self) -> None:
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                str(EXAMPLE_PLUGIN),
                "--repos",
                "/tmp/test-repo",  # noqa: S108
                "--lite",
            ],
        )
        assert result.exit_code == 0
        assert "Lite Mode" in result.output

    def test_run_with_invalid_plugin_path(self) -> None:
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                "nonexistent/plugin.yaml",
                "--repos",
                "https://github.com/example/repo",
            ],
        )
        assert result.exit_code == 1
        assert "Error loading plugin" in result.output

    def test_run_with_config_flag(self, tmp_path: Path) -> None:
        config_file = tmp_path / "rak-config.yaml"
        config_file.write_text("checkpoint_mode: slack\ncost_threshold: 100.0\n")
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                str(EXAMPLE_PLUGIN),
                "--repos",
                "https://github.com/example/repo",
                "--config",
                str(config_file),
            ],
        )
        assert result.exit_code == 0
        assert "Pipeline starting" in result.output

    def test_run_config_cli_overrides_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "rak-config.yaml"
        config_file.write_text("checkpoint_mode: slack\n")
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                str(EXAMPLE_PLUGIN),
                "--repos",
                "https://github.com/example/repo",
                "--config",
                str(config_file),
                "--checkpoint-mode",
                "webhook",
            ],
        )
        assert result.exit_code == 0
        # CLI flag (webhook) overrides YAML (slack)
        assert "webhook" in result.output


# ======================================================================
# rak status
# ======================================================================


class TestStatusCommand:
    def test_status_with_valid_uuid(self) -> None:
        result = runner.invoke(app, ["status", "--run-id", VALID_UUID])
        assert result.exit_code == 0
        assert VALID_UUID in result.output

    def test_status_with_invalid_uuid(self) -> None:
        result = runner.invoke(app, ["status", "--run-id", "not-a-uuid"])
        assert result.exit_code != 0


# ======================================================================
# rak retry-failures
# ======================================================================


class TestRetryFailuresCommand:
    def test_retry_failures_with_valid_uuid(self) -> None:
        result = runner.invoke(app, ["retry-failures", "--run-id", VALID_UUID])
        assert result.exit_code == 0
        assert "Retrying failures" in result.output


# ======================================================================
# rak rollback
# ======================================================================


class TestRollbackCommand:
    def test_rollback_normal(self) -> None:
        result = runner.invoke(app, ["rollback", "--run-id", VALID_UUID])
        assert result.exit_code == 0
        assert "Rolling back" in result.output

    def test_rollback_dry_run(self) -> None:
        result = runner.invoke(app, ["rollback", "--run-id", VALID_UUID, "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output


# ======================================================================
# rak resume
# ======================================================================


class TestResumeCommand:
    def test_resume_with_valid_uuid(self) -> None:
        result = runner.invoke(app, ["resume", "--run-id", VALID_UUID])
        assert result.exit_code == 0
        assert "Resuming" in result.output


# ======================================================================
# rak cancel
# ======================================================================


class TestCancelCommand:
    def test_cancel_with_valid_uuid(self) -> None:
        result = runner.invoke(app, ["cancel", "--run-id", VALID_UUID])
        assert result.exit_code == 0
        assert "Cancelling" in result.output


# ======================================================================
# rak plugin validate
# ======================================================================


class TestPluginValidate:
    def test_validate_valid_plugin(self) -> None:
        result = runner.invoke(app, ["plugin", "validate", str(EXAMPLE_PLUGIN)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_nonexistent_plugin(self) -> None:
        result = runner.invoke(app, ["plugin", "validate", "nonexistent/plugin.yaml"])
        assert result.exit_code == 1
        assert "Validation failed" in result.output

    def test_validate_invalid_yaml(self, tmp_path: Path) -> None:
        bad_plugin = tmp_path / "bad.yaml"
        bad_plugin.write_text("not: a: valid: plugin")
        result = runner.invoke(app, ["plugin", "validate", str(bad_plugin)])
        assert result.exit_code == 1
        assert "Validation failed" in result.output


# ======================================================================
# rak plugin init
# ======================================================================


class TestPluginInit:
    def test_init_creates_scaffold(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["plugin", "init", "--name", "test-regulation", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "scaffold created" in result.output

        plugin_dir = tmp_path / "test-regulation"
        assert plugin_dir.is_dir()
        assert (plugin_dir / "test-regulation.yaml").is_file()
        assert (plugin_dir / "templates" / "example.j2").is_file()
        assert (plugin_dir / "README.md").is_file()

    def test_init_refuses_existing_directory(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing"
        existing.mkdir()
        result = runner.invoke(
            app,
            ["plugin", "init", "--name", "existing", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output


# ======================================================================
# rak db clean-cache
# ======================================================================


class TestDbCleanCache:
    def test_clean_cache_callable(self) -> None:
        result = runner.invoke(app, ["db", "clean-cache"])
        assert result.exit_code == 0
        assert "cache" in result.output.lower()


# ======================================================================
# rak db create-partitions
# ======================================================================


class TestDbCreatePartitions:
    def test_create_partitions_default(self) -> None:
        result = runner.invoke(app, ["db", "create-partitions"])
        assert result.exit_code == 0
        assert "3" in result.output

    def test_create_partitions_custom_months(self) -> None:
        result = runner.invoke(app, ["db", "create-partitions", "--months", "6"])
        assert result.exit_code == 0
        assert "6" in result.output


# ======================================================================
# No print() in cli.py
# ======================================================================


class TestNoPrint:
    def test_no_print_statements_in_cli(self) -> None:
        """Verify cli.py uses typer.echo() / Rich console, not print()."""
        cli_path = Path("src/regulatory_agent_kit/cli.py")
        source = cli_path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    pytest.fail(f"Found print() call at line {node.lineno} in cli.py")
