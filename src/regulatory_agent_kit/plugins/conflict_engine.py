"""Conflict engine — detects overlapping AST regions across loaded plugins."""

from __future__ import annotations

from regulatory_agent_kit.models.impact_map import ASTRegion, ConflictRecord, ImpactMap
from regulatory_agent_kit.plugins.schema import RegulationPlugin  # noqa: TC001


class ConflictEngine:
    """Detects conflicts between rules from different regulation plugins."""

    def __init__(self, plugins: list[RegulationPlugin]) -> None:
        self._plugins = {p.id: p for p in plugins}
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

    @staticmethod
    def _build_cross_ref_index(
        plugins: list[RegulationPlugin],
    ) -> dict[tuple[str, str], str]:
        """Build an index of precedence relationships from cross-references."""
        index: dict[tuple[str, str], str] = {}
        for plugin in plugins:
            if plugin.cross_references is None:
                continue
            for ref in plugin.cross_references:
                if ref.relationship in ("takes_precedence", "supersedes"):
                    index[(plugin.id, ref.regulation_id)] = plugin.id
        return index

    @staticmethod
    def _find_overlapping_regions(
        map_a: ImpactMap, map_b: ImpactMap
    ) -> list[tuple[list[str], list[ASTRegion]]]:
        """Find overlapping AST regions between two impact maps."""
        overlaps: list[tuple[list[str], list[ASTRegion]]] = []

        for file_a in map_a.files:
            for file_b in map_b.files:
                if file_a.file_path != file_b.file_path:
                    continue

                for region_a in file_a.affected_regions:
                    for region_b in file_b.affected_regions:
                        if _regions_overlap(region_a, region_b):
                            rule_ids_a = [m.rule_id for m in file_a.matched_rules]
                            rule_ids_b = [m.rule_id for m in file_b.matched_rules]
                            all_rules = list(dict.fromkeys(rule_ids_a + rule_ids_b))
                            if len(all_rules) >= 2:
                                overlaps.append((all_rules, [region_a, region_b]))
        return overlaps


def _regions_overlap(a: ASTRegion, b: ASTRegion) -> bool:
    """Check if two AST regions overlap (same file assumed)."""
    if a.end_line < b.start_line or b.end_line < a.start_line:
        return False
    if a.end_line == b.start_line and a.end_col <= b.start_col:
        return False
    return not (b.end_line == a.start_line and b.end_col <= a.start_col)
