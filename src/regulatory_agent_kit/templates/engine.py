"""Jinja2 sandboxed template engine for code generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

from regulatory_agent_kit.exceptions import TemplateError


def _basename_filter(path: str) -> str:
    """Return the final component of a path."""
    return Path(path).name


def _dirname_filter(path: str) -> str:
    """Return the directory component of a path."""
    return str(Path(path).parent)


def _snake_case_filter(value: str) -> str:
    """Convert a string to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[\s\-]+", "_", s)
    return s.lower()


def _camel_case_filter(value: str) -> str:
    """Convert a string to camelCase."""
    parts = re.split(r"[_\-\s]+", value)
    if not parts:
        return value
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def _pascal_case_filter(value: str) -> str:
    """Convert a string to PascalCase."""
    parts = re.split(r"[_\-\s]+", value)
    return "".join(p.capitalize() for p in parts)


class TemplateEngine:
    """Sandboxed Jinja2 template rendering for regulation remediation."""

    def __init__(self) -> None:
        self._env = SandboxedEnvironment(
            keep_trailing_newline=True,
            lstrip_blocks=True,
            trim_blocks=True,
        )
        self._env.filters["basename"] = _basename_filter
        self._env.filters["dirname"] = _dirname_filter
        self._env.filters["snake_case"] = _snake_case_filter
        self._env.filters["camel_case"] = _camel_case_filter
        self._env.filters["pascal_case"] = _pascal_case_filter

    def render(self, template_path: Path, context: dict[str, Any]) -> str:
        """Render a Jinja2 template file with the given context."""
        if not template_path.exists():
            msg = f"Template file not found: {template_path}"
            raise TemplateError(msg)
        try:
            template_str = template_path.read_text(encoding="utf-8")
            template = self._env.from_string(template_str)
            return template.render(context)
        except TemplateError:
            raise
        except Exception as exc:
            msg = f"Template rendering failed for '{template_path}': {exc}"
            raise TemplateError(msg) from exc

    def render_string(self, template_str: str, context: dict[str, Any]) -> str:
        """Render an inline template string with the given context."""
        try:
            template = self._env.from_string(template_str)
            return template.render(context)
        except Exception as exc:
            msg = f"Template rendering failed: {exc}"
            raise TemplateError(msg) from exc

    def validate_template(self, template_path: Path) -> list[str]:
        """Validate a template file, returning error descriptions (empty = valid)."""
        errors: list[str] = []
        if not template_path.exists():
            errors.append(f"Template file not found: {template_path}")
            return errors
        try:
            source = template_path.read_text(encoding="utf-8")
            self._env.parse(source)
        except TemplateSyntaxError as exc:
            errors.append(f"Syntax error in '{template_path}': {exc}")
        except Exception as exc:
            errors.append(f"Validation error in '{template_path}': {exc}")
        return errors
