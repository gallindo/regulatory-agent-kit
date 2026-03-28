---
description: Validate a regulation plugin YAML file against the schema
---

Validate a regulation plugin. Ask the user for the plugin path (default: `regulations/dora/dora-ict-risk-2025.yaml`).

Then:
1. Read the YAML file
2. Check for required fields: id, name, version, effective_date, rules[]
3. For each rule, verify: id, description, condition, remediation_strategy
4. Check that Jinja2 templates in remediation blocks are syntactically valid
5. Verify condition DSL predicates use valid operators (has_*, is_*, contains_*)
6. Report: total rules found, validation errors, warnings about missing optional fields
