"""Plugin certification validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003

from regulatory_agent_kit.plugins.loader import PluginLoader
from regulatory_agent_kit.plugins.schema import Certification, RegulationPlugin


def validate_for_certification(plugin_path: Path) -> tuple[bool, list[str]]:
    """Validate a plugin meets technically_valid requirements.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    errors: list[str] = []
    loader = PluginLoader()

    try:
        plugin = loader.load(plugin_path)
    except Exception as exc:
        return False, [f"Plugin failed to load: {exc}"]

    # Check required fields
    if not plugin.id:
        errors.append("id is required")
    if not plugin.name:
        errors.append("name is required")
    if not plugin.version:
        errors.append("version is required")
    if not plugin.rules:
        errors.append("At least one rule is required")

    # Validate each rule
    for i, rule in enumerate(plugin.rules):
        if not rule.id:
            errors.append(f"Rule {i}: id is required")
        if not rule.description:
            errors.append(f"Rule {i}: description is required")
        if not rule.severity:
            errors.append(f"Rule {i}: severity is required")
        if not rule.remediation:
            errors.append(f"Rule {i}: remediation is required")

    return len(errors) == 0, errors


def certify_plugin(
    plugin: RegulationPlugin,
    *,
    tier: str = "technically_valid",
    certified_by: str = "",
) -> Certification:
    """Create a certification record for a plugin."""
    return Certification(
        tier=tier,
        certified_at=datetime.now(tz=UTC),
        certified_by=certified_by,
        ci_validated=tier == "technically_valid",
    )
