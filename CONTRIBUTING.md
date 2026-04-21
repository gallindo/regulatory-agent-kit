# Contributing to regulatory-agent-kit

Thank you for your interest in contributing. This guide covers everything you need to submit a quality pull request.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Writing Regulation Plugins](#writing-regulation-plugins)
- [Reporting Issues](#reporting-issues)

---

## Development Setup

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker & Docker Compose.

```bash
# 1. Fork and clone
git clone https://github.com/gallindo/regulatory-agent-kit.git
cd regulatory-agent-kit

# 2. Install all dependencies (including dev extras)
uv sync --all-extras

# 3. Copy config files
cp .env.example .env
cp rak-config.yaml.example rak-config.yaml

# 4. Start the full stack (optional — not needed for unit tests)
docker compose up -d

# 5. Apply database migrations
alembic upgrade head

# 6. Verify setup
pytest tests/unit/ -v
```

For Lite Mode development (no Docker required):

```bash
rak run --lite --regulation regulations/examples/example.yaml --repos .
```

---

## Project Structure

```
src/regulatory_agent_kit/   # All library code
regulations/                # Example and test regulation plugins
tests/unit/                 # Unit tests (no external services)
tests/integration/          # Integration tests (require Docker)
migrations/                 # Alembic database migrations
docs/                       # Documentation
infrastructure/             # Terraform IaC modules
helm/                       # Kubernetes Helm charts
```

Key architectural invariants — read before touching code:

- **Never hardcode regulatory logic in Python** — all regulation knowledge belongs in YAML plugins under `regulations/`
- **Human checkpoint gates are non-bypassable** — no code path may skip approval at impact-review or merge-review stages
- **Audit trail entries must be cryptographically signed** — Ed25519 via `cryptography` library
- **Agents are regulation-agnostic** — they receive context from plugins, never from internal logic
- **LLM calls go through LiteLLM** — never call Anthropic/OpenAI APIs directly
- **Configuration via pydantic-settings** — never parse env vars with `os.getenv()` manually
- **All custom exceptions inherit from `RAKError`** in `exceptions.py`

---

## Code Standards

### Style

- **Line length:** 99 characters
- **Python target:** 3.12+ syntax (`list[str]`, `dict[str, Any]`, `X | None`)
- **Naming:** PascalCase classes, snake_case functions/variables, UPPERCASE constants
- **No `print()`** — use `typer.echo()` in CLI, structured logging in library code

### Type Safety

All public functions require full type annotations. mypy strict mode is enforced in CI.

```bash
mypy src/
```

### Linting and Formatting

```bash
# Check
ruff check src/ tests/
ruff format --check src/ tests/

# Auto-fix
ruff check --fix src/ tests/
ruff format src/ tests/
```

### Database

- Parameterized queries only — never f-string or %-format SQL
- Repository pattern: thin classes in `database/repositories/`
- All schema changes via Alembic migrations — never run DDL directly

### Templates

- Always use `SandboxedEnvironment` from `jinja2.sandbox` — never plain `Environment`

### Running all quality checks

```bash
make check
# or: just check
```

---

## Testing

| Test type | Location | Marker | Requires |
|-----------|----------|--------|---------|
| Unit | `tests/unit/` | _(none)_ | Nothing |
| Integration | `tests/integration/` | `@pytest.mark.integration` | Docker |
| Slow | anywhere | `@pytest.mark.slow` | Varies |

```bash
# Unit only (fast, no Docker)
pytest tests/unit/ -v

# Integration (requires docker compose up -d)
pytest tests/integration/ -v -m integration

# With coverage (80% minimum enforced)
pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing
```

Rules:
- Use `testcontainers` for PostgreSQL and Elasticsearch in integration tests — never mock databases
- Use `httpx.AsyncClient` for testing FastAPI endpoints — not `requests`
- Async tests work automatically (`asyncio_mode = "auto"`) — no `@pytest.mark.asyncio` needed
- Keep tests under 30 seconds each (global timeout enforced)
- Fixtures go in `conftest.py` at the appropriate scope level

New code must maintain ≥ 80% coverage. New features should include both unit and integration tests.

---

## Submitting a Pull Request

1. **Create a branch** from `main` with a descriptive name:
   ```bash
   git checkout -b feat/my-feature
   # or: fix/issue-description, docs/update-guide, refactor/module-name
   ```

2. **Make your changes** following the code standards above.

3. **Run the full check suite** before pushing:
   ```bash
   make check   # lint + typecheck + tests
   ```

4. **Write a clear commit message:**
   ```
   feat: add support for custom remediation strategies

   Longer description of why this change is needed, not what it does.
   ```
   Prefix: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`.

5. **Open a PR** against `main`. Fill in the PR template completely — PRs missing test evidence or description of the change will be asked to revise.

6. **CI must pass** — lint, typecheck, unit tests, dependency audit all run automatically.

### What makes a good PR

- Focused: one logical change per PR
- Tested: new behaviour has unit tests; new infrastructure has integration tests
- Documented: public API changes update the relevant `docs/` file
- Minimal: no refactoring of unrelated code; no speculative abstractions

---

## Writing Regulation Plugins

Regulation plugins are **declarative YAML files** — readable by compliance officers, not just engineers. They live in separate repositories and are installed via `rak plugin install`.

See [`docs/plugin-template-guide.md`](docs/plugin-template-guide.md) for the full authoring guide, including:

- Plugin YAML schema reference
- Condition DSL (`has_*`, `is_*`, `contains_*` predicates)
- Remediation strategies (`add_annotation`, `replace_pattern`, `generate_file`, `custom_agent`, …)
- Jinja2 template context variables
- Certification tiers

The `regulations/examples/` directory has a minimal working example to fork.

---

## Reporting Issues

- **Bug reports:** use the GitHub issue template — include reproduction steps, Python version, and relevant log output.
- **Feature requests:** describe the regulation or use-case driving the request, not just the desired API.
- **Security vulnerabilities:** see [`SECURITY.md`](SECURITY.md) for responsible disclosure.
- **Questions:** open a GitHub Discussion rather than an issue.
