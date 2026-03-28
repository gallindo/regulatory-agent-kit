---
description: Pre-commit quality gate — runs before every git commit
---

# Pre-Commit Hook

Before committing, run these checks in order. Fail the commit if any step fails.

1. **Lint:** `ruff check src/ tests/` — no lint errors
2. **Format:** `ruff format --check src/ tests/` — code is formatted
3. **Types:** `mypy src/` — no type errors in strict mode
4. **Tests:** `pytest tests/unit/ -q --timeout=30` — all unit tests pass
5. **Secrets:** Scan staged files for patterns: `API_KEY=sk-`, `PASSWORD=`, `SECRET=` with actual values — block if found

## Setup

Install via pre-commit framework:

```bash
pre-commit install
```

Or add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]
```
