# regulatory-agent-kit — Implementation Plan

> **Version:** 1.1
> **Date:** 2026-03-28
> **Status:** Active
> **Scope:** Phase 1 (v1.0) — Foundation. Takes the project from scaffold (empty `__init__.py` stubs) to a working end-to-end pipeline.
> **Source documents:** `docs/architecture.md`, `docs/sad.md`, `docs/hld.md`, `docs/lld.md`, `docs/data-model.md`, `docs/cli-reference.md`, `docs/infrastructure.md`, `docs/regulatory-agent-kit.md`

---

## Current State

The repository contains:
- Complete documentation suite (architecture, SAD, HLD, LLD, data model, 6 ADRs, CLI reference, infrastructure)
- Project scaffold: `pyproject.toml`, Docker Compose, Dockerfiles, Alembic config, Makefile/Justfile
- Empty Python package structure under `src/regulatory_agent_kit/` with stub `__init__.py` files
- Minimal stubs for `config.py` (basic pydantic-settings), `cli.py` (two placeholder commands), `exceptions.py` (4 exception classes), `api/main.py` (health endpoint only)
- Empty test directories (`tests/unit/`, `tests/integration/`)

**Everything below needs to be implemented.**

---

## Implementation Principles

1. **Bottom-up, dependency-order**: Build foundational layers first (models, config, database) before dependent layers (agents, orchestration, CLI)
2. **Test-driven**: Write unit tests alongside each module; integration tests for database and external service interactions
3. **Incremental milestone validation**: Each phase ends with a runnable checkpoint — a command, a test suite, or a Docker service that proves the layer works
4. **Lite Mode first**: Implement the zero-infrastructure Lite Mode path before the full Temporal/Kafka/Elasticsearch stack — this enables early end-to-end testing

---

## Phase 1: Core Domain Models (`models/`)

> **Goal:** Establish all Pydantic v2 data models that flow through the entire system. Every other layer depends on these.

### Checklist

- [ ] **1.1** Implement `models/events.py` — `RegulatoryEvent` model (event_id, timestamp, regulation_id, change_type, source, payload)
- [ ] **1.2** Implement `models/pipeline.py` — `PipelineInput`, `PipelineConfig`, `PipelineResult`, `PipelineStatus` (run_id, status, phase, repo counts, cost summary — returned by `CompliancePipeline.query_status()`), `RepoInput`, `RepoResult`, `CostEstimate` (estimated_total_cost, per_repo_cost, estimated_total_tokens, model_used, exceeds_threshold — per LLD Section 2.3). Note: `PipelineStatus` and `CostEstimate` are distinct models used by the orchestration layer — implement them as full `BaseModel` subclasses, not just type aliases
- [ ] **1.3** Implement `models/impact_map.py` — `ImpactMap`, `FileImpact`, `RuleMatch`, `ASTRegion`, `ConflictRecord`
- [ ] **1.4** Implement `models/changes.py` — `ChangeSet`, `FileDiff`, `TestResult`, `TestFailure`, `ReportBundle`
- [ ] **1.5** Implement `models/audit.py` — `AuditEntry` (entry_id, run_id, event_type as Literal of 9 types per data-model.md Section 3.3, timestamp, payload as dict, signature), `CheckpointDecision` (checkpoint_type as Literal["impact_review","merge_review"], actor, decision as Literal["approved","rejected","modifications_requested"], rationale, signature, decided_at). Note: `CheckpointDecision` includes `checkpoint_type` even though the LLD Section 2.1 class diagram omits it — the field is required by the Temporal signal handler, API endpoint, and database DTO; the domain model and DB schema should be consistent
- [ ] **1.6** Add `model_validator` for cross-field constraints (e.g., PipelineResult terminal statuses)
- [ ] **1.7** Write unit tests for all models — validation, serialization, edge cases (`tests/unit/test_models.py`)
- [ ] **1.8** Export all models from `models/__init__.py`

**Files created:** `models/events.py`, `models/pipeline.py`, `models/impact_map.py`, `models/changes.py`, `models/audit.py`, `tests/unit/test_models.py`

**Validation:** `pytest tests/unit/test_models.py` passes; `mypy src/regulatory_agent_kit/models/` clean

---

## Phase 2: Configuration & Exceptions (`config.py`, `exceptions.py`)

> **Goal:** Full pydantic-settings configuration covering all services, plus the complete exception hierarchy.

### Checklist

