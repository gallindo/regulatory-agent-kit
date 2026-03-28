"""Jinja2 sandboxed template engine for code generation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Any

from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

from regulatory_agent_kit.exceptions import TemplateError


class TemplateEngine:
    """Sandboxed Jinja2 template rendering for regulation remediation."""

    def __init__(self) -> None:
        self._env = SandboxedEnvironment(
            keep_trailing_newline=True,
            lstrip_blocks=True,
            trim_blocks=True,
        )

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
