# regulatory-agent-kit

  .claude/rules/ (6 files)

  ┌─────────────────┬────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────┐
  │      File       │                 Scope                  │                                    Key Rules                                    │
  ├─────────────────┼────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤
  │ python-style.md │ src/**/*.py, tests/**/*.py             │ Python 3.12+ syntax, 99-char lines, mypy strict, no print(), Pydantic v2 API    │
  ├─────────────────┼────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤
  │ database.md     │ database/**/*.py                       │ Psycopg 3 only, parameterized SQL, repository pattern, append-only audit table  │
  ├─────────────────┼────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤
  │ architecture.md │ src/**/*.py                            │ No hardcoded regulations, non-bypassable checkpoints, LiteLLM for all LLM calls │
  ├─────────────────┼────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤
  │ testing.md      │ tests/**/*.py                          │ testcontainers over mocks, 80% coverage, async auto mode, 30s timeout           │
  ├─────────────────┼────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤
  │ docker.md       │ docker/**, docker-compose.yml          │ python:3.12-slim, non-root user, multi-stage builds, named volumes              │
  ├─────────────────┼────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤
  │ plugins.md      │ regulations/**/*.yaml, plugins/**/*.py │ Declarative YAML, SandboxedEnvironment, ruamel.yaml, condition DSL              │
  └─────────────────┴────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────┘

  .claude/commands/ (5 files)

  ┌──────────────────┬───────────────────────────────────────────────────────────────┐
  │     Command      │                            Purpose                            │
  ├──────────────────┼───────────────────────────────────────────────────────────────┤
  │ /stack-up        │ Start Docker Compose and verify all service health            │
  ├──────────────────┼───────────────────────────────────────────────────────────────┤
  │ /quality-check   │ Run lint + typecheck + tests with coverage in sequence        │
  ├──────────────────┼───────────────────────────────────────────────────────────────┤
  │ /new-module      │ Scaffold a new module with types, tests, and proper structure │
  ├──────────────────┼───────────────────────────────────────────────────────────────┤
  │ /new-migration   │ Create and validate an Alembic migration                      │
  ├──────────────────┼───────────────────────────────────────────────────────────────┤
  │ /validate-plugin │ Validate a regulation plugin YAML against the schema          │
  └──────────────────┴───────────────────────────────────────────────────────────────┘

  .claude/hooks/ (3 files)

  ┌────────────────┬───────────────────────┬──────────────────────────────────────────────────────────────────┐
  │      Hook      │        Trigger        │                              Checks                              │
  ├────────────────┼───────────────────────┼──────────────────────────────────────────────────────────────────┤
  │ pre-commit     │ Before git commit     │ ruff lint, format, mypy, unit tests, secrets scan                │
  ├────────────────┼───────────────────────┼──────────────────────────────────────────────────────────────────┤
  │ post-migration │ After alembic upgrade │ Current head, roundtrip downgrade/upgrade, audit table integrity │
  ├────────────────┼───────────────────────┼──────────────────────────────────────────────────────────────────┤
  │ post-test      │ After pytest          │ Coverage >= 80%, slow test detection, flaky test analysis        │
  └────────────────┴───────────────────────┴──────────────────────────────────────────────────────────────────┘

  .claude/agents/ (5 files)

  ┌─────────────────────┬────────────────────────────────────────────────────────────────┐
  │        Agent        │                             Domain                             │
  ├─────────────────────┼────────────────────────────────────────────────────────────────┤
  │ database-agent      │ PostgreSQL schemas, Alembic migrations, Psycopg 3 repositories │
  ├─────────────────────┼────────────────────────────────────────────────────────────────┤
  │ orchestration-agent │ Temporal workflows, pipeline state machine, checkpoint gates   │
  ├─────────────────────┼────────────────────────────────────────────────────────────────┤
  │ compliance-agent    │ YAML regulation plugins, condition DSL, Jinja2 templates       │
  ├─────────────────────┼────────────────────────────────────────────────────────────────┤
  │ observability-agent │ MLflow tracing, OpenTelemetry, Prometheus, Grafana             │
  ├─────────────────────┼────────────────────────────────────────────────────────────────┤
  │ api-agent           │ FastAPI endpoints, webhooks, approval workflows                │
  └─────────────────────┴────────────────────────────────────────────────────────────────┘
