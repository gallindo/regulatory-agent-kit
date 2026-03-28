"""Plugin loader — load, validate, and cache regulation YAML plugins."""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003
from typing import Protocol, runtime_checkable

from ruamel.yaml import YAML

from regulatory_agent_kit.exceptions import (
    ConditionParseError,
    PluginLoadError,
    PluginValidationError,
)
from regulatory_agent_kit.plugins.condition_dsl import parse
from regulatory_agent_kit.plugins.schema import RegulationPlugin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template-validation protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TemplateValidator(Protocol):
    """Interface for objects that can validate Jinja2 template files."""

    def validate_template(self, path: Path) -> list[str]:
        """Return a list of error messages (empty means valid)."""
        ...  # pragma: no cover


class PluginLoader:
    """Loads, validates, and caches regulation YAML plugins.

    Template validation is deferred until a ``TemplateValidator`` is provided
    via :meth:`set_template_validator`.
    """

    def __init__(self, plugin_dir: Path | None = None) -> None:
        self._plugin_dir = plugin_dir
        self._cache: dict[str, RegulationPlugin] = {}
        self._path_cache: dict[str, RegulationPlugin] = {}
        self._yaml = YAML(typ="safe")
        self._template_validator: TemplateValidator | None = None

    # -- validator wiring ---------------------------------------------------

    def set_template_validator(
        self,
        validator: TemplateValidator | None,
    ) -> None:
        """Set the template validator used during :meth:`validate`."""
        self._template_validator = validator

    def set_template_engine(self, engine: object) -> None:
        """Backward-compatible alias for :meth:`set_template_validator`."""
        self.set_template_validator(engine)  # type: ignore[arg-type]

    # -- public API ---------------------------------------------------------

    def load(self, path: Path) -> RegulationPlugin:
        """Load and validate a plugin YAML file, returning a cached RegulationPlugin."""
        cache_key = str(path.resolve())
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        raw = self._parse_yaml(path)
        try:
            plugin = RegulationPlugin.model_validate(raw)
        except Exception as exc:
            msg = f"Failed to validate plugin '{path}': {exc}"
            raise PluginValidationError(msg) from exc

        self._path_cache[cache_key] = plugin
        self._cache[plugin.id] = plugin
        return plugin

    def load_all(self) -> list[RegulationPlugin]:
        """Load all .yaml/.yml plugins from the plugin directory."""
        if self._plugin_dir is None:
            msg = "No plugin directory configured"
            raise PluginLoadError(msg)

        plugins: list[RegulationPlugin] = []
        for yaml_path in sorted(self._plugin_dir.rglob("*.yaml")):
            try:
                plugins.append(self.load(yaml_path))
            except (PluginValidationError, PluginLoadError) as exc:
                logger.warning("Skipping invalid plugin %s: %s", yaml_path, exc)
        for yaml_path in sorted(self._plugin_dir.rglob("*.yml")):
            try:
                plugins.append(self.load(yaml_path))
            except (PluginValidationError, PluginLoadError) as exc:
                logger.warning("Skipping invalid plugin %s: %s", yaml_path, exc)
        return plugins

    def validate(self, path: Path) -> list[str]:
        """Validate a plugin YAML file, returning a list of error messages (empty = valid)."""
        errors: list[str] = []

        # Check file existence
        if not path.exists():
            errors.append(f"File not found: {path}")
            return errors

        # Parse YAML
        try:
            raw = self._parse_yaml(path)
        except PluginLoadError as exc:
            errors.append(str(exc))
            return errors

        # Validate schema
        try:
            plugin = RegulationPlugin.model_validate(raw)
        except Exception as exc:
            errors.append(f"Schema validation failed: {exc}")
            return errors

        # Validate condition DSL expressions
        for rule in plugin.rules:
            for affects in rule.affects:
                try:
                    parse(affects.condition)
                except ConditionParseError as exc:
                    errors.append(f"Rule '{rule.id}', condition '{affects.condition}': {exc}")

        # Validate templates (if a TemplateValidator is available)
        if self._template_validator is not None:
            errors.extend(self._validate_templates(plugin, path.parent))

        return errors

    def get_by_id(self, plugin_id: str) -> RegulationPlugin | None:
        """Return a cached plugin by ID, or None if not loaded."""
        return self._cache.get(plugin_id)

    # -- internals ----------------------------------------------------------

    def _parse_yaml(self, path: Path) -> dict:  # type: ignore[type-arg]
        """Parse a YAML file, raising PluginLoadError on failure."""
        if not path.exists():
            msg = f"Plugin file not found: {path}"
            raise PluginLoadError(msg)
        try:
            data = self._yaml.load(path)
        except Exception as exc:
            msg = f"Failed to parse YAML '{path}': {exc}"
            raise PluginLoadError(msg) from exc
        if not isinstance(data, dict):
            msg = f"Plugin file '{path}' must contain a YAML mapping, got {type(data).__name__}"
            raise PluginLoadError(msg)
        return data

    def _validate_templates(
        self,
        plugin: RegulationPlugin,
        base_dir: Path,
    ) -> list[str]:
        """Validate templates referenced by plugin rules."""
        errors: list[str] = []
        validator = self._template_validator
        if validator is None:
            return errors

        for rule in plugin.rules:
            template_path, test_path = rule.get_template_paths(base_dir)
            result = validator.validate_template(template_path)
            if result:
                errors.append(f"Rule '{rule.id}' template '{template_path.name}': {result}")
            if test_path is not None:
                result = validator.validate_template(test_path)
                if result:
                    errors.append(f"Rule '{rule.id}' test template '{test_path.name}': {result}")
        return errors
