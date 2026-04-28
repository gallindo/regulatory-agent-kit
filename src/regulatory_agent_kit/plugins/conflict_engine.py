"""Conflict engine — detects overlapping AST regions across loaded plugins."""

from __future__ import annotations

from typing import Any

from regulatory_agent_kit.models.impact_map import ASTRegion, ConflictRecord, ImpactMap
from regulatory_agent_kit.plugins.schema import RegulationPlugin  # noqa: TC001


class ConflictEngine:
    """Detects conflicts between rules from different regulation plugins."""

    def __init__(self, plugins: list[RegulationPlugin]) -> None:
        self._plugins = {plugin.id: plugin for plugin in plugins}
        self._cross_refs = self._build_cross_ref_index(plugins)

    def detect(self, impact_maps: dict[str, ImpactMap]) -> list[ConflictRecord]:
        """Find overlapping AST regions across impact maps from different plugins.

        Args:
            impact_maps: Mapping of plugin ID → ImpactMap.

        Returns:
            List of ConflictRecord instances describing detected conflicts.
        """
        conflicts: list[ConflictRecord] = []
        plugin_ids = list(impact_maps.keys())

        for i, pid_a in enumerate(plugin_ids):
            for pid_b in plugin_ids[i + 1 :]:
                overlaps = self._find_overlapping_regions(impact_maps[pid_a], impact_maps[pid_b])
                for rule_ids, regions in overlaps:
                    conflicts.append(
                        ConflictRecord(
                            conflicting_rule_ids=rule_ids,
                            affected_regions=regions,
                            description=(
                                f"Conflict between plugins '{pid_a}' and '{pid_b}': "
                                f"rules {rule_ids} affect the same code regions."
                            ),
                        )
                    )
        return conflicts

    def get_precedence(self, plugin_a: str, plugin_b: str) -> str | None:
        """Return the plugin ID that takes precedence, or None if unresolved.

        Checks cross-references for ``takes_precedence`` or ``supersedes`` relationships.
        """
        key = (plugin_a, plugin_b)
        if key in self._cross_refs:
            return self._cross_refs[key]
        key_rev = (plugin_b, plugin_a)
        if key_rev in self._cross_refs:
            return self._cross_refs[key_rev]
        return None

    def _build_cross_ref_index(
        self,
        plugins: list[RegulationPlugin],
    ) -> dict[tuple[str, str], str]:
        """Build an index of precedence relationships from cross-references."""
        index: dict[tuple[str, str], str] = {}
        for plugin in plugins:
            for reg_id, _rel in plugin.get_precedence_refs():
                index[(plugin.id, reg_id)] = plugin.id
        return index

    def _find_overlapping_regions(
        self,
        first_map: ImpactMap,
        second_map: ImpactMap,
    ) -> list[tuple[list[str], list[ASTRegion]]]:
        """Find overlapping AST regions between two impact maps."""
        overlaps: list[tuple[list[str], list[ASTRegion]]] = []

        for file_a in first_map.files:
            for file_b in second_map.files:
                if file_a.shares_file_with(file_b):
                    self._collect_region_overlaps(file_a, file_b, overlaps)
        return overlaps

    @staticmethod
    def _collect_region_overlaps(
        file_a: Any,
        file_b: Any,
        overlaps: list[tuple[list[str], list[ASTRegion]]],
    ) -> None:
        """Check all region pairs between two file impacts for overlaps."""
        for region_a in file_a.affected_regions:
            for region_b in file_b.affected_regions:
                if _regions_overlap(region_a, region_b):
                    rule_ids = list(dict.fromkeys(file_a.get_rule_ids() + file_b.get_rule_ids()))
                    if len(rule_ids) >= 2:
                        overlaps.append((rule_ids, [region_a, region_b]))


def _regions_overlap(region_a: ASTRegion, region_b: ASTRegion) -> bool:
    """Check if two AST regions overlap (same file assumed).

    Uses positive conditionals: returns True when overlap is confirmed.
    """
    regions_are_disjoint = (
        region_a.end_line < region_b.start_line or region_b.end_line < region_a.start_line
    )
    if regions_are_disjoint:
        return False

    touches_at_boundary_ab = (
        region_a.end_line == region_b.start_line and region_a.end_col <= region_b.start_col
    )
    touches_at_boundary_ba = (
        region_b.end_line == region_a.start_line and region_b.end_col <= region_a.start_col
    )
    return not touches_at_boundary_ab and not touches_at_boundary_ba
