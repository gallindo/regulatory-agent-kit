"""Tests for plugin schema validation (Phase 3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulatory_agent_kit.plugins.schema import (
    CrossReference,
    RegulationPlugin,
    Remediation,
    Rule,
)
from tests.helpers import minimal_plugin as _minimal_plugin
from tests.helpers import minimal_rule as _minimal_rule


class TestRegulationPlugin:
    def test_valid_plugin(self) -> None:
        plugin = RegulationPlugin.model_validate(_minimal_plugin())
        assert plugin.id == "test-plugin"
        assert len(plugin.rules) == 1

    def test_missing_disclaimer(self) -> None:
        with pytest.raises(ValidationError):
            RegulationPlugin.model_validate(_minimal_plugin(disclaimer=""))

    def test_whitespace_only_disclaimer(self) -> None:
        with pytest.raises(ValidationError, match=r"[Dd]isclaimer"):
            RegulationPlugin.model_validate(_minimal_plugin(disclaimer="   \n  "))

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            RegulationPlugin.model_validate({"id": "incomplete"})

    def test_extra_fields_allowed(self) -> None:
        plugin = RegulationPlugin.model_validate(
            _minimal_plugin(plugin_pillar="ICT Risk Management")
        )
        assert plugin.model_extra is not None
        assert plugin.model_extra["plugin_pillar"] == "ICT Risk Management"

    def test_cross_references(self) -> None:
        plugin = RegulationPlugin.model_validate(
            _minimal_plugin(
                cross_references=[
                    {
                        "regulation_id": "gdpr",
                        "relationship": "does_not_override",
                        "articles": ["2(3)"],
                        "conflict_handling": "escalate_to_human",
                    }
                ]
            )
        )
        assert plugin.cross_references is not None
        assert plugin.cross_references[0].regulation_id == "gdpr"

    def test_empty_rules_rejected(self) -> None:
        with pytest.raises(ValidationError, match="rules"):
            RegulationPlugin.model_validate(_minimal_plugin(rules=[]))


class TestRule:
    def test_valid_rule(self) -> None:
        rule = Rule.model_validate(_minimal_rule())
        assert rule.id == "R1"

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValidationError, match="severity"):
            Rule.model_validate(_minimal_rule(severity="urgent"))

    def test_extra_fields_on_rule(self) -> None:
        rule = Rule.model_validate(_minimal_rule(custom_field="custom_value"))
        assert rule.model_extra["custom_field"] == "custom_value"


class TestRemediation:
    def test_valid_remediation(self) -> None:
        r = Remediation(strategy="add_annotation", template="fix.j2")
        assert r.confidence_threshold == 0.85

    def test_invalid_strategy(self) -> None:
        with pytest.raises(ValidationError, match="strategy"):
            Remediation(strategy="invalid", template="fix.j2")

    def test_confidence_range(self) -> None:
        with pytest.raises(ValidationError, match="confidence_threshold"):
            Remediation(strategy="add_annotation", template="fix.j2", confidence_threshold=1.5)


class TestCrossReference:
    def test_valid_reference(self) -> None:
        ref = CrossReference(
            regulation_id="gdpr",
            relationship="takes_precedence",
        )
        assert ref.relationship == "takes_precedence"

    def test_invalid_relationship(self) -> None:
        with pytest.raises(ValidationError, match="relationship"):
            CrossReference(regulation_id="gdpr", relationship="unknown")

    def test_invalid_conflict_handling(self) -> None:
        with pytest.raises(ValidationError, match="conflict_handling"):
            CrossReference(
                regulation_id="gdpr",
                relationship="complementary",
                conflict_handling="ignore",
            )
