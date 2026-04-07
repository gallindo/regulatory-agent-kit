# ADR-004: Python Stack Selection

**Status:** Accepted
**Date:** 2026-03-27
**Decision Makers:** Engineering Team
**Related:** [ADR-002](002-langgraph-vs-temporal-pydanticai.md) (Temporal + PydanticAI), [ADR-003](003-database-selection.md) (PostgreSQL)

---

## Context

With the orchestration framework (Temporal + PydanticAI) and database (PostgreSQL) decisions settled, this ADR selects the concrete Python libraries for every layer of the `regulatory-agent-kit` stack. The goal is a coherent, minimal dependency set where each library earns its place.

### Decisions Already Made

| Layer | Decision | Source |
|---|---|---|
| Orchestration | Temporal (self-hosted) + Python SDK | ADR-002 |
| Agent framework | PydanticAI | ADR-002 |
| LLM gateway | LiteLLM | `framework-spec.md` SS6 |
| Database | PostgreSQL (single instance) | ADR-003 |
| Search / knowledge base | Elasticsearch 8.x | `framework-spec.md` SS5 |
| LLM trace collector | MLflow (see [ADR-005](005-llm-observability-platform.md)) | ADR-005 |
| Operational metrics | OpenTelemetry -> Prometheus | `framework-spec.md` SS7 |

### Layers Requiring Library Selection

| Layer | Concern | Options to evaluate |
|---|---|---|
| L1 | Python version | 3.11 vs 3.12 vs 3.13 |
| L2 | Project / dependency management | pip + requirements.txt vs Poetry vs uv vs PDM |
| L3 | Data validation and serialization | Pydantic (already implicit via PydanticAI) — confirm version and role |
| L4 | Database access (application tables) | SQLAlchemy vs asyncpg vs Psycopg 3 |
| L5 | Database migrations | Alembic vs custom vs Temporal-managed |
| L6 | HTTP framework (webhook event source, API) | FastAPI vs Litestar vs Starlette |
| L7 | Async runtime | asyncio (stdlib) vs uvloop vs AnyIO |
| L8 | AST parsing | tree-sitter |
| L9 | Git operations | GitPython vs pygit2 vs subprocess (git CLI) |
| L10 | Kafka client | confluent-kafka vs aiokafka |
| L11 | Elasticsearch client | elasticsearch-py (official) |
| L12 | Template engine (remediation templates) | Jinja2 |
| L13 | YAML parsing (plugins) | PyYAML vs ruamel.yaml |
| L14 | Cryptographic signing (audit, checkpoints) | cryptography vs PyNaCl |
| L15 | CLI framework | Click vs Typer |
| L16 | Testing | pytest ecosystem |
| L17 | Linting / formatting | Ruff |
| L18 | Type checking | mypy vs pyright |
| L19 | Observability SDK | opentelemetry-sdk + langfuse |
| L20 | Task runner / build | Makefile vs Just vs Nox vs Taskfile |

---

## Decisions

### L1 — Python 3.12

**Decision:** Python 3.12 (minimum). Support 3.12 and 3.13.

**Rationale:**
- Python 3.12 provides significant performance improvements (10-15% faster than 3.11), improved error messages, and `type` statement for type aliases.
- Python 3.11 reaches end-of-life October 2027 — starting a new project on it provides limited runway.
- Python 3.13 is current but some dependencies (particularly native extensions like `confluent-kafka`, `tree-sitter`) may lag in wheel availability.
- Temporal Python SDK requires 3.9+. PydanticAI requires 3.9+. No upper bound conflicts.
- Target: develop on 3.12, CI tests on 3.12 + 3.13.

---

### L2 — uv (Project & Dependency Management)

**Decision:** `uv` for project management, dependency resolution, virtual environment management, and lockfile generation.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| pip + requirements.txt | Universal, zero learning curve | No lockfile, no dependency resolution guarantees, manual venv management |
| Poetry | Mature, lockfile, publishing support | Slow resolution, custom `pyproject.toml` sections being replaced by PEP 621, resolver conflicts with large dependency trees |
| PDM | PEP 621 native, fast | Smaller community than Poetry or uv |
| **uv** | Extremely fast (10-100x pip), PEP 621 native, lockfile (`uv.lock`), venv management, Python version management, `--require-hashes` for supply chain security | Newer tool (Astral, creators of Ruff), still maturing |

