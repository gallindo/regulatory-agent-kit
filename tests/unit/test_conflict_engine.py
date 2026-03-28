"""Tests for the ConflictEngine (Phase 3)."""

from __future__ import annotations

from regulatory_agent_kit.models.impact_map import (
    ASTRegion,
    FileImpact,
    ImpactMap,
    RuleMatch,
)
from regulatory_agent_kit.plugins.conflict_engine import ConflictEngine
from regulatory_agent_kit.plugins.schema import RegulationPlugin
from tests.unit.test_plugin_schema import _minimal_plugin


def _make_plugin(plugin_id: str, **kwargs: object) -> RegulationPlugin:
    return RegulationPlugin.model_validate(_minimal_plugin(id=plugin_id, **kwargs))


def _make_impact_map(
    file_path: str,
    rule_id: str,
    start_line: int,
    end_line: int,
) -> ImpactMap:
    return ImpactMap(
        files=[
            FileImpact(
                file_path=file_path,
                matched_rules=[
                    RuleMatch(
                        rule_id=rule_id,
                        description="test",
                        severity="high",
                        confidence=0.9,
                        condition_evaluated="test",
                    )
                ],
                affected_regions=[
                    ASTRegion(
                        start_line=start_line,
                        end_line=end_line,
                        start_col=0,
                        end_col=80,
                        node_type="class",
                    )
                ],
            )
        ],
        analysis_confidence=0.9,
    )


class TestConflictDetection:
    def test_no_conflicts_different_files(self) -> None:
        p1 = _make_plugin("plugin-a")
        p2 = _make_plugin("plugin-b")
        engine = ConflictEngine([p1, p2])

        map_a = _make_impact_map("src/A.java", "RULE-A1", 1, 10)
        map_b = _make_impact_map("src/B.java", "RULE-B1", 1, 10)

        conflicts = engine.detect({"plugin-a": map_a, "plugin-b": map_b})
        assert len(conflicts) == 0

    def test_overlapping_regions_detected(self) -> None:
        p1 = _make_plugin("plugin-a")
        p2 = _make_plugin("plugin-b")
        engine = ConflictEngine([p1, p2])

        map_a = _make_impact_map("src/Service.java", "RULE-A1", 5, 20)
        map_b = _make_impact_map("src/Service.java", "RULE-B1", 15, 30)

        conflicts = engine.detect({"plugin-a": map_a, "plugin-b": map_b})
        assert len(conflicts) == 1
        assert "RULE-A1" in conflicts[0].conflicting_rule_ids
        assert "RULE-B1" in conflicts[0].conflicting_rule_ids

    def test_non_overlapping_same_file(self) -> None:
        p1 = _make_plugin("plugin-a")
        p2 = _make_plugin("plugin-b")
        engine = ConflictEngine([p1, p2])

        map_a = _make_impact_map("src/Service.java", "RULE-A1", 1, 10)
        map_b = _make_impact_map("src/Service.java", "RULE-B1", 20, 30)

        conflicts = engine.detect({"plugin-a": map_a, "plugin-b": map_b})
        assert len(conflicts) == 0


class TestPrecedence:
    def test_takes_precedence(self) -> None:
        p1 = _make_plugin(
            "dora",
            cross_references=[
                {
                    "regulation_id": "nis2",
                    "relationship": "takes_precedence",
                }
            ],
        )
        p2 = _make_plugin("nis2")
        engine = ConflictEngine([p1, p2])

        assert engine.get_precedence("dora", "nis2") == "dora"
        assert engine.get_precedence("nis2", "dora") == "dora"

    def test_no_precedence(self) -> None:
        p1 = _make_plugin("plugin-a")
        p2 = _make_plugin("plugin-b")
        engine = ConflictEngine([p1, p2])

        assert engine.get_precedence("plugin-a", "plugin-b") is None