- [ ] **2.1** Expand `config.py` `Settings` class with all fields: database (PostgreSQL URL, pool sizes), Temporal (address, namespace, task queue), Elasticsearch (URL, index name), LiteLLM (URL, master key, default model), MLflow (tracking URI), crypto (Ed25519 key path), pipeline defaults (cost threshold, max retries, checkpoint mode), Lite Mode toggle
- [ ] **2.2** Add nested settings models: `DatabaseSettings`, `TemporalSettings`, `ElasticsearchSettings`, `LLMSettings`, `ObservabilitySettings`
- [ ] **2.3** Implement `rak-config.yaml` file loading (YAML config overlay on env vars, using ruamel.yaml)
- [ ] **2.4** Expand `exceptions.py` with full hierarchy: `RAKError` > `PluginValidationError`, `PluginLoadError`, `ConditionParseError`, `PipelineError`, `CheckpointTimeoutError`, `CheckpointRejectedError`, `AgentError`, `ToolError`, `GitError`, `ASTError`, `TemplateError`, `AuditSigningError`, `EventSourceError`, `DatabaseError`, `CostThresholdExceededError`
- [ ] **2.5** Write unit tests for config loading (env vars, `.env` file, YAML overlay) (`tests/unit/test_config.py`)
- [ ] **2.6** Write unit tests for exception hierarchy (`tests/unit/test_exceptions.py`)

**Validation:** `pytest tests/unit/test_config.py tests/unit/test_exceptions.py` passes

---

## Phase 3: Plugin System (`plugins/`)

> **Goal:** Load, validate, and parse regulation YAML plugins with the Condition DSL. This is the heart of the "regulation-as-configuration" architecture.

### Checklist

- [ ] **3.1** Implement `plugins/schema.py` — Pydantic models for `RegulationPlugin`, `Rule`, `AffectsClause`, `Remediation`, `CrossReference`, `RTS`, `EventTrigger` (per LLD Section 2.2). Enable `model_config = ConfigDict(extra="allow")` for open schema
- [ ] **3.2** Implement `plugins/loader.py` — `PluginLoader` class: `load(path)`, `load_all()`, `validate(path)`, `get_by_id(id)`. Use `ruamel.yaml` for YAML parsing. Cache loaded plugins. Note: `validate()` checks file existence and YAML schema at this phase; template rendering validation is deferred until Phase 6 (TemplateEngine) and wired back via an optional `validate_templates()` pass
- [ ] **3.3** Implement `plugins/condition_dsl.py` — Recursive descent parser for the Condition DSL (per LLD Section 6.1). Tokenizer, `ConditionAST`, `Predicate` types, `parse()`, `can_evaluate_statically()`, `to_llm_prompt()`
- [ ] **3.4** Implement `plugins/conflict_engine.py` — `ConflictEngine.detect()`: finds overlapping AST regions across multiple loaded plugins; `get_precedence()` evaluates cross-reference relationships
- [ ] **3.5** Create `regulations/examples/example.yaml` — a minimal, self-contained example plugin for testing and the getting-started guide
- [ ] **3.6** Write unit tests for schema validation (valid/invalid plugins) (`tests/unit/test_plugin_schema.py`)
- [ ] **3.7** Write unit tests for PluginLoader (load, validate, cache, error handling) (`tests/unit/test_plugin_loader.py`)
- [ ] **3.8** Write unit tests for Condition DSL parser (all operators, precedence, error cases) (`tests/unit/test_condition_dsl.py`)
- [ ] **3.9** Write unit tests for ConflictEngine (overlap detection, precedence) (`tests/unit/test_conflict_engine.py`)

**Validation:** `pytest tests/unit/test_plugin_*.py tests/unit/test_condition_dsl.py tests/unit/test_conflict_engine.py` passes. Note: `rak plugin validate` CLI command is wired in Phase 13.6 — at this phase, validate programmatically via `PluginLoader.validate()` in tests

---

## Phase 4: Utility Layer (`util/`)

> **Goal:** Cryptographic signing, structured logging, and validation utilities shared across all layers.

### Checklist

- [ ] **4.1** Implement `util/crypto.py` — `AuditSigner` class: Ed25519 key generation (`generate_key_pair()`), key loading (`load_key()`), payload canonicalization (`_canonicalize()` via sorted JSON), `sign(payload)`, `verify(payload, signature)`. Use `cryptography` library
- [ ] **4.2** Implement `util/logging.py` — Structured JSON logging setup using stdlib `logging` + `json` formatter. Log level from config. Correlation ID (run_id) propagation via contextvars
- [ ] **4.3** Implement `util/hashing.py` — `compute_cache_key(content, plugin_version, agent_version)` returning SHA-256 hex digest for file analysis cache
- [ ] **4.4** Write unit tests for crypto (key gen, sign, verify, tamper detection) (`tests/unit/test_crypto.py`)
- [ ] **4.5** Write unit tests for logging setup (`tests/unit/test_logging.py`)
- [ ] **4.6** Write unit tests for hashing (`tests/unit/test_hashing.py`)

**Validation:** `pytest tests/unit/test_crypto.py tests/unit/test_logging.py tests/unit/test_hashing.py` passes

---

## Phase 5: Database Layer (`database/`)

> **Goal:** Psycopg 3 connection pool, Alembic migrations for the `rak` schema, and repository classes for all 6 tables.

### Checklist

