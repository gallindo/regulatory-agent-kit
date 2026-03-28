---
description: Regulation plugin authoring rules
globs: ["regulations/**/*.yaml", "regulations/**/*.yml", "src/regulatory_agent_kit/plugins/**/*.py"]
---

# Plugin Rules

- Regulation plugins are declarative YAML — readable by compliance officers, not just engineers
- Plugin schema is validated by Pydantic models in `plugins/schema.py`
- Use `ruamel.yaml` for YAML parsing (preserves comments and key ordering)
- Condition DSL uses `has_*`, `is_*`, `contains_*` predicates for code pattern matching
- Remediation strategies: add_annotation, add_configuration, replace_pattern, add_dependency, generate_file, custom_agent
- Templates use Jinja2 SandboxedEnvironment — never use regular Jinja2 Environment
- Plugin files live under `regulations/<regulation-name>/` with a README.md