**Rationale:**
- `uv` resolves the dependency tree for this project (Temporal SDK + PydanticAI + LiteLLM + Elasticsearch + tree-sitter + Kafka + cryptography) in seconds, not minutes.
- Native `--require-hashes` support aligns with the architecture's supply chain security requirement (`framework-spec.md` SS9: "Pinned deps with hash verification").
- `uv.lock` provides reproducible builds. `uv export --format requirements-txt` generates `requirements.txt` for Docker builds.
- Same creator as Ruff (Astral) — consistent toolchain.
- PEP 621 `pyproject.toml` — no proprietary metadata format.

---

### L3 — Pydantic v2

**Decision:** Pydantic v2 for all data validation, serialization, and settings management.

**Rationale:**
- PydanticAI is built on Pydantic v2 — it is already a transitive dependency.
- Pydantic models define: plugin YAML schema validation, agent input/output contracts, event schemas, API request/response models, audit entry structure, database record DTOs.
- `pydantic-settings` for configuration management (environment variables, `.env` files, secrets).
- Pydantic v2's Rust-based core (`pydantic-core`) provides 5-50x faster validation than v1.
- The architecture mandates "Pydantic output validation" as a security boundary (`framework-spec.md` SS9).

---

### L4 — Psycopg 3 (async) for Database Access

**Decision:** Psycopg 3 (`psycopg[binary]`) with async support for application database access. No ORM.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| SQLAlchemy 2.0 + asyncio | Full ORM, migration integration (Alembic), wide adoption | Heavy abstraction for what are mostly simple INSERT/SELECT queries; adds large dependency; ORM overhead for append-only audit tables |
| asyncpg | Fastest PostgreSQL driver (C extension, binary protocol) | No sync mode; limited prepared statement caching in some patterns; no connection pooling built-in |
| **Psycopg 3** | Official PostgreSQL adapter (successor to psycopg2); async + sync; connection pooling; COPY support; pipeline mode; typed; `JSONB` native support | Slightly slower than asyncpg in microbenchmarks (negligible at application scale) |

**Rationale:**
- The application's database queries are straightforward: `INSERT` audit entries, `UPDATE` repository status, `SELECT` by run_id/status. An ORM adds abstraction weight without commensurate value.
- Psycopg 3 provides async support (`psycopg.AsyncConnection`) for non-blocking database access within Temporal activities.
- Built-in connection pooling (`psycopg_pool.AsyncConnectionPool`) — no need for PgBouncer in simple deployments.
- Native `JSONB` support with automatic Pydantic model serialization via `psycopg.types.json`.
- `COPY` protocol support for bulk audit entry insertion (batch writes).
- The official PostgreSQL adapter — alignment with the "single database" decision in ADR-003.

**Pattern:**
```python
# Thin repository layer using Psycopg 3 + Pydantic models
class AuditRepository:
    def __init__(self, pool: AsyncConnectionPool): ...
    async def insert(self, entry: AuditEntry) -> None: ...
    async def get_by_run(self, run_id: UUID) -> list[AuditEntry]: ...
```

---

### L5 — Alembic for Database Migrations

**Decision:** Alembic for the `rak` schema migrations. Temporal manages its own schema separately.

**Rationale:**
- Alembic is the standard Python migration tool, works with raw SQL (does not require SQLAlchemy ORM).
- Temporal server manages its own database schema via its built-in `temporal-sql-tool` — the application must not touch Temporal's tables.
- Alembic manages the `rak` schema tables (pipeline_runs, repository_progress, audit_entries, checkpoint_decisions, conflict_log) defined in ADR-003.
- Migrations are version-controlled alongside application code.
- `alembic upgrade head` runs as part of the deployment pipeline.

---

### L6 — FastAPI (HTTP Framework)

**Decision:** FastAPI for the webhook event source endpoint, the human checkpoint approval API, and the pipeline management API (`rak status`, `rak retry-failures`).

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| **FastAPI** | Async-native, Pydantic integration (auto-validation, OpenAPI generation), wide adoption, excellent docs | Starlette dependency (lightweight), slightly opinionated |
| Litestar | Faster than FastAPI in benchmarks, no Starlette dependency, DTO system | Smaller community, fewer third-party integrations |
| Starlette | Minimal, FastAPI is built on it | No auto-validation, no OpenAPI generation without manual work |

