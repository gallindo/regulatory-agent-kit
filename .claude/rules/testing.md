---
description: Testing conventions for pytest
globs: ["tests/**/*.py"]
---

# Testing Rules

- Test files: `test_<module>.py` in `tests/unit/` or `tests/integration/`
- Use `testcontainers` for PostgreSQL and Elasticsearch in integration tests — never mock databases
- Mark integration tests with `@pytest.mark.integration`
- Mark slow tests with `@pytest.mark.slow`
- Async tests work automatically (asyncio_mode = "auto") — no `@pytest.mark.asyncio` needed
- 30-second timeout per test (global) — keep tests fast
- Coverage minimum: 80% — enforced by `pytest-cov`
- Use `httpx.AsyncClient` for testing FastAPI endpoints (not requests)
- Fixtures go in `conftest.py` at the appropriate scope level
- Assert in tests is fine (S101 is ignored by ruff)
