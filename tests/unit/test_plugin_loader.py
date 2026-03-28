"""Tests for PluginLoader (Phase 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.exceptions import PluginLoadError, PluginValidationError
from regulatory_agent_kit.plugins.loader import PluginLoader

EXAMPLE_PLUGIN = Path(__file__).resolve().parents[2] / "regulations" / "examples" / "example.yaml"


class TestPluginLoader:
    def test_load_example_plugin(self) -> None:
        loader = PluginLoader()
        plugin = loader.load(EXAMPLE_PLUGIN)
        assert plugin.id == "example-audit-logging-2025"
        assert len(plugin.rules) == 2

    def test_cache_returns_same_object(self) -> None:
        loader = PluginLoader()
        p1 = loader.load(EXAMPLE_PLUGIN)
        p2 = loader.load(EXAMPLE_PLUGIN)
        assert p1 is p2

    def test_get_by_id_after_load(self) -> None:
        loader = PluginLoader()
        loader.load(EXAMPLE_PLUGIN)
        assert loader.get_by_id("example-audit-logging-2025") is not None

    def test_get_by_id_unknown(self) -> None:
        loader = PluginLoader()
        assert loader.get_by_id("nonexistent") is None

    def test_load_nonexistent_raises(self) -> None:
        loader = PluginLoader()
        with pytest.raises(PluginLoadError):
            loader.load(Path("/nonexistent/plugin.yaml"))

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(": : : [[[")
        loader = PluginLoader()
        with pytest.raises((PluginLoadError, PluginValidationError)):
            loader.load(bad_yaml)

    def test_load_non_mapping_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "list.yaml"
        yaml_file.write_text("- item1\n- item2\n")
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="mapping"):
            loader.load(yaml_file)

    def test_load_invalid_schema_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "incomplete.yaml"
        yaml_file.write_text("id: incomplete\n")
        loader = PluginLoader()
        with pytest.raises(PluginValidationError):
            loader.load(yaml_file)

    def test_validate_valid_plugin(self) -> None:
        loader = PluginLoader()
        errors = loader.validate(EXAMPLE_PLUGIN)
        assert errors == []

    def test_validate_missing_file(self) -> None:
        loader = PluginLoader()
        errors = loader.validate(Path("/nonexistent/plugin.yaml"))
        assert len(errors) == 1
        assert "not found" in errors[0].lower() or "File not found" in errors[0]

    def test_validate_invalid_schema(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("id: bad\nname: bad\n")
        loader = PluginLoader()
        errors = loader.validate(yaml_file)
        assert len(errors) > 0

    def test_validate_bad_condition(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "badcond.yaml"
        yaml_file.write_text(
            "id: test\n"
            "name: Test\n"
            "version: '1.0.0'\n"
            "effective_date: '2025-01-01'\n"
            "jurisdiction: EU\n"
            "authority: Auth\n"
            "source_url: https://example.com\n"
            "disclaimer: Not legal advice.\n"
            "rules:\n"
            "  - id: R1\n"
            "    description: test\n"
            "    severity: high\n"
            "    affects:\n"
            "      - pattern: '**/*.java'\n"
            "        condition: '((( broken'\n"
            "    remediation:\n"
            "      strategy: add_annotation\n"
            "      template: fix.j2\n"
        )
        loader = PluginLoader()
        errors = loader.validate(yaml_file)
        assert any("R1" in e for e in errors)

    def test_load_all_from_directory(self) -> None:
        plugin_dir = EXAMPLE_PLUGIN.parent
        loader = PluginLoader(plugin_dir=plugin_dir)
        plugins = loader.load_all()
        assert len(plugins) >= 1
        assert any(p.id == "example-audit-logging-2025" for p in plugins)

    def test_load_all_no_dir(self) -> None:
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="directory"):
            loader.load_all()
