---
description: Scaffold a new module with proper structure, types, and tests
---

Create a new module in the regulatory-agent-kit package. Ask the user for:
1. Module name (e.g., "notifications")
2. Which package it belongs to (agents, tools, models, etc.)

Then create:
- `src/regulatory_agent_kit/<package>/<module>.py` with:
  - Module docstring
  - Proper imports
  - Type-annotated stub class or functions
  - `__all__` export list
- `tests/unit/test_<module>.py` with:
  - Import of the new module
  - At least one placeholder test with `def test_<module>_placeholder() -> None:`

Follow all rules: mypy strict types, Pydantic v2 models if data class, ruff-compatible style, 99-char line length.
