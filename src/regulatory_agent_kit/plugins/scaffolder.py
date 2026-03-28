"""Plugin scaffolding — generates directory structure for new regulation plugins."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

_SCAFFOLD_PLUGIN_YAML = """\
# Regulation Plugin: {name}
# Edit this file to define your regulatory rules.

id: {slug}
name: "{name}"
version: "1.0.0"
effective_date: "2025-01-01"
jurisdiction: "CHANGE_ME"
authority: "CHANGE_ME"
source_url: "https://example.com/regulations/{slug}"
disclaimer: >
  DISCLAIMER: Replace this with an appropriate legal disclaimer.

changelog: "1.0.0: Initial plugin scaffold."

rules:
  - id: {upper_slug}-001
    description: >
      Replace this with a description of the regulatory rule.
    severity: medium
    affects:
      - pattern: "**/*.java"
        condition: "has_annotation(@Example)"
    remediation:
      strategy: add_annotation
      template: templates/example.j2
      confidence_threshold: 0.85
"""

_SCAFFOLD_TEMPLATE = """\
{{# Jinja2 template for {name} rule remediation #}}
{{{{ content }}}}
"""

_SCAFFOLD_README = """\
# {name}

Regulation plugin scaffold. Edit `{slug}.yaml` to define your rules.
"""


class PluginScaffolder:
    """Generates scaffold files for a new regulation plugin."""

    def scaffold(self, name: str, output_dir: Path) -> Path:
        """Create plugin directory with YAML, template, and README.

        Args:
            name: Human-readable regulation name.
            output_dir: Parent directory for the plugin scaffold.

        Returns:
            The created plugin directory path.

        Raises:
            FileExistsError: If the plugin directory already exists.
        """
        slug = name.lower().replace(" ", "-")
        plugin_dir = output_dir / slug

        if plugin_dir.exists():
            msg = f"Directory already exists: {plugin_dir}"
            raise FileExistsError(msg)

        # Create directory structure
        templates_dir = plugin_dir / "templates"
        templates_dir.mkdir(parents=True)

        # Write scaffold files
        upper_slug = slug.upper().replace("-", "_")

        plugin_yaml = plugin_dir / f"{slug}.yaml"
        plugin_yaml.write_text(
            _SCAFFOLD_PLUGIN_YAML.format(name=name, slug=slug, upper_slug=upper_slug)
        )

        template_file = templates_dir / "example.j2"
        template_file.write_text(_SCAFFOLD_TEMPLATE.format(name=name))

        readme_file = plugin_dir / "README.md"
        readme_file.write_text(_SCAFFOLD_README.format(name=name, slug=slug))

        return plugin_dir
