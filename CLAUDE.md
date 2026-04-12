# CLAUDE.md — regulatory-agent-kit

## Project Overview

**regulatory-agent-kit (RAK)** is an open-source Python framework for building multi-agent AI pipelines that automate regulatory compliance across software codebases. It detects compliance violations, applies fixes, generates tests, and produces immutable audit trails — all driven by declarative YAML regulation plugins, not hardcoded logic.

- **Status:** Alpha (v0.1.0) — scaffold complete, implementations are stubs
- **Architecture:** Regulation-as-configuration; agents are generic, regulatory knowledge lives in YAML plugins
- **Core principle:** Human-in-the-loop checkpoints are non-bypassable by design

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12+ |
| Package Manager | uv | latest |
| Build System | Hatchling | latest |
| Orchestration | Temporal (Python SDK) | >=1.24.0 |
| Agent Framework | PydanticAI | >=1.0.0 |
| Data Validation | Pydantic v2 + pydantic-settings | >=2.7.0 |
| HTTP API | FastAPI + Uvicorn | >=0.115.0 |
| Database | PostgreSQL 16 (Psycopg 3, no ORM) | >=3.2.0 |
| Migrations | Alembic | >=1.14.0 |
| Search Index | Elasticsearch 8.x | >=8.13.0 |
| LLM Gateway | LiteLLM | >=1.40.0 |
| CLI | Typer + Rich | >=0.12.0 |
| Observability | MLflow + OpenTelemetry | >=2.18.0 |
| AST Parsing | tree-sitter | >=0.22.0 |
| Cryptography | cryptography (Ed25519) | >=43.0.0 |

## Build / Test / Lint Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests (requires Docker services running)
pytest tests/integration/ -v -m integration

# Tests with coverage
pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing

# Lint (check only)
ruff check src/ tests/
ruff format --check src/ tests/

# Lint (auto-fix)
ruff check --fix src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# All quality checks
make check  # or: just check

# Docker Compose
docker compose up -d    # start full stack
docker compose down     # stop
docker compose build    # rebuild images

# Database migrations
alembic upgrade head                         # apply all
alembic revision --autogenerate -m "name"    # create new

# CLI (after install)
rak run --regulation regulations/examples/example.yaml --repos <url> --checkpoint-mode terminal
rak run --lite --regulation <path> --repos <path>  # no Docker required
```

## Coding Standards

### Style
- **Line length:** 99 characters
- **Python target:** 3.12 (use modern syntax: `list[str]`, `dict[str, Any]`, `X | None`)
- **Naming:** PascalCase classes, snake_case functions/variables, UPPERCASE constants
- **Imports:** sorted by ruff/isort; first-party = `regulatory_agent_kit`
- **No print():** use `typer.echo()` for CLI output, structured logging elsewhere

### Type Safety
- **mypy strict mode** — all functions must have type annotations
- **Pydantic v2** for all data models — use `model_validator`, not `@validator`
- **pydantic-settings** for configuration — never parse env vars manually
- Guard circular imports with `if TYPE_CHECKING:`

### Async
- **pytest-asyncio mode:** `auto` — async tests just work, no decorator needed
- **Psycopg 3 AsyncConnectionPool** for database access
- **uvloop** as default event loop in production

### Database
- **No ORM** — raw SQL via Psycopg 3 with parameterized queries
- **Repository pattern** — thin data access classes in `database/repositories/`
- **Three PostgreSQL schemas:** `rak` (app, Alembic-managed), `temporal` (DO NOT TOUCH), `mlflow` (DO NOT TOUCH)
- **UUIDs** for all primary keys
- **audit_entries table is append-only** — INSERT/SELECT only, never UPDATE/DELETE

### Testing
- **Minimum coverage:** 80% (enforced)
- **Markers:** `@pytest.mark.integration` (requires Docker), `@pytest.mark.slow`
- **Real services over mocks:** use `testcontainers` for PostgreSQL and Elasticsearch in integration tests
- **Timeout:** 30 seconds per test (global)

### Architecture Rules
- **Never hardcode regulatory logic** — all regulation knowledge belongs in YAML plugins under `regulations/`
- **Human checkpoints are non-bypassable** — no code path may skip approval gates
- **Audit trail entries must be cryptographically signed** — use Ed25519 via `cryptography` library
- **Agents are regulation-agnostic** — they receive context from plugins, not from internal logic
- **Event sources are pluggable** — implement the `EventSource` interface; never couple to a specific message broker

## Project Structure

```
src/regulatory_agent_kit/
├── cli.py              # Typer CLI entry point (rak command)
├── config.py           # pydantic-settings configuration
├── exceptions.py       # Custom exception hierarchy (RAKError base)
├── api/                # FastAPI application (webhooks, approvals)
├── agents/             # PydanticAI agent definitions (analyzer, refactor, test_generator, reporter)
├── orchestration/      # Temporal workflow and activity definitions
├── models/             # Pydantic data models (events, pipeline, impact_map, audit)
├── tools/              # Agent tools (git, ast_parser, test_runner, elasticsearch)
├── plugins/            # YAML plugin loader, schema, condition DSL
├── templates/          # Jinja2 sandboxed template engine for code generation
├── event_sources/      # Pluggable event sources (kafka, webhook, sqs, file)
├── database/           # Psycopg 3 connection pool + repository pattern
├── observability/      # MLflow + OpenTelemetry integration
└── util/               # Crypto (Ed25519), structured logging, validation
```

## Docker Services (docker-compose.yml)

| Service | Port | Purpose |
|---------|------|---------|
| postgres | 5432 | Application + Temporal + MLflow data |
| elasticsearch | 9200 | Regulatory knowledge base |
| temporal | 7233 | Workflow engine (gRPC) |
| temporal-ui | 8233 | Temporal web dashboard |
| litellm | 4000 | LLM proxy gateway |
| mlflow | 5000 | LLM trace tracking |
| prometheus | 9090 | Metrics collection |
| grafana | 3000 | Dashboards |
| rak-api | 8000 | FastAPI server |
| rak-worker | — | Temporal worker (no exposed port) |

## Key ADRs

- **ADR-002:** Temporal + PydanticAI over LangGraph (durability, fan-out, separation of concerns)
- **ADR-003:** PostgreSQL-only (single DB for all schemas; JSONB for semi-structured data)
- **ADR-004:** Python 3.12+, uv, Pydantic v2, Psycopg 3, FastAPI, Ruff, mypy
- **ADR-005:** MLflow + OpenTelemetry over Langfuse (LLM tracing + operational metrics)
- **ADR-006:** Elasticsearch 8.x over pgvector (full-text + semantic vector search)

## Ruff Rules

Enabled rule sets: `E W F I N UP B SIM TCH RUF S T20`. Exception: `S101` ignored (assert allowed in tests).

## Environment Setup

1. Copy `.env.example` → `.env` and set at minimum `ANTHROPIC_API_KEY`
2. Copy `rak-config.yaml.example` → `rak-config.yaml` for pipeline configuration
3. `docker compose up -d` for full stack, or `rak run --lite` for evaluation mode