- [ ] **5.1** Implement `database/pool.py` — `create_pool()` returning `AsyncConnectionPool` from config; `close_pool()` for graceful shutdown
- [ ] **5.2** Implement `database/repositories/base.py` — `BaseRepository` with `_fetch_one()`, `_fetch_all()`, `_execute()` helper methods using parameterized queries
- [ ] **5.3** Implement `database/repositories/pipeline_runs.py` — `PipelineRunRepository`: `create()`, `update_status()`, `update_cost()`, `complete()`, `get()`, `list_by_status()`, `list_by_regulation()`
- [ ] **5.4** Implement `database/repositories/repository_progress.py` — `RepositoryProgressRepository`: `create()`, `update_status()`, `set_pr_url()`, `set_error()`, `get_by_run()`, `get_failed()`, `count_by_status()`
- [ ] **5.5** Implement `database/repositories/audit_entries.py` — `AuditRepository`: `insert()`, `bulk_insert()`, `get_by_run()`, `get_by_type()`, `get_by_date_range()`. INSERT/SELECT only. Note: `export_partition(year, month, output_path)` is defined in the LLD class diagram but implemented as part of `AuditArchiver` in Phase 8.4 — the repository provides the raw query, the archiver handles the S3 upload
- [ ] **5.6** Implement `database/repositories/checkpoint_decisions.py` — `CheckpointDecisionRepository`: `create()`, `get_by_run()`, `get_latest()`
- [ ] **5.7** Implement `database/repositories/conflict_log.py` — `ConflictLogRepository`: `create()`, `resolve()`, `get_by_run()`, `get_unresolved()`
- [ ] **5.8** Implement `database/repositories/file_analysis_cache.py` — `FileAnalysisCacheRepository`: `get()`, `put()`, `delete_expired()`. Cache eviction (`delete_expired()`) will be invoked at pipeline startup and can be triggered via `rak db clean-cache` (wired in Phase 13)
- [ ] **5.9** Create Alembic migration `001_initial_schema.py` — Full DDL from LLD Section 5.1: all 6 tables, constraints, indexes, triggers. Create `rak_admin` and `rak_app` database roles with restricted grants (audit_entries: INSERT/SELECT only for `rak_app`). Create partitioned parent table for `audit_entries` plus initial partitions (current month and next 2 months). Note: ongoing monthly partition creation is an operational task — wired as `rak db create-partitions` in Phase 13.8. Design decision: use a single migration for all 6 tables (data-model.md Section 9.2 suggests a separate `002_add_cache_table.py`, but for v1 a single migration is simpler and avoids ordering complexity)
- [ ] **5.10** Write integration tests using `testcontainers` PostgreSQL (`tests/integration/test_repositories.py`): CRUD operations for all repositories, verify audit_entries append-only behavior, test partition routing
- [ ] **5.11** Write unit tests for pool creation logic (`tests/unit/test_database.py`)

**Validation:** `alembic upgrade head` against a real PostgreSQL; `pytest tests/integration/test_repositories.py -m integration` passes

---

## Phase 6: Template Engine (`templates/`)

> **Goal:** Jinja2 sandboxed template rendering for code generation by the Refactor and TestGenerator agents.

### Checklist

- [ ] **6.1** Implement `templates/engine.py` — `TemplateEngine` class: creates `SandboxedEnvironment`, `render(template_path, context)`, `render_string(template_str, context)`, `validate_template(template_path)`
- [ ] **6.2** Create example Jinja2 templates: `regulations/examples/templates/audit_log.j2`, `regulations/examples/templates/audit_log_test.j2`. These extend the example plugin created in Phase 3.5 — the plugin's `remediation.template` and `test_template` fields should reference these paths
- [ ] **6.3** Wire template validation back into `PluginLoader.validate()` — add an optional `validate_templates()` pass that calls `TemplateEngine.validate_template()` for each rule's `remediation.template` and `test_template`. This resolves the deferred validation noted in Phase 3.2
- [ ] **6.4** Write unit tests for template rendering, sandboxing (no access to dangerous builtins), validation, and PluginLoader template validation integration (`tests/unit/test_templates.py`)

**Validation:** `pytest tests/unit/test_templates.py` passes

---

## Phase 7: Tool Layer (`tools/`)

> **Goal:** Implement the shared tools that agents use: Git operations, AST parsing, test execution, and Elasticsearch search.

### Checklist

