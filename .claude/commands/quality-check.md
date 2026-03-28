---
description: Run all quality checks — lint, typecheck, and tests with coverage
---

Run the full quality gate in sequence. Stop and report on first failure.

1. `ruff check src/ tests/` — lint check
2. `ruff format --check src/ tests/` — format check
3. `mypy src/` — type check (strict mode)
4. `pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing -v` — tests with coverage

Summarize: pass/fail for each step, coverage percentage, and any issues found.