**Rationale:**
- FastAPI's native Pydantic v2 integration means request/response validation uses the same models as the rest of the application — zero duplication.
- Auto-generated OpenAPI schema is valuable for the CI/CD integration API and the webhook event source.
- The architecture specifies a "built-in HTTP endpoint (FastAPI)" for `WebhookEventSource` (`framework-spec.md` SS5.1).
- Async support aligns with Temporal's async Python SDK.
- Largest ecosystem for middleware (CORS, authentication, rate limiting).

---

### L7 — uvloop + AnyIO

**Decision:** `uvloop` as the event loop policy for production. `anyio` as the async abstraction where needed.

**Rationale:**
- `uvloop` provides 2-4x faster asyncio event loop (libuv-based). Drop-in replacement.
- PydanticAI uses `anyio` internally. Using `anyio` in application code where applicable ensures compatibility.
- Temporal Python SDK uses `asyncio` natively.
- `uvicorn` (FastAPI's ASGI server) supports `uvloop` out of the box via `--loop uvloop`.

---

### L8 — tree-sitter

**Decision:** `tree-sitter` (Python bindings) for AST parsing across all supported languages.

**Rationale:**
- The architecture mandates tree-sitter for universal AST parsing (`framework-spec.md` SS2, "AST Tools (tree-sitter)").
- Supports partial parsing (syntactically invalid files still produce usable ASTs) — critical for analyzing code mid-refactor.
- Language grammars are separate packages (`tree-sitter-java`, `tree-sitter-python`, `tree-sitter-kotlin`), installed per deployment's language scope.
- v1.0 scope: Java, Kotlin, Python. v2.0: Go, TypeScript.

---

### L9 — subprocess (Git CLI)

**Decision:** Shell out to the `git` CLI via `subprocess` (wrapped in a thin async adapter). Not GitPython, not pygit2.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| GitPython | Pythonic API, widely used | Shells out to `git` anyway for most operations; memory leaks on long-running processes; maintenance concerns |
| pygit2 | True libgit2 binding (no subprocess) | Complex build (requires libgit2); limited GitHub/GitLab API integration; credential handling is manual |
| **subprocess (git CLI)** | Uses the exact same `git` binary as the CI/CD environment; no abstraction mismatch; predictable behavior; minimal dependency | Requires `git` installed; string parsing of output; no Python API |

**Rationale:**
- The framework performs a small set of Git operations: clone, checkout, branch, add, commit, diff, push. These map 1:1 to CLI commands.
- GitPython adds a dependency that mostly wraps `subprocess` anyway, with known memory leak issues in long-running processes (the pipeline processes hundreds of repos).
- The `git` CLI is guaranteed to be present in every deployment environment (Docker images, CI runners, developer machines).
- Git provider API interactions (creating PRs, commenting) use the provider's REST API via `httpx`, not the Git protocol.

**Pattern:**
```python
class GitClient:
    async def clone(self, url: str, path: Path, depth: int = 1) -> None: ...
    async def create_branch(self, repo: Path, name: str) -> None: ...
    async def diff(self, repo: Path) -> str: ...
```

---

### L10 — confluent-kafka

**Decision:** `confluent-kafka` for Kafka integration.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| **confluent-kafka** | Official Confluent client; C-based librdkafka (highest performance); Schema Registry support; production-proven | C extension (build complexity on some platforms); not async-native (uses callback/polling model) |
| aiokafka | Pure Python, async-native | Lower throughput; less mature; no Schema Registry integration |

**Rationale:**
- `confluent-kafka` is the production standard for Python Kafka clients. Used at scale by the target customer profile (financial services, enterprise).
- Schema Registry support for Avro/Protobuf event schemas aligns with the architecture's event schema validation.
- The Kafka consumer runs in its own thread/process (not in the async event loop), so async-native is not required — the consumer receives events and triggers Temporal workflows via the Temporal SDK.
- Wheels are available for Linux/macOS/Windows on Python 3.12.

---

### L11 — elasticsearch-py (Official Client)

**Decision:** `elasticsearch[async]` (official Elasticsearch Python client with async support).

**Rationale:**
- Official client maintained by Elastic. Supports Elasticsearch 8.x.
- Async support via `AsyncElasticsearch` for non-blocking index and search operations within Temporal activities.
- Used by the Analyzer Agent to query the regulatory knowledge base and by the event consumer to index regulatory changes.

---

### L12 — Jinja2

**Decision:** Jinja2 for remediation and test template rendering.

**Rationale:**
- The architecture specifies Jinja2 templates for all remediation strategies (`framework-spec.md` SS3.4).
- Plugins reference templates as `.j2` files (`template: "templates/audit_log_annotation.j2"`).
- Jinja2 is the de facto Python template engine. Sandboxed mode (`SandboxedEnvironment`) prevents template injection in user-contributed plugins.

---

### L13 — ruamel.yaml

**Decision:** `ruamel.yaml` for YAML parsing of regulation plugins.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| PyYAML | Ubiquitous, fast C loader | No round-trip preservation; no YAML 1.2 support; `yaml.safe_load` only |
| **ruamel.yaml** | YAML 1.2 compliant; round-trip preservation (comments, ordering); safe by default | Slightly slower than PyYAML's C loader; API is more verbose |

**Rationale:**
- Regulation plugins are authored and reviewed by compliance officers and legal teams. Preserving YAML comments, key ordering, and formatting during `rak plugin validate` / `rak plugin init` operations is essential for a good contributor experience.
- YAML 1.2 compliance avoids the "Norway problem" (PyYAML's YAML 1.1 treats `NO` as boolean `false`).
- Safe loading by default — no arbitrary Python object deserialization.

---

### L14 — cryptography

**Decision:** `cryptography` library for audit log signing and checkpoint approval signatures.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| **cryptography** | Comprehensive; Ed25519, RSA, ECDSA; backed by PyCA; FIPS-capable (via OpenSSL backend); widely audited | Large dependency (includes OpenSSL bindings) |
| PyNaCl | Simple API; libsodium-based | Limited to NaCl algorithms; no RSA/ECDSA (some enterprise PKI requires RSA) |

**Rationale:**
- Enterprise financial institutions may require RSA or ECDSA signatures to integrate with existing PKI infrastructure. `cryptography` supports all common algorithms.
- Ed25519 as the default signing algorithm (fast, small signatures, safe by design). RSA/ECDSA available for enterprise requirements.
- FIPS-capable builds are possible via the OpenSSL backend — relevant for US financial institutions and government-adjacent deployments.

---

### L15 — Typer

**Decision:** Typer for the `rak` CLI.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| Click | Mature, stable, composable, wide adoption | Verbose decorator syntax; no auto-generated help from type hints |
| **Typer** | Built on Click; auto-generates CLI from type hints; Pydantic-compatible; less boilerplate | Depends on Click (adds no new dependency if Click is already transitive); Rich integration for output |

**Rationale:**
- Typer leverages Python type hints to auto-generate CLI argument parsing — consistent with the Pydantic-first approach.
- Built on Click, so all Click features (groups, context, plugins) are available.
- Rich integration for formatted terminal output (progress bars for multi-repo processing, tables for `rak status`).
- CLI commands: `rak run`, `rak status`, `rak resume`, `rak retry-failures`, `rak rollback`, `rak plugin init/validate/test/search`.

---

### L16 — pytest Ecosystem

**Decision:** `pytest` with `pytest-asyncio`, `pytest-cov`, `pytest-timeout`, `testcontainers-python`.

**Rationale:**
- `pytest` is the standard Python test framework.
- `pytest-asyncio` for testing async Temporal activities and PydanticAI agents.
- `pytest-cov` for coverage reporting.
- `pytest-timeout` to prevent hanging tests (important with LLM and network calls).
- `testcontainers-python` for integration tests with PostgreSQL and Elasticsearch containers — aligns with "real database, not mocks" for critical infrastructure tests.
- `pytest-docker` as an alternative for full-stack integration tests (Temporal + PostgreSQL + Elasticsearch).

---

### L17 — Ruff

**Decision:** Ruff for linting and formatting (replaces Black, isort, flake8, pylint for most rules).

**Rationale:**
- Single tool for linting + formatting. 10-100x faster than the tools it replaces.
- Same creator as `uv` (Astral) — consistent toolchain.
- Configured in `pyproject.toml`. Rules: `["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "SIM", "TCH", "RUF"]`.
- Line length: 120 (financial services codebases tend toward descriptive naming).

---

### L18 — mypy (Strict Mode)

**Decision:** mypy in strict mode for static type checking.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| **mypy** | Most mature; widest plugin ecosystem; strict mode; Pydantic plugin (`pydantic.mypy`) | Slower than pyright on large codebases |
| pyright | Faster; better inference; Microsoft-backed | Stricter than mypy in some edge cases (can cause friction with third-party stubs); fewer plugins |

**Rationale:**
- `pydantic.mypy` plugin provides full type-checking of Pydantic models (field validators, model inheritance, serialization). This is critical given that Pydantic models are the backbone of the application's data layer.
- Strict mode enforces: no implicit `Any`, no untyped definitions, no untyped decorators. Appropriate for a framework that will be used in regulated environments.
- CI runs mypy on every PR.

---

### L19 — OpenTelemetry SDK + MLflow

**Decision:** `opentelemetry-sdk` + `opentelemetry-exporter-otlp` for operational metrics. `mlflow` for LLM-specific tracing. See [ADR-005](005-llm-observability-platform.md) for the full evaluation.

**Rationale:**
- Temporal has native OpenTelemetry interceptors (`temporalio.contrib.opentelemetry`). Every workflow start, activity execution, signal, and timer is automatically traced.
- MLflow provides native PydanticAI integration via `mlflow.pydantic_ai.autolog()` — first-class SDK-level tracing, not an OTel bridge.
- LiteLLM native callback (`success_callback=["mlflow"]`) for automatic LLM call tracing.
- MLflow uses PostgreSQL + S3 — no ClickHouse or additional databases required (aligns with ADR-003).
- MLflow server is Python/Flask — consistent with the Python-only stack.
- Apache 2.0 license, Linux Foundation governance — strongest long-term stability.
- OpenTelemetry -> Prometheus exporter for Grafana dashboards (pipeline health, latency, error rates).
- The two-layer observability model: OTel for infrastructure, MLflow for AI — matches the architecture's separation of operational vs. audit observability.

---

### L20 — Just (Task Runner)

**Decision:** `just` (command runner) for development tasks.

**Options considered:**

| Tool | Strengths | Weaknesses |
|---|---|---|
| Makefile | Universal, zero-install | Arcane syntax, tab sensitivity, poor cross-platform |
| Nox | Python-native, multi-environment testing | Overkill for task running; better for CI matrix testing |
| Taskfile (go-task) | YAML-based, cross-platform | Requires Go binary; YAML for commands is awkward |
| **just** | Clean syntax, cross-platform, `.env` loading, argument passing, shell-agnostic | Requires install (available via `cargo install just`, `brew`, or `uv tool install`) |

**Rationale:**
- `just` replaces `Makefile` with a cleaner syntax and no tab-sensitivity issues.
- `.env` file loading built-in — useful for development configuration.
- Commands: `just test`, `just lint`, `just migrate`, `just dev` (starts Docker Compose + workers), `just fmt`.

---

## Full Stack Summary

```
+-----------------------------------------------------+
|                   regulatory-agent-kit                |
+-----------------------------------------------------+
|  Runtime          | Python 3.12+                     |
|  Package Manager  | uv (lockfile, hashes)            |
|  Task Runner      | just                             |
+-----------------------------------------------------+
|  ORCHESTRATION                                       |
|  Workflow engine   | Temporal (self-hosted)           |
|  Workflow SDK      | temporalio                       |
|  Agent framework   | pydantic-ai                      |
|  LLM gateway       | litellm                          |
|  Data validation   | pydantic v2                      |
+-----------------------------------------------------+
|  DATA                                                |
|  Database          | PostgreSQL 16+                   |
|  DB driver         | psycopg[binary] (async)          |
|  Migrations        | alembic                          |
|  Search index      | elasticsearch[async]             |
+-----------------------------------------------------+
|  INFRASTRUCTURE                                      |
|  HTTP framework    | fastapi + uvicorn                |
|  Async runtime     | asyncio + uvloop                 |
|  Kafka client      | confluent-kafka                  |
|  Git operations    | subprocess (git CLI)             |
|  HTTP client       | httpx (Git provider REST APIs)   |
+-----------------------------------------------------+
|  DOMAIN                                              |
|  AST parsing       | tree-sitter                      |
|  Templates         | jinja2 (sandboxed)               |
|  YAML parsing      | ruamel.yaml                      |
|  Crypto signing    | cryptography                     |
+-----------------------------------------------------+
|  CLI                                                 |
|  CLI framework     | typer + rich                     |
+-----------------------------------------------------+
|  OBSERVABILITY                                       |
|  OTel SDK          | opentelemetry-sdk + otlp export  |
|  LLM tracing       | mlflow (ADR-005)                 |
|  Metrics           | prometheus-client                |
+-----------------------------------------------------+
|  QUALITY                                             |
|  Testing           | pytest + pytest-asyncio          |
|                    | testcontainers-python            |
|  Linting/format    | ruff                             |
|  Type checking     | mypy (strict, pydantic plugin)   |
+-----------------------------------------------------+
```

### pyproject.toml Dependencies

```toml
[project]
name = "regulatory-agent-kit"
requires-python = ">=3.12"

dependencies = [
    # Orchestration
    "temporalio>=1.24.0",
    "pydantic-ai>=1.0.0",
    "litellm>=1.40.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",

    # Data
    "psycopg[binary,pool]>=3.2.0",
    "alembic>=1.14.0",
    "elasticsearch[async]>=8.13.0",

    # Infrastructure
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "uvloop>=0.20.0",
    "httpx>=0.27.0",
    "confluent-kafka>=2.5.0",
    "anyio>=4.4.0",

    # Domain
    "tree-sitter>=0.22.0",
    "jinja2>=3.1.0",
    "ruamel.yaml>=0.18.0",
    "cryptography>=43.0.0",

    # CLI
    "typer>=0.12.0",
    "rich>=13.7.0",

    # Observability
    "opentelemetry-sdk>=1.25.0",
    "opentelemetry-exporter-otlp>=1.25.0",
    "mlflow>=2.18.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "pytest-timeout>=2.3.0",
    "testcontainers[postgres,elasticsearch]>=4.7.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[project.scripts]
rak = "regulatory_agent_kit.cli:app"
```

---

## Consequences

1. **Pydantic-centric data layer** — Pydantic v2 models are the single source of truth for data shapes across all layers: YAML plugin validation, agent I/O contracts, API schemas, database DTOs, and event schemas. No separate serialization formats.

2. **No ORM** — Psycopg 3 with thin repository classes keeps the database layer explicit and debuggable. SQL queries are visible in the codebase, not hidden behind ORM abstractions.

3. **Astral toolchain (uv + Ruff)** — Consistent, fast developer tooling from a single vendor. Both tools are open-source (MIT/Apache-2.0).

4. **Minimal dependency tree** — Each library was selected to avoid overlapping responsibilities. No LangChain dependency remains after the ADR-002 decision.

5. **Async-first but not async-only** — Temporal activities and FastAPI handlers are async. The CLI (`rak run --lite`) supports synchronous execution for evaluation mode. Psycopg 3 supports both modes.

6. **Supply chain security** — `uv.lock` with hash verification, `pip-audit` in CI, SBOM generation via Syft/CycloneDX. Aligns with `framework-spec.md` SS9.

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| `uv` is a young tool | MEDIUM | `uv export --format requirements-txt` generates a standard requirements file as fallback. Migration to pip-tools or Poetry is straightforward since `pyproject.toml` uses PEP 621. |
| Psycopg 3 without ORM increases SQL maintenance burden | LOW | The application has ~10 distinct queries. A thin repository pattern with Pydantic models for input/output keeps it manageable. If query complexity grows, SQLAlchemy Core (not ORM) can be added later without rewriting. |
| `confluent-kafka` C extension build issues on non-standard platforms | LOW | Pre-built wheels available for Linux (manylinux), macOS (arm64 + x86_64), Windows. Docker builds use standard Linux images. Alpine requires musl workaround (use `slim` base image instead). |
| tree-sitter language grammar version drift | LOW | Pin grammar package versions. CI tests validate parsing against sample files for each supported language. |

---

## References

- [uv Documentation](https://docs.astral.sh/uv/)
- [Psycopg 3 Documentation](https://www.psycopg.org/psycopg3/docs/)
- [Temporal Python SDK](https://docs.temporal.io/develop/python)
- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [tree-sitter Python Bindings](https://github.com/tree-sitter/py-tree-sitter)
- [ruamel.yaml Documentation](https://yaml.readthedocs.io/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [`docs/framework-spec.md`](../framework-spec.md) — Framework architecture specification
- [ADR-002](002-langgraph-vs-temporal-pydanticai.md) — Temporal + PydanticAI selection
- [ADR-003](003-database-selection.md) — PostgreSQL selection
