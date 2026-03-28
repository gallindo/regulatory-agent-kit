"""E2E tests for the CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from regulatory_agent_kit.cli import app

EXAMPLE_PLUGIN = Path(__file__).resolve().parents[2] / "regulations" / "examples" / "example.yaml"
runner = CliRunner()


@pytest.mark.integration
class TestE2ECLI:
    """End-to-end tests for the rak CLI commands."""

    def test_rak_run_lite_validates_plugin(self, tmp_path: Path) -> None:
        """rak run --lite --regulation <valid> --repos <dir> loads plugin."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                str(EXAMPLE_PLUGIN),
                "--repos",
                str(repo_dir),
                "--lite",
            ],
        )
        assert result.exit_code == 0
        assert "Pipeline starting" in result.output
        assert "Lite Mode" in result.output

    def test_rak_run_config_loading(self, tmp_path: Path) -> None:
        """rak run --config loads settings from YAML."""
        config_file = tmp_path / "rak-config.yaml"
        config_file.write_text(
            "checkpoint_mode: slack\ncost_threshold: 100.0\n",
            encoding="utf-8",
        )
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        result = runner.invoke(
            app,
            [
                "run",
                "--regulation",
                str(EXAMPLE_PLUGIN),
                "--repos",
                str(repo_dir),
                "--lite",
                "--config",
                str(config_file),
            ],
        )
        assert result.exit_code == 0
        assert "Pipeline starting" in result.output

    def test_rak_plugin_validate_valid(self) -> None:
        """rak plugin validate <valid_plugin> -> exit 0, 'is valid' in output."""
        result = runner.invoke(app, ["plugin", "validate", str(EXAMPLE_PLUGIN)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_rak_plugin_validate_invalid(self, tmp_path: Path) -> None:
        """rak plugin validate <invalid> -> exit 1, errors in output."""
        bad_yaml = tmp_path / "bad-plugin.yaml"
        bad_yaml.write_text("id: x\n", encoding="utf-8")

        result = runner.invoke(app, ["plugin", "validate", str(bad_yaml)])
        assert result.exit_code == 1
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_rak_plugin_init_scaffold(self, tmp_path: Path) -> None:
        """rak plugin init creates directory with YAML, template, README."""
        result = runner.invoke(
            app,
            [
                "plugin",
                "init",
                "--name",
                "My Test Reg",
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0

        plugin_dir = tmp_path / "my-test-reg"
        assert plugin_dir.is_dir()
        assert (plugin_dir / "my-test-reg.yaml").exists()
        assert (plugin_dir / "templates" / "example.j2").exists()
        assert (plugin_dir / "README.md").exists()

    def test_rak_status_invalid_uuid(self) -> None:
        """rak status --run-id not-a-uuid -> exit 1."""
        result = runner.invoke(app, ["status", "--run-id", "not-a-uuid"])
        assert result.exit_code != 0

    def test_rak_all_commands_in_help(self) -> None:
        """rak --help lists all expected command names."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        output = result.output.lower()
        for cmd in ("run", "status", "cancel", "plugin", "db"):
            assert cmd in output, f"Expected '{cmd}' in help output"
