"""E2E tests for the plugin system."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.models.impact_map import (
    ASTRegion,
    FileImpact,
    ImpactMap,
    RuleMatch,
)
from regulatory_agent_kit.plugins.condition_dsl import (
    can_evaluate_statically,
    parse,
    to_llm_prompt,
)
from regulatory_agent_kit.plugins.conflict_engine import ConflictEngine
from regulatory_agent_kit.plugins.loader import PluginLoader
from regulatory_agent_kit.plugins.schema import (
    CrossReference,
    RegulationPlugin,
)
from regulatory_agent_kit.templates.engine import TemplateEngine

EXAMPLE_PLUGIN = Path(__file__).resolve().parents[2] / "regulations" / "examples" / "example.yaml"


def _make_plugin(
    plugin_id: str,
    *,
    cross_refs: list[CrossReference] | None = None,
) -> RegulationPlugin:
    """Build a minimal RegulationPlugin for testing."""
    return RegulationPlugin.model_validate(
        {
            "id": plugin_id,
            "name": f"Test Plugin {plugin_id}",
            "version": "1.0.0",
            "effective_date": "2025-01-01",
            "jurisdiction": "TEST",
            "authority": "Test Authority",
            "source_url": "https://example.com/test",
            "disclaimer": "Test disclaimer text.",
            "rules": [
                {
                    "id": f"{plugin_id}-001",
                    "description": "Test rule",
                    "severity": "medium",
                    "affects": [
                        {
                            "pattern": "**/*.java",
                            "condition": "has_annotation(@Test)",
                        }
                    ],
                    "remediation": {
                        "strategy": "add_annotation",
                        "template": "templates/test.j2",
                    },
                }
            ],
            "cross_references": ([cr.model_dump() for cr in cross_refs] if cross_refs else None),
        }
    )


@pytest.mark.integration
class TestE2EPlugins:
    """End-to-end tests for plugin loading, validation, and rendering."""

    async def test_load_validate_render_cycle(self) -> None:
        """Load plugin -> validate -> render template with fixture context."""
        loader = PluginLoader()
        plugin = loader.load(EXAMPLE_PLUGIN)
        assert plugin.id == "example-audit-logging-2025"
        assert len(plugin.rules) >= 1

        # Validate returns no errors
        errors = loader.validate(EXAMPLE_PLUGIN)
        assert errors == []

        # Render the audit_log template
        engine = TemplateEngine()
        template_path = EXAMPLE_PLUGIN.parent / "templates" / "audit_log.j2"
        result = engine.render(
            template_path,
            {
                "rule_id": "EXAMPLE-001",
                "rule_description": "All services need audit logging.",
                "audit_level": "WARN",
                "class_name": "PaymentService",
                "regulation_id": "example-audit-logging-2025",
            },
        )
        assert "PaymentService" in result
        assert "@AuditLog" in result
        assert "WARN" in result

    async def test_plugin_with_template_validation(self) -> None:
        """PluginLoader validates templates when engine is set."""
        loader = PluginLoader()
        engine = TemplateEngine()
        loader.set_template_engine(engine)

        errors = loader.validate(EXAMPLE_PLUGIN)
        assert errors == []

    async def test_plugin_with_broken_template(self, tmp_path: Path) -> None:
        """Plugin referencing broken .j2 -> validate reports template error."""
        # Create a plugin YAML that references a broken template
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        broken_template = templates_dir / "broken.j2"
        broken_template.write_text("{% if x %} unclosed", encoding="utf-8")

        plugin_yaml = tmp_path / "broken-plugin.yaml"
        plugin_yaml.write_text(
            """\
id: broken-plugin
name: "Broken Plugin"
version: "1.0.0"
effective_date: "2025-01-01"
jurisdiction: "TEST"
authority: "Test Authority"
source_url: "https://example.com/broken"
disclaimer: "Test disclaimer."
rules:
  - id: BROKEN-001
    description: "A rule with a broken template."
    severity: low
    affects:
      - pattern: "**/*.py"
        condition: "has_annotation(@Test)"
    remediation:
      strategy: add_annotation
      template: templates/broken.j2
""",
            encoding="utf-8",
        )

        loader = PluginLoader()
        engine = TemplateEngine()
        loader.set_template_engine(engine)

        errors = loader.validate(plugin_yaml)
        assert len(errors) >= 1
        assert any("broken" in e.lower() or "syntax" in e.lower() for e in errors)

    async def test_conflict_detection_across_plugins(self) -> None:
        """Two plugins with overlapping AST regions -> ConflictRecord produced."""
        plugin_a = _make_plugin("plugin-a")
        plugin_b = _make_plugin("plugin-b")
        engine = ConflictEngine([plugin_a, plugin_b])

        # Build overlapping impact maps
        shared_region = ASTRegion(
            start_line=10,
            end_line=20,
            start_col=0,
            end_col=50,
            node_type="class_declaration",
        )
        match_a = RuleMatch(
            rule_id="plugin-a-001",
            description="Rule A",
            severity="high",
            confidence=0.9,
            condition_evaluated="has_annotation(@Test)",
        )
        match_b = RuleMatch(
            rule_id="plugin-b-001",
            description="Rule B",
            severity="medium",
            confidence=0.8,
            condition_evaluated="has_annotation(@Test)",
        )

        impact_a = ImpactMap(
            files=[
                FileImpact(
                    file_path="src/Service.java",
                    matched_rules=[match_a],
                    affected_regions=[shared_region],
                )
            ],
            analysis_confidence=0.9,
        )
        impact_b = ImpactMap(
            files=[
                FileImpact(
                    file_path="src/Service.java",
                    matched_rules=[match_b],
                    affected_regions=[shared_region],
                )
            ],
            analysis_confidence=0.85,
        )

        conflicts = engine.detect({"plugin-a": impact_a, "plugin-b": impact_b})
        assert len(conflicts) >= 1
        rule_ids = conflicts[0].conflicting_rule_ids
        assert "plugin-a-001" in rule_ids
        assert "plugin-b-001" in rule_ids

    async def test_cross_reference_precedence(self) -> None:
        """Plugin A declares takes_precedence over B -> get_precedence returns A."""
        cross_ref = CrossReference(
            regulation_id="plugin-b",
            relationship="takes_precedence",
            articles=["1(1)"],
        )
        plugin_a = _make_plugin("plugin-a", cross_refs=[cross_ref])
        plugin_b = _make_plugin("plugin-b")

        engine = ConflictEngine([plugin_a, plugin_b])
        result = engine.get_precedence("plugin-a", "plugin-b")
        assert result == "plugin-a"

        # Reversed lookup should also resolve
        result_rev = engine.get_precedence("plugin-b", "plugin-a")
        assert result_rev == "plugin-a"

    async def test_condition_dsl_to_llm_prompt(self) -> None:
        """Complex DSL expression -> to_llm_prompt() -> readable text."""
        ast = parse("class implements Service AND NOT has_annotation(@AuditLog)")

        # Verify static evaluation
        assert can_evaluate_statically(ast) is True

        # Convert to LLM prompt
        prompt = to_llm_prompt(ast)
        assert "Service" in prompt
        assert "AuditLog" in prompt
        assert "AND" in prompt
        assert "NOT" in prompt