- [ ] **7.1** Implement `tools/git_client.py` — `GitClient` class: async subprocess wrapper around `git` CLI. Methods: `clone()`, `create_branch()`, `checkout()`, `add()`, `commit()`, `push()`, `diff()`, `log()`. Token acquisition from config/secrets
- [ ] **7.2** Implement `tools/git_provider.py` — `GitProviderClient` (Protocol), `GitHubClient`, `GitLabClient` (using `httpx.AsyncClient`): `create_pull_request()`, `add_comment()`, `get_pr_status()`. Include `create_git_provider(repo_url: str) -> GitProviderClient` factory function that selects implementation based on repo URL host
- [ ] **7.3** Implement `tools/ast_engine.py` — `ASTEngine` class: `parse()`, `query()`, `find_classes()`, `find_annotations()`, `find_methods()`, `get_node_range()`, `check_implements()`. Uses `tree-sitter` with language detection. Support Java and Python initially
- [ ] **7.4** Implement `tools/test_runner.py` — `TestRunner` class: `execute()` method that runs tests in a Docker container with `--network=none --read-only --memory=512m --cpus=1 --timeout=300s`. Static AST pre-analysis to reject suspicious patterns (imports of os, subprocess, socket)
- [ ] **7.5** Implement `tools/search_client.py` — `SearchClient` class: async Elasticsearch client. `index_regulation()`, `search_rules()`, `search_context()`. Includes `ensure_index()` to create/update **both** the `rak-regulations` index (structured rule data, per data-model.md Section 6.1) and the `rak-regulation-context` index (chunked regulatory document text with `dense_vector` embeddings for RAG, per data-model.md Section 6.2) on startup. Must gracefully degrade (return empty results, log warning) when Elasticsearch is unavailable (Lite Mode)
- [ ] **7.6** Implement `tools/notification.py` — `NotificationClient` (Protocol), `SlackNotifier`, `EmailNotifier`, `WebhookNotifier`. Methods: `send_checkpoint_request()`, `send_pipeline_complete()`, `send_error()`. Factory function `create_notifier(checkpoint_mode)` selects implementation from config. Uses `httpx.AsyncClient` for Slack/webhook, `aiosmtplib` for email
- [ ] **7.7** Write unit tests for GitClient (mock subprocess) (`tests/unit/test_git_client.py`)
- [ ] **7.8** Write unit tests for ASTEngine (parse, query, find) (`tests/unit/test_ast_engine.py`)
- [ ] **7.9** Write unit tests for TestRunner (command building, output parsing) (`tests/unit/test_test_runner.py`)
- [ ] **7.10** Write unit tests for NotificationClient (mock HTTP/SMTP, factory selection) (`tests/unit/test_notification.py`)
- [ ] **7.11** Write integration tests for SearchClient using testcontainers Elasticsearch (`tests/integration/test_search_client.py`). Must cover: `ensure_index()` creates both indexes with correct mappings, `index_regulation()` indexes a plugin, `search_rules()` and `search_context()` return results, graceful degradation when ES is unavailable
- [ ] **7.12** Write integration tests for GitClient with a real temp repo (`tests/integration/test_git_client.py`)

**Files created:** `tools/git_client.py`, `tools/git_provider.py`, `tools/ast_engine.py`, `tools/test_runner.py`, `tools/search_client.py`, `tools/notification.py`

**Validation:** `pytest tests/unit/test_git_client.py tests/unit/test_ast_engine.py tests/unit/test_test_runner.py tests/unit/test_notification.py` passes; integration tests pass with Docker

---

## Phase 8: Observability Layer (`observability/`)

> **Goal:** MLflow tracing setup, OpenTelemetry metrics, and the AuditLogger that ties cryptographic signing to database persistence.

### Checklist

- [ ] **8.1** Implement `observability/setup.py` — `ObservabilitySetup` class: `configure_mlflow()`, `configure_otel()`, `configure_audit_signer()`. Sets up PydanticAI autolog (`mlflow.pydantic_ai.autolog`), LiteLLM success callbacks, OTLP exporter for Prometheus
- [ ] **8.2** Implement `observability/audit_logger.py` — `AuditLogger` class: high-level methods `log_llm_call()`, `log_tool_invocation()`, `log_state_transition()`, `log_human_decision()`, `log_conflict_detected()`. Each creates an `AuditEntry`, signs it with `AuditSigner`, inserts via `AuditRepository`
- [ ] **8.3** Implement `observability/wal.py` — Local write-ahead log for audit-critical traces. Buffers to a local file when MLflow is unavailable; replays on reconnection
- [ ] **8.4** Implement `observability/storage.py` — `AuditArchiver` class: exports monthly audit partitions and compliance reports to object storage (S3/GCS/Azure Blob) using `boto3`/`google-cloud-storage`/`azure-storage-blob`. Methods: `export_partition()`, `upload_report()`, `upload_mlflow_artifact()`. Uses a `StorageBackend` Protocol for provider abstraction. In Lite Mode, writes to local filesystem instead
- [ ] **8.5** Write unit tests for AuditLogger (mock repo/signer) (`tests/unit/test_audit_logger.py`)
- [ ] **8.6** Write unit tests for WAL (write, replay, corruption recovery) (`tests/unit/test_wal.py`)
- [ ] **8.7** Write unit tests for AuditArchiver (mock storage backends) (`tests/unit/test_storage.py`)

**Validation:** `pytest tests/unit/test_audit_logger.py tests/unit/test_wal.py tests/unit/test_storage.py` passes

---

## Phase 9: Event Sources (`event_sources/`)

> **Goal:** Pluggable event sources that produce normalized `RegulatoryEvent` objects and start Temporal workflows.

### Checklist

