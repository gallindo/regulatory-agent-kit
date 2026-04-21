# Changelog

All notable changes to regulatory-agent-kit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] — 2026-04-21

Initial public alpha release. The full framework scaffold is implemented and tested.

### Added

**Core framework**
- Package structure across 12 subpackages with custom exception hierarchy (`RAKError` base)
- Configuration via pydantic-settings with YAML overlay and environment variable support
- Typer + Rich CLI (`rak`) with commands: `run`, `status`, `retry-failures`, `rollback`, `resume`, `cancel`, `plugin *`, `db *`, `ci analyze`

**Agent layer (PydanticAI)**
- Four specialized agents: Analyzer (violation detection), Refactor (fix application), TestGenerator (sandbox validation), Reporter (PR + audit trail)
- `@instrumented_tool` decorator for automatic MLflow/OpenTelemetry tracing on all agent tools
- Custom agent support via `custom_agent` remediation strategy and `invoke_custom_agent` tool

**Orchestration (Temporal)**
- `CompliancePipeline` workflow with 9 phases and child `RepositoryProcessor` for fan-out
- Non-bypassable human checkpoint gates (impact-review and merge-review stages)
- Lite Mode executor (`rak run --lite`) — no Docker, SQLite + terminal prompts
- Data residency routing with jurisdiction-based LLM model selection
- Workflow cancellation, retry, resume, and rollback via CLI

**Plugin system**
- Declarative YAML plugin schema validated by Pydantic v2 models
- Plugin loader with caching and Jinja2 template validation
- Condition DSL with recursive descent parser: 7 predicate types, AND/OR/NOT operators
- Condition evaluator with language detection and LLM delegation for complex rules
- Cross-regulation conflict engine: overlapping AST region detection and precedence resolution
- Plugin scaffolder (`rak plugin init`) and certification tier validation
- Plugin registry: discovery, search, publication, versioning (API + CLI + database)
- `rak plugin install <id>` installs external plugins from the registry

**Tools layer**
- Async Git client (clone, branch, commit, push, PR creation)
- GitHub and GitLab REST API provider (PRs, comments, status)
- tree-sitter AST engine (parse, find_classes, find_methods, find_annotations)
- Token-based cost estimator with model pricing tables
- Notification clients: Slack, SMTP email, generic webhook
- Rollback executor with manifest-driven action planning
- Docker-sandboxed test runner (`--network=none`, `--read-only`, CPU/memory caps)
- Elasticsearch client with BM25, kNN vector, and structured filtering strategies
- Token bucket rate limiter, file analysis cache, data residency router, secrets backends

**API layer (FastAPI)**
- Lifespan-managed application with graceful degradation on missing services
- Bearer + JWT/OIDC auth middleware with JWKS caching and HS256/RS256 support
- Routes: `POST /events`, `GET /runs`, `GET /runs/{id}`, `POST /approvals/{run_id}`, plugin registry CRUD
- `PluginRegistryStore` protocol with in-memory adapter for Lite Mode and test isolation

**Event sources**
- Pluggable `EventSource` protocol — no coupling to a specific message broker
- Implementations: Webhook (HMAC-SHA256), Kafka (credential hot-reload), SQS, file watcher, Temporal starter

**Database layer**
- Psycopg 3 `AsyncConnectionPool` with repository pattern (no ORM)
- Repositories: `AuditEntries` (append-only), `PipelineRuns`, `RepositoryProgress`, `CheckpointDecisions`, `FileAnalysisCache`, `ConflictLog`, `PluginRegistry`
- Monthly partition auto-rotation with archive export for `audit_entries`
- Alembic migrations: `001_initial_schema` (6 tables, roles, indexes) + `002_plugin_registry`
- Lite Mode SQLite adapter (5 tables, async aiosqlite)

**Observability**
- JSON-LD audit logger with 9 event types; entries cryptographically signed (Ed25519)
- Prometheus metrics registry with `@instrumented` decorator and write-ahead log for crash resilience
- MLflow + OpenTelemetry setup with OTLP export and PydanticAI autolog
- MLflow evaluation framework with scorers and experiment comparison
- Object storage backends: S3, GCS, Azure Blob with archive pipeline

**CI/CD integration**
- Shift-left compliance scanner (`rak ci scan`) with exit codes for CI gates
- GitHub and GitLab PR reviewer automation with combined markdown output
- CI/CD pipeline analysis: GHA and GitLab CI parser with OCP extension registry
- 6 compliance checks: security scanning, dependency scanning, test step, deployment approval, no hardcoded secrets, artifact signing
- `rak ci analyze` CLI command

**Infrastructure**
- Docker Compose stack: 10 services (postgres, elasticsearch, temporal, temporal-ui, litellm, mlflow, prometheus, grafana, rak-api, rak-worker)
- Multi-stage Dockerfiles for API and worker; non-root `rak` user (UID 1000)
- Helm charts for Kubernetes deployment
- Terraform IaC: 7 AWS modules (networking, rds, opensearch, s3, eks, iam, secrets) + staging/production environments
- Prometheus alert rules, Alertmanager config, pre-built Grafana dashboards
- PgBouncer connection pooling

**Testing**
- 75+ test files across `tests/unit/` and `tests/integration/`
- Integration tests use `testcontainers` for real PostgreSQL and Elasticsearch (no mocks)
- 80% coverage minimum enforced by `pytest-cov`

### Architecture decisions

- **ADR-002:** Temporal + PydanticAI over LangGraph — durability, fan-out, separation of concerns
- **ADR-003:** PostgreSQL-only with JSONB for semi-structured data; three schema namespaces (`rak`, `temporal`, `mlflow`)
- **ADR-004:** Python 3.12+, uv, Pydantic v2, Psycopg 3, FastAPI, Ruff, mypy strict
- **ADR-005:** MLflow + OpenTelemetry over Langfuse — LLM tracing + operational metrics in one stack
- **ADR-006:** Elasticsearch 8.x over pgvector — full-text + semantic vector search

### Out of scope for this repository

Regulation-specific plugins (DORA, PSD2, PCI-DSS, HIPAA, NIS2, Open Finance, etc.) are distributed as separate repositories and installed via `rak plugin install`. The framework is regulation-agnostic by design.

---

[Unreleased]: https://github.com/gallindo/regulatory-agent-kit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gallindo/regulatory-agent-kit/releases/tag/v0.1.0
