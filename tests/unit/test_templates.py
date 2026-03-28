"""Tests for the template engine (Phase 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.exceptions import TemplateError
from regulatory_agent_kit.plugins.loader import PluginLoader
from regulatory_agent_kit.templates.engine import TemplateEngine

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "regulations" / "examples"
AUDIT_LOG_TEMPLATE = EXAMPLE_DIR / "templates" / "audit_log.j2"
AUDIT_LOG_TEST_TEMPLATE = EXAMPLE_DIR / "templates" / "audit_log_test.j2"
EXAMPLE_PLUGIN = EXAMPLE_DIR / "example.yaml"


class TestTemplateEngine:
    def test_render_file(self, tmp_path: Path) -> None:
        engine = TemplateEngine()
        tpl = tmp_path / "test.j2"
        tpl.write_text("Hello {{ name }}!")
        result = engine.render(tpl, {"name": "World"})
        assert result == "Hello World!"

    def test_render_string(self) -> None:
        engine = TemplateEngine()
        result = engine.render_string("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_render_missing_file_raises(self) -> None:
        engine = TemplateEngine()
        with pytest.raises(TemplateError, match="not found"):
            engine.render(Path("/nonexistent/template.j2"), {})

    def test_sandbox_blocks_dangerous_builtins(self) -> None:
        engine = TemplateEngine()
        # Attempt to access __import__ via string methods
        with pytest.raises(TemplateError):
            engine.render_string("{{ ''.__class__.__mro__[1].__subclasses__() }}", {})

    def test_validate_valid_template(self, tmp_path: Path) -> None:
        engine = TemplateEngine()
        tpl = tmp_path / "valid.j2"
        tpl.write_text("{{ name }} is {{ age }}")
        errors = engine.validate_template(tpl)
        assert errors == []

    def test_validate_invalid_template(self, tmp_path: Path) -> None:
        engine = TemplateEngine()
        tpl = tmp_path / "broken.j2"
        tpl.write_text("{% if x %}no end")
        errors = engine.validate_template(tpl)
        assert len(errors) > 0
        assert "Syntax error" in errors[0] or "syntax" in errors[0].lower()

    def test_validate_missing_template(self) -> None:
        engine = TemplateEngine()
        errors = engine.validate_template(Path("/nonexistent.j2"))
        assert len(errors) == 1
        assert "not found" in errors[0]


class TestExampleTemplates:
    def test_audit_log_template_renders(self) -> None:
        engine = TemplateEngine()
        context = {
            "rule_id": "EXAMPLE-001",
            "rule_description": "Test rule",
            "class_name": "PaymentService",
            "regulation_id": "example-audit-logging-2025",
        }
        result = engine.render(AUDIT_LOG_TEMPLATE, context)
        assert "PaymentService" in result
        assert "@AuditLog" in result
        assert "EXAMPLE-001" in result

    def test_audit_log_test_template_renders(self) -> None:
        engine = TemplateEngine()
        context = {
            "rule_id": "EXAMPLE-001",
            "class_name": "PaymentService",
            "regulation_id": "example-audit-logging-2025",
        }
        result = engine.render(AUDIT_LOG_TEST_TEMPLATE, context)
        assert "PaymentServiceAuditLogTest" in result
        assert "AuditLog" in result

    def test_templates_preserve_indentation(self) -> None:
        engine = TemplateEngine()
        result = engine.render(
            AUDIT_LOG_TEMPLATE,
            {
                "rule_id": "R1",
                "rule_description": "desc",
                "class_name": "Svc",
                "regulation_id": "reg",
            },
        )
        # Should have consistent indentation, no trailing whitespace on lines
        for line in result.splitlines():
            assert line == line.rstrip() or line.strip() == ""


class TestPluginLoaderTemplateValidation:
    def test_validate_with_template_engine(self) -> None:
        engine = TemplateEngine()
        loader = PluginLoader()
        loader.set_template_engine(engine)
        errors = loader.validate(EXAMPLE_PLUGIN)
        assert errors == []

    def test_validate_with_broken_template(self, tmp_path: Path) -> None:
        # Create a plugin referencing a broken template
        tpl_dir = tmp_path / "templates"
        tpl_dir.mkdir()
        broken_tpl = tpl_dir / "broken.j2"
        broken_tpl.write_text("{% if x %}no end")

        plugin_yaml = tmp_path / "plugin.yaml"
        plugin_yaml.write_text(
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
            "        condition: 'has_method(foo)'\n"
            "    remediation:\n"
            "      strategy: add_annotation\n"
            "      template: templates/broken.j2\n"
        )
        engine = TemplateEngine()
        loader = PluginLoader()
        loader.set_template_engine(engine)
        errors = loader.validate(plugin_yaml)
        assert any("template" in e.lower() or "R1" in e for e in errors)
