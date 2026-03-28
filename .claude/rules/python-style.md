---
description: Python code style rules for regulatory-agent-kit
globs: ["src/**/*.py", "tests/**/*.py"]
---

# Python Style Rules

- Use Python 3.12+ syntax: `list[str]` not `List[str]`, `X | None` not `Optional[X]`
- Line length: 99 characters maximum
- All functions must have full type annotations (mypy strict mode)
- Use `from __future__ import annotations` only if needed for forward refs; prefer `if TYPE_CHECKING:` guards
- No bare `except:` — always catch specific exceptions
- No `print()` — use `typer.echo()` in CLI, structured logging in library code
- Import order enforced by ruff isort: stdlib → third-party → first-party (`regulatory_agent_kit`)
- Use PascalCase for classes, snake_case for functions/variables/modules, UPPERCASE for constants
- Docstrings on all public classes and functions (Google style)
- Use Pydantic v2 API: `model_validator` not `@validator`, `model_dump()` not `.dict()`