- [ ] **9.1** Implement `event_sources/base.py` — `EventSource` Protocol with `start()`, `stop()` methods. Note: the LLD Section 2.6 labels this module as `events/` but the project scaffold and CLAUDE.md use `event_sources/` — use `event_sources/` as the canonical name
- [ ] **9.2** Implement `event_sources/file.py` — `FileEventSource`: watches a directory for JSON files, parses into `RegulatoryEvent`, calls `WorkflowStarter.start_pipeline()`. For Lite Mode and testing
- [ ] **9.3** Implement `event_sources/webhook.py` — `WebhookEventSource`: FastAPI endpoint (`POST /events`) that validates incoming events and starts workflows. HMAC signature verification
- [ ] **9.4** Implement `event_sources/kafka.py` — `KafkaEventSource`: Kafka consumer group using `confluent-kafka`. Deserializes messages, routes to `WorkflowStarter`
- [ ] **9.5** Implement `event_sources/sqs.py` — `SQSEventSource`: AWS SQS long-polling using `boto3`
- [ ] **9.6** Implement `event_sources/starter.py` — `WorkflowStarter` class: wraps Temporal client. `start_pipeline()`, `signal_approval()`, `query_status()`, `cancel()`, `list_running()`. Note: depends on `CompliancePipeline` workflow (Phase 11) for the workflow type reference; at this phase, use the workflow class name as a string reference so tests can pass with a mock Temporal client
- [ ] **9.7** Write unit tests for FileEventSource (create temp dir, drop JSON files) (`tests/unit/test_file_event_source.py`)
- [ ] **9.8** Write unit tests for WebhookEventSource (HMAC validation, event parsing) (`tests/unit/test_webhook_event_source.py`)
- [ ] **9.9** Write unit tests for WorkflowStarter (mock Temporal client) (`tests/unit/test_workflow_starter.py`)
- [ ] **9.10** Write unit tests for KafkaEventSource (mock confluent-kafka Consumer, deserialization, error handling) (`tests/unit/test_kafka_event_source.py`)
- [ ] **9.11** Write unit tests for SQSEventSource (mock boto3 SQS client, long-polling, message deletion) (`tests/unit/test_sqs_event_source.py`)

**Validation:** `pytest tests/unit/test_*event_source*.py tests/unit/test_workflow_starter.py` passes

---

## Phase 10: Agent Definitions (`agents/`)

> **Goal:** Define the four PydanticAI agents with their tool bindings, system prompts, and structured output types.

### Checklist

- [ ] **10.1** Implement `agents/analyzer.py` — `AnalyzerAgent`: PydanticAI Agent with `result_type=ImpactMap`, tools: `git_clone`, `ast_parse`, `ast_search`, `es_search` (READ-ONLY). System prompt instructs regulation-agnostic analysis using plugin rules
- [ ] **10.2** Implement `agents/refactor.py` — `RefactorAgent`: PydanticAI Agent with `result_type=ChangeSet`, tools: `git_branch`, `git_commit`, `ast_transform`, `jinja_render` (READ-WRITE)
- [ ] **10.3** Implement `agents/test_generator.py` — `TestGeneratorAgent`: PydanticAI Agent with `result_type=TestResult`, tools: `git_read`, `test_run`, `jinja_render` (SANDBOXED)
- [ ] **10.4** Implement `agents/reporter.py` — `ReporterAgent`: PydanticAI Agent with `result_type=ReportBundle`, tools: `git_pr_create`, `notification_send`, `jinja_render` (EXTERNAL)
- [ ] **10.5** Implement `agents/tools.py` — PydanticAI `@agent.tool` decorated functions that wrap the `tools/` classes (GitClient, ASTEngine, SearchClient, TemplateEngine, TestRunner, GitProviderClient). Tool instances are injected via PydanticAI agent dependencies. Enforce tool isolation: Analyzer gets read-only tools (clone, parse, search); Refactor gets read-write tools (branch, commit, template render); TestGenerator gets sandboxed tools (test run); Reporter gets external tools (PR create, notify)
- [ ] **10.6** Write unit tests for each agent (mock LLM responses via PydanticAI test utilities) (`tests/unit/test_agents.py`)

**Validation:** `pytest tests/unit/test_agents.py` passes

---

## Phase 11: Temporal Orchestration (`orchestration/`)

> **Goal:** Implement the Temporal workflows and activities that drive the compliance pipeline state machine.

### Checklist

