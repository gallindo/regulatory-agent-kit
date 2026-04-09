"""Tests for DORA regulation YAML plugins — all 4 pillars."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.plugins.loader import PluginLoader

DORA_DIR = Path(__file__).resolve().parents[2] / "regulations" / "dora"

PILLAR_FILES = [
    ("dora-ict-risk-2025.yaml", "dora-ict-risk-2025", 7),
    ("dora-incident-reporting-2025.yaml", "dora-incident-reporting-2025", 5),
    ("dora-resilience-testing-2025.yaml", "dora-resilience-testing-2025", 4),
    ("dora-third-party-risk-2025.yaml", "dora-third-party-risk-2025", 5),
]


class TestDORAPluginLoading:
    """Verify all DORA plugins load and validate against the schema."""

    @pytest.fixture
    def loader(self) -> PluginLoader:
        return PluginLoader()

    @pytest.mark.parametrize(
        ("filename", "expected_id", "expected_rule_count"),
        PILLAR_FILES,
        ids=["pillar1-ict-risk", "pillar2-incident", "pillar3-resilience", "pillar4-tpr"],
    )
    def test_plugin_loads_successfully(
        self,
        loader: PluginLoader,
        filename: str,
        expected_id: str,
        expected_rule_count: int,
    ) -> None:
        plugin = loader.load(DORA_DIR / filename)
        assert plugin.id == expected_id
        assert len(plugin.rules) == expected_rule_count

    @pytest.mark.parametrize(
        ("filename", "expected_id", "_rule_count"),
        PILLAR_FILES,
        ids=["pillar1-ict-risk", "pillar2-incident", "pillar3-resilience", "pillar4-tpr"],
    )
    def test_plugin_has_required_fields(
        self,
        loader: PluginLoader,
        filename: str,
        expected_id: str,
        _rule_count: int,
    ) -> None:
        plugin = loader.load(DORA_DIR / filename)
        assert plugin.jurisdiction == "EU"
        assert plugin.authority == "European Banking Authority"
        assert "DORA" in plugin.disclaimer or "2022/2554" in plugin.disclaimer
        assert plugin.version == "1.0.0"
        assert str(plugin.effective_date) == "2025-01-17"

    @pytest.mark.parametrize(
        ("filename", "_expected_id", "_rule_count"),
        PILLAR_FILES,
        ids=["pillar1-ict-risk", "pillar2-incident", "pillar3-resilience", "pillar4-tpr"],
    )
    def test_plugin_has_cross_references(
        self,
        loader: PluginLoader,
        filename: str,
        _expected_id: str,
        _rule_count: int,
    ) -> None:
        plugin = loader.load(DORA_DIR / filename)
        assert plugin.cross_references is not None
        assert len(plugin.cross_references) >= 1

    @pytest.mark.parametrize(
        ("filename", "_expected_id", "_rule_count"),
        PILLAR_FILES,
        ids=["pillar1-ict-risk", "pillar2-incident", "pillar3-resilience", "pillar4-tpr"],
    )
    def test_plugin_has_rts(
        self,
        loader: PluginLoader,
        filename: str,
        _expected_id: str,
        _rule_count: int,
    ) -> None:
        plugin = loader.load(DORA_DIR / filename)
        assert plugin.regulatory_technical_standards is not None
        assert len(plugin.regulatory_technical_standards) >= 1

    def test_all_rules_have_remediation_templates(self, loader: PluginLoader) -> None:
        for filename, _, _ in PILLAR_FILES:
            plugin = loader.load(DORA_DIR / filename)
            for rule in plugin.rules:
                template_path = DORA_DIR / rule.remediation.template
                assert template_path.exists(), (
                    f"Template {rule.remediation.template} missing for rule {rule.id}"
                )

    def test_all_test_templates_exist(self, loader: PluginLoader) -> None:
        for filename, _, _ in PILLAR_FILES:
            plugin = loader.load(DORA_DIR / filename)
            for rule in plugin.rules:
                if rule.remediation.test_template:
                    template_path = DORA_DIR / rule.remediation.test_template
                    assert template_path.exists(), (
                        f"Test template {rule.remediation.test_template} missing for {rule.id}"
                    )

    def test_ict_risk_nis2_takes_precedence(self, loader: PluginLoader) -> None:
        plugin = loader.load(DORA_DIR / "dora-ict-risk-2025.yaml")
        precedence_refs = plugin.get_precedence_refs()
        nis2_ref = [r for r in precedence_refs if r[0] == "nis2"]
        assert len(nis2_ref) == 1
        assert nis2_ref[0][1] == "takes_precedence"

    def test_ict_risk_has_dora_extension_fields(self, loader: PluginLoader) -> None:
        plugin = loader.load(DORA_DIR / "dora-ict-risk-2025.yaml")
        first_rule = plugin.rules[0]
        assert first_rule.model_extra is not None
        assert "dora_pillar" in first_rule.model_extra
        assert first_rule.model_extra["dora_pillar"] == "ict_risk_management"