- [ ] **11.1** Implement `orchestration/activities.py` — Temporal `@activity.defn` functions: `estimate_cost()`, `analyze_repository()`, `refactor_repository()`, `test_repository()`, `report_results()`. Each wraps the corresponding agent. Note: the LLD defines 5 distinct activity classes (`CostEstimationActivity`, `AnalyzeActivity`, `RefactorActivity`, `TestActivity`, `ReportActivity`). All can live in a single `activities.py` file for Phase 1, but consider splitting into separate files if the module exceeds ~500 lines
- [ ] **11.2** Implement `orchestration/workflows.py` — `CompliancePipeline` (`@workflow.defn`): top-level workflow implementing the state machine (LLD Section 4.1). Signal handlers for `approve_impact_review` and `approve_merge_review`. Query handler for `query_status`. Fan-out/fan-in via child workflows
- [ ] **11.3** Implement `orchestration/workflows.py` — `RepositoryProcessor` (`@workflow.defn`): child workflow for per-repo processing (analyze -> refactor -> test)
- [ ] **11.4** Implement `orchestration/worker.py` — Temporal worker setup: register workflows and activities, configure task queue, OpenTelemetry interceptor, connection to Temporal server
- [ ] **11.5** Implement `database/lite.py` — Lite Mode SQLite adapter: provides the same repository interfaces backed by SQLite via `aiosqlite`. Creates tables on first use (`create_tables()`). No partitioning, no roles, no triggers — simplified schema for single-user evaluation. **Repositories included:** `PipelineRunRepository`, `RepositoryProgressRepository`, `AuditRepository`, `CheckpointDecisionRepository`. **Repositories excluded:** `ConflictLogRepository` (cross-regulation conflicts require full mode with multiple plugins loaded concurrently), `FileAnalysisCacheRepository` (Lite Mode runs sequentially so caching provides minimal benefit; can be added later if needed)
- [ ] **11.6** Implement `orchestration/lite.py` — Lite Mode sequential executor: runs the same pipeline logic without Temporal. File-based events, SQLite database (via `database/lite.py`), sequential repository processing, terminal-based checkpoints. `SearchClient` gracefully degrades to empty results when Elasticsearch is unavailable. Notifications are terminal-only (Rich console output)
- [ ] **11.7** Write unit tests for activities (mock agents, mock repos) (`tests/unit/test_activities.py`)
- [ ] **11.8** Write unit tests for Lite Mode SQLite adapter (`tests/unit/test_lite_db.py`)
- [ ] **11.9** Write unit tests for Lite Mode executor (`tests/unit/test_lite_mode.py`)
- [ ] **11.10** Write integration tests for workflows using Temporal test server (`tests/integration/test_workflows.py`)

**Validation:** `pytest tests/unit/test_activities.py tests/unit/test_lite_db.py tests/unit/test_lite_mode.py` passes; Temporal workflow integration test passes

---

## Phase 12: FastAPI Application (`api/`)

> **Goal:** Complete the REST API with event ingestion, approval endpoints, and pipeline status queries.

### Checklist

- [ ] **12.1** Implement `api/routes/events.py` — `POST /events`: receives `RegulatoryEvent`, validates with Pydantic, starts Temporal workflow, returns 202 with workflow_id
- [ ] **12.2** Implement `api/routes/approvals.py` — `POST /approvals/{run_id}`: receives `CheckpointDecision`, signs it, persists to DB, sends Temporal signal
- [ ] **12.3** Implement `api/routes/runs.py` — `GET /runs/{run_id}`: returns pipeline status combining DB and Temporal state. `GET /runs`: list runs with filters
- [ ] **12.4** Implement `api/middleware.py` — `RakAuthMiddleware` extension point for custom authentication backends. Bearer token validation for dev/Docker mode
- [ ] **12.5** Implement `api/dependencies.py` — FastAPI dependency injection for DB pool, Temporal client, AuditSigner, config
- [ ] **12.6** Update `api/main.py` — Wire all routes, middleware, startup/shutdown lifecycle (pool creation, Temporal connection, MLflow setup)
- [ ] **12.7** Write unit tests for all API endpoints using `httpx.AsyncClient` (`tests/unit/test_api.py`)

**Validation:** `pytest tests/unit/test_api.py` passes; `uvicorn regulatory_agent_kit.api.main:app` starts and responds to health/events/approvals

---

## Phase 13: CLI Completion (`cli.py`)

> **Goal:** Implement all CLI commands from `docs/cli-reference.md`.

### Checklist

- [ ] **13.1** Implement `rak run` command — full implementation: load plugin, validate, start pipeline (Temporal or Lite Mode based on `--lite` flag), display progress with Rich. Support `--config <path>` flag to load all options from `rak-config.yaml` (per local-development.md). CLI flags override config file values
- [ ] **13.2** Implement `rak status` command — query pipeline status from DB + Temporal, display Rich table with per-repo progress
- [ ] **13.3** Implement `rak retry-failures` command — find failed repos, signal Temporal to re-dispatch
- [ ] **13.4** Implement `rak rollback` command — read rollback manifest, close PRs, delete branches, create revert PRs
- [ ] **13.5** Implement `rak resume` command — resume interrupted Lite Mode pipeline
- [ ] **13.6** Implement `rak plugin` subcommands: `init` (scaffold new plugin), `validate` (schema check), `test` (run against test repo), `search` (placeholder for registry)
- [ ] **13.7** Implement `rak cancel` command — cancel a running pipeline by sending a Temporal cancellation signal via `WorkflowStarter.cancel()`. In Lite Mode, set the pipeline status to `cancelled` in SQLite
- [ ] **13.8** Implement `rak db` subcommands: `clean-cache` (invoke `FileAnalysisCacheRepository.delete_expired()`), `create-partitions` (create next N months of `audit_entries` partitions via raw DDL). These are operational management commands referenced in Phase 5.8 and 5.9
- [ ] **13.9** Write unit tests for CLI commands using typer.testing.CliRunner (`tests/unit/test_cli.py`). Must include: `rak run --config` loading from `rak-config.yaml` with CLI flag overrides, `rak cancel`, `rak db` subcommands

**Validation:** `pytest tests/unit/test_cli.py` passes; `rak --help` shows all commands including `cancel` and `db`; `rak run --lite` executes end-to-end; `rak run --config rak-config.yaml` loads YAML config correctly

---

## Phase 14: Docker & Infrastructure

> **Goal:** Working Docker Compose stack with all services healthy.

### Checklist

- [ ] **14.1** Update `docker/Dockerfile.worker` — multi-stage build with `python:3.12-slim`, non-root user `rak`, copy site-packages from builder stage, entrypoint runs Temporal worker
- [ ] **14.2** Update `docker/Dockerfile.api` — multi-stage build, non-root user, entrypoint runs `uvicorn`
- [ ] **14.3** Update `docker/Dockerfile.mlflow` — installs `mlflow`, `psycopg2-binary`, `boto3`; runs `mlflow server`
- [ ] **14.4** Update `docker-compose.yml` — health checks for all stateful services (postgres, elasticsearch, temporal), proper depends_on with conditions, named volumes
- [ ] **14.5** Update `docker/init-db.sql` — create `temporal` and `mlflow` databases (the `rak` database is created by `POSTGRES_DB` env var). Create `rak_admin` and `rak_app` PostgreSQL roles with passwords. Note: `init-db.sql` handles database-level and role-level setup only; schema, tables, constraints, and grants are managed by Alembic (Phase 5.9)
- [ ] **14.5a** Create `docker/litellm_config.yaml` — LiteLLM proxy configuration: model list (Anthropic Claude, OpenAI fallback), master key reference from env var, success callbacks for MLflow, rate limit settings. Mounted into the `litellm` container
- [ ] **14.5b** Create `docker/prometheus.yml` — Prometheus scrape configuration: targets for rak-api (:8000/metrics), rak-worker (:9464/metrics), temporal (:9090/metrics), litellm (:4000/metrics). Scrape interval 15s
- [ ] **14.5c** Create `docker/grafana/` provisioning — datasource configuration (Prometheus at http://prometheus:9090), and pre-built dashboard JSON files for pipeline throughput, LLM cost tracking, and error rates
- [ ] **14.6** Verify full stack: `docker compose up -d` → all services healthy → `rak run` against Docker stack works
- [ ] **14.7** Write smoke test script (`tests/smoke/test_docker_compose.sh`) that starts stack, runs health checks, submits an event, verifies pipeline

**Validation:** `docker compose up -d` all containers healthy; smoke test passes

---

## Phase 15: End-to-End Integration & Quality

> **Goal:** Full system integration tests, coverage enforcement, and quality gates.

### Checklist

- [ ] **15.1** Write end-to-end Lite Mode test: load example plugin, run against a fixture repo, verify impact map, refactored code, test results, audit trail (`tests/integration/test_e2e_lite.py`)
- [ ] **15.2** Write end-to-end Docker Compose test: submit event via API, wait for pipeline completion, verify all outputs (`tests/integration/test_e2e_docker.py`)
- [ ] **15.3** Run `ruff check src/ tests/` — fix all lint issues
- [ ] **15.4** Run `ruff format src/ tests/` — format all code
- [ ] **15.5** Run `mypy src/` — fix all type errors (strict mode)
- [ ] **15.6** Run `pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing` — verify >= 80% coverage
- [ ] **15.7** Update `README.md` with installation, quickstart, and architecture overview
- [ ] **15.8** Create `CONTRIBUTING.md` with development setup and contribution guidelines

**Validation:** All quality checks pass (`make check`); full test suite green; coverage >= 80%

---

## Dependency Graph

```
Phase 1: Models ──────────────────────────────────────┐
Phase 2: Config/Exceptions ───────────────────────────┤
                                                      ├── Phase 5: Database
Phase 3: Plugin System ──────────────┐                │
                                     ├── Phase 7: Tools
Phase 4: Utilities (Crypto/Logging) ─┤                │
                                     │                ├── Phase 8: Observability
Phase 6: Templates ──────────────────┘                │
                                                      ├── Phase 9: Event Sources
                                                      │
Phase 10: Agents ─────────────────────────────────────┤
                                                      │
Phase 11: Orchestration ──────────────────────────────┤
                                                      │
Phase 12: API ────────────────────────────────────────┤
Phase 13: CLI ────────────────────────────────────────┤
                                                      │
Phase 14: Docker ─────────────────────────────────────┤
Phase 15: E2E Integration ───────────────────────────-┘
```

**Parallelizable groups:**
- Phases 1–4 can be developed in parallel (no inter-dependencies)
- Phases 5–9 can be partially parallelized (DB, Tools, Templates are independent; Observability depends on DB+Crypto; Event Sources depend on Models)
- Phases 10–13 are sequential (Agents → Orchestration → API/CLI)
- Phase 14–15 are final integration

---

## Implementation Order Summary

| Order | Phase | Module | Key Deliverable |
|-------|-------|--------|-----------------|
| 1 | Phase 1 | `models/` | All Pydantic v2 domain models |
| 2 | Phase 2 | `config.py`, `exceptions.py` | Full configuration and error hierarchy |
| 3 | Phase 3 | `plugins/` | Plugin loader, schema validation, Condition DSL parser |
| 4 | Phase 4 | `util/` | Ed25519 signing, structured logging, cache hashing |
| 5 | Phase 5 | `database/` | Psycopg 3 pool, Alembic migrations, all 6 repositories |
| 6 | Phase 6 | `templates/` | Jinja2 sandboxed template engine + PluginLoader template validation wiring |
| 7 | Phase 7 | `tools/` | Git client, AST engine, test runner, ES search client (2 indexes), notification clients |
| 8 | Phase 8 | `observability/` | MLflow setup, AuditLogger, WAL, object storage archiver |
| 9 | Phase 9 | `event_sources/` | File, Webhook, Kafka, SQS event sources + WorkflowStarter |
| 10 | Phase 10 | `agents/` | 4 PydanticAI agents with tool bindings |
| 11 | Phase 11 | `orchestration/` | Temporal workflows/activities + Lite Mode executor + SQLite adapter |
| 12 | Phase 12 | `api/` | FastAPI routes: events, approvals, runs |
| 13 | Phase 13 | `cli.py` | All `rak` CLI commands including `cancel` and `db` subcommands |
| 14 | Phase 14 | `docker/` | Working Docker Compose stack + service configs (LiteLLM, Prometheus, Grafana) |
| 15 | Phase 15 | `tests/` | E2E tests, lint, typecheck, coverage enforcement |

---

## Total Checklist Count

| Phase | Items |
|-------|-------|
| Phase 1: Models | 8 |
| Phase 2: Config/Exceptions | 6 |
| Phase 3: Plugin System | 9 |
| Phase 4: Utilities | 6 |
| Phase 5: Database | 11 |
| Phase 6: Templates | 4 |
| Phase 7: Tools | 12 |
| Phase 8: Observability | 7 |
| Phase 9: Event Sources | 11 |
| Phase 10: Agents | 6 |
| Phase 11: Orchestration | 10 |
| Phase 12: API | 7 |
| Phase 13: CLI | 9 |
| Phase 14: Docker | 10 |
| Phase 15: E2E/Quality | 8 |
| **Total** | **124** |

---

## Milestone Checkpoints

| Milestone | After Phase | What You Can Do |
|-----------|------------|-----------------|
| **M1: Data layer complete** | Phase 5 | `alembic upgrade head` creates full schema; all repos have CRUD tests passing |
| **M2: Plugin system works** | Phase 3 | `PluginLoader.validate()` validates a YAML plugin programmatically; Condition DSL parses expressions. CLI wiring (`rak plugin validate`) happens in Phase 13 |
| **M3: Tools work standalone** | Phase 7 | Git clone, AST parse, template render, ES index/search all work independently |
| **M4: Lite Mode E2E** | Phase 13 | `rak run --lite --regulation examples/... --repos ./test-repo --checkpoint-mode terminal` runs a full pipeline end-to-end with zero infrastructure |
| **M5: Docker Compose E2E** | Phase 14 | `docker compose up -d && rak run --regulation ... --repos ...` runs full pipeline with Temporal, PostgreSQL, Elasticsearch, MLflow |
| **M6: Production-ready** | Phase 15 | All tests pass, coverage >= 80%, lint clean, type-safe, Docker images built |

---

## Review Notes (v1.1 — 2026-03-28)

The following cross-cutting notes were identified during a doc-vs-plan review and should be kept in mind during implementation:

1. **LLD naming inconsistency:** The LLD Section 2.6 labels the event source module as `events/`, but the project scaffold and CLAUDE.md use `event_sources/`. The canonical name is `event_sources/`.

2. **`CostEstimate` location:** The model is defined in `models/pipeline.py` (Phase 1.2) and imported by `CostEstimationActivity` in `orchestration/activities.py` (Phase 11.1). It is not duplicated — the activity uses the model.

3. **`AuditSigner` boundary:** `util/crypto.py` (Phase 4.1) implements the `AuditSigner` class. `observability/setup.py` (Phase 8.1) provides `configure_audit_signer()` which loads keys and constructs the signer. Phase 8 depends on Phase 4.

4. **`rak-config.yaml` and plugin YAML both use `ruamel.yaml`:** The YAML parsing dependency is shared between config loading (Phase 2.3) and plugin loading (Phase 3.2). No shared utility is needed — both use `ruamel.yaml` directly.

5. **`PipelineResult.status` vs `pipeline_runs.status`:** `PipelineResult` uses terminal-only statuses (`completed`, `rejected`, `failed`, `cost_rejected`). The database column includes all 7 lifecycle statuses. This is by design — `PipelineResult` is the workflow return type, the DB tracks the full lifecycle.

6. **`cost_rejected` in `valid_completion` CHECK constraint:** The `cost_rejected` status is terminal (requires `completed_at IS NOT NULL`). Verify this is set correctly in the `CostEstimationActivity` when the cost is rejected.
