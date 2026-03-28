# regulatory-agent-kit — Implementation Plan

> **Version:** 1.2
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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-1.1 | All 15+ model classes instantiate with valid data and reject invalid data (wrong types, missing required fields) | `pytest tests/unit/test_models.py` — parametrized tests with valid/invalid fixtures | Yes |
| AC-1.2 | `RegulatoryEvent.change_type` only accepts `"new_requirement"`, `"amendment"`, `"withdrawal"` | Unit test with `pytest.raises(ValidationError)` for invalid literals | Yes |
| AC-1.3 | `PipelineResult` model validator enforces: terminal statuses (`completed`, `failed`, `rejected`, `cost_rejected`) require `report` or `actual_cost`; non-terminal statuses are rejected | Unit test for `model_validator` with all status combinations | Yes |
| AC-1.4 | `AuditEntry.event_type` only accepts the 9 defined types from data-model.md Section 3.3 | Unit test with all 9 valid types + 1 invalid | Yes |
| AC-1.5 | `CheckpointDecision.decision` only accepts `"approved"`, `"rejected"`, `"modifications_requested"` | Unit test with `pytest.raises(ValidationError)` | Yes |
| AC-1.6 | All models round-trip through `model_dump()` → `model_validate()` without data loss | Unit test: `assert Model.model_validate(instance.model_dump()) == instance` for each model | Yes |
| AC-1.7 | All models serialize to JSON via `model_dump_json()` and deserialize back | Unit test for JSON round-trip | Yes |
| AC-1.8 | `models/__init__.py` exports all public model classes (importable as `from regulatory_agent_kit.models import X`) | Unit test: `import regulatory_agent_kit.models; assert hasattr(...)` for each class | Yes |
| AC-1.9 | `mypy src/regulatory_agent_kit/models/` passes with zero errors in strict mode | `mypy --strict src/regulatory_agent_kit/models/` exit code 0 | Yes |
| AC-1.10 | No use of deprecated Pydantic v1 API (`@validator`, `.dict()`, `.json()`) | `ruff check` with TCH rules + grep for deprecated patterns | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-2.1 | `Settings` loads all fields from environment variables with correct types and defaults | `pytest tests/unit/test_config.py` — set env vars via `monkeypatch`, assert field values | Yes |
| AC-2.2 | `Settings` loads from a `.env` file when present | Unit test: write temp `.env` file, verify fields populated | Yes |
| AC-2.3 | `rak-config.yaml` overlay overrides env var defaults; env vars still override YAML values | Unit test: set YAML value + env var for same field, verify env var wins | Yes |
| AC-2.4 | Nested settings models (`DatabaseSettings`, `TemporalSettings`, etc.) validate their own field types independently | Unit test: construct each nested model with invalid data, assert `ValidationError` | Yes |
| AC-2.5 | `Settings.lite_mode` toggle defaults to `False` and disables Temporal/ES/PostgreSQL fields when `True` | Unit test: `lite_mode=True` doesn't require `database_url` or `temporal_address` | Yes |
| AC-2.6 | All 15 exception classes exist and inherit from `RAKError` | `pytest tests/unit/test_exceptions.py` — `assert issubclass(XError, RAKError)` for each | Yes |
| AC-2.7 | Each exception class can be raised and caught by its parent type | Unit test: `with pytest.raises(RAKError): raise PluginValidationError(...)` | Yes |
| AC-2.8 | `mypy src/regulatory_agent_kit/config.py src/regulatory_agent_kit/exceptions.py` passes | mypy exit code 0 | Yes |
| AC-2.9 | No manual `os.getenv()` calls — all config uses pydantic-settings | `grep -r "os.getenv\|os.environ" src/regulatory_agent_kit/config.py` returns 0 matches | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-3.1 | `RegulationPlugin` model validates all required fields (id, name, version, effective_date, jurisdiction, authority, source_url, disclaimer) and rejects missing ones | `pytest tests/unit/test_plugin_schema.py` — valid + invalid plugin fixtures | Yes |
| AC-3.2 | `RegulationPlugin` accepts arbitrary extra fields (`model_config = ConfigDict(extra="allow")`) and preserves them in `model_extra` | Unit test: load plugin with unknown field, assert it appears in `model_extra` | Yes |
| AC-3.3 | `PluginLoader.load()` parses a valid YAML file into a `RegulationPlugin` instance | Unit test with `regulations/examples/example.yaml` | Yes |
| AC-3.4 | `PluginLoader.validate()` returns a list of errors for an invalid plugin (missing disclaimer, invalid severity, bad condition syntax) | Unit test with intentionally broken YAML fixtures | Yes |
| AC-3.5 | `PluginLoader` caches loaded plugins — calling `load()` twice on the same path returns the same object | Unit test: `assert loader.load(path) is loader.load(path)` | Yes |
| AC-3.6 | `PluginLoader.get_by_id()` returns `None` for unknown IDs and the correct plugin for known IDs | Unit test after loading example plugin | Yes |
| AC-3.7 | Condition DSL parser handles all operators: `AND`, `OR`, `NOT`, `implements`, `inherits`, `has_annotation`, `has_decorator`, `has_method`, `has_key`, `matches` | `pytest tests/unit/test_condition_dsl.py` — one test per operator | Yes |
| AC-3.8 | Condition DSL respects operator precedence: `NOT` > `AND` > `OR`; parentheses override | Unit test: `parse("A OR B AND NOT C")` produces correct AST shape | Yes |
| AC-3.9 | Condition DSL raises `ConditionParseError` with line/column for malformed expressions | Unit test with invalid expressions: unclosed parens, unknown operators, empty input | Yes |
| AC-3.10 | `can_evaluate_statically()` returns `True` for all 7 static predicates and `False` for semantic conditions | Unit test for each predicate type | Yes |
| AC-3.11 | `to_llm_prompt()` converts a condition AST into a natural-language prompt string | Unit test: assert output is non-empty string containing predicate terms | Yes |
| AC-3.12 | `ConflictEngine.detect()` identifies overlapping AST regions across two plugins with conflicting rules | Unit test with two mock ImpactMaps containing overlapping `ASTRegion` ranges | Yes |
| AC-3.13 | `ConflictEngine.get_precedence()` respects `takes_precedence` cross-references | Unit test with two plugins where one declares `takes_precedence` over the other | Yes |
| AC-3.14 | `regulations/examples/example.yaml` loads and validates without errors | Unit test: `PluginLoader.validate()` returns empty error list | Yes |
| AC-3.15 | Plugin schema uses `ruamel.yaml` (not PyYAML) for parsing | Code review: verify import; no `import yaml` in plugin code | Manual |

Note: `rak plugin validate` CLI command is wired in Phase 13.6 — at this phase, validate programmatically via `PluginLoader.validate()` in tests

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-4.1 | `AuditSigner.generate_key_pair()` produces valid Ed25519 public/private key bytes | `pytest tests/unit/test_crypto.py` — generate, load, verify round-trip | Yes |
| AC-4.2 | `AuditSigner.sign()` produces a base64-encoded Ed25519 signature that `verify()` accepts | Unit test: sign payload, verify signature returns `True` | Yes |
| AC-4.3 | `AuditSigner.verify()` rejects tampered payloads (modified field, added field, removed field) | Unit test: sign, modify payload, assert `verify()` returns `False` or raises | Yes |
| AC-4.4 | `_canonicalize()` produces deterministic output regardless of dict key ordering | Unit test: `_canonicalize({"b":1,"a":2}) == _canonicalize({"a":2,"b":1})` | Yes |
| AC-4.5 | Structured logging outputs valid JSON with `run_id` correlation ID when set via contextvars | `pytest tests/unit/test_logging.py` — capture log output, parse JSON, assert `run_id` field present | Yes |
| AC-4.6 | Log level is configurable from Settings and defaults to INFO | Unit test: set level to DEBUG, verify debug messages appear; set to WARNING, verify info messages suppressed | Yes |
| AC-4.7 | `compute_cache_key()` returns a 64-character hex SHA-256 digest | `pytest tests/unit/test_hashing.py` — `assert len(result) == 64 and all(c in '0123456789abcdef' for c in result)` | Yes |
| AC-4.8 | `compute_cache_key()` is deterministic: same inputs always produce the same key | Unit test: call twice with identical inputs, assert equal | Yes |
| AC-4.9 | `compute_cache_key()` is sensitive: changing any input (content, plugin_version, agent_version) changes the key | Unit test: vary each input independently, assert all keys differ | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-5.1 | `create_pool()` returns an `AsyncConnectionPool` that can execute a simple query (`SELECT 1`) | `pytest tests/unit/test_database.py` — mock or integration test | Yes |
| AC-5.2 | `close_pool()` gracefully shuts down all connections | Unit test: call `close_pool()`, verify pool is closed | Yes |
| AC-5.3 | All 6 repositories inherit from `BaseRepository` and use parameterized queries (no f-strings or %-formatting in SQL) | `grep -rn "f\".*SELECT\|f\".*INSERT\|%s.*SELECT" src/regulatory_agent_kit/database/` returns 0 matches | Yes |
| AC-5.4 | `PipelineRunRepository` CRUD: `create()` returns UUID, `get()` retrieves by ID, `update_status()` changes status, `complete()` sets `completed_at`, `list_by_status()` filters correctly | `pytest tests/integration/test_repositories.py -m integration` — full CRUD cycle | Yes |
| AC-5.5 | `RepositoryProgressRepository`: `create()` enforces `(run_id, repo_url)` uniqueness; `get_failed()` returns only failed rows; `count_by_status()` returns correct counts | Integration test with multiple repos in different statuses | Yes |
| AC-5.6 | `AuditRepository` is append-only: `insert()` and `bulk_insert()` succeed; no `update()` or `delete()` methods exist on the class | Integration test: verify insert works; code review: no update/delete methods | Yes (partial) |
| AC-5.7 | `AuditRepository` queries work across partitions: insert into current month partition, query by `run_id` returns results | Integration test with testcontainers PostgreSQL after running migration | Yes |
| AC-5.8 | `CheckpointDecisionRepository.get_latest()` returns the most recent decision per `(run_id, checkpoint_type)` when multiple exist | Integration test: insert 2 decisions for same checkpoint, verify latest returned | Yes |
| AC-5.9 | `ConflictLogRepository.resolve()` sets `resolution` and `human_decision_id`; `get_unresolved()` excludes resolved entries | Integration test with resolve/query cycle | Yes |
| AC-5.10 | `FileAnalysisCacheRepository.delete_expired()` removes only entries where `expires_at < now()` | Integration test: insert expired + non-expired entries, delete, verify counts | Yes |
| AC-5.11 | `alembic upgrade head` creates all 6 tables with correct constraints, indexes, triggers, roles, and grants | Integration test: run migration against testcontainers PostgreSQL, introspect `information_schema` for table/column existence | Yes |
| AC-5.12 | `audit_entries` table is partitioned by month with at least 2 initial partitions created | Integration test: query `pg_catalog.pg_partitioned_table` and `pg_class` for partition children | Yes |
| AC-5.13 | `rak_app` role has INSERT/SELECT only on `audit_entries` (no UPDATE/DELETE) | Integration test: connect as `rak_app`, attempt `UPDATE` and `DELETE`, assert they fail with permission error | Yes |
| AC-5.14 | `repository_progress.updated_at` trigger fires on UPDATE (auto-sets to `now()`) | Integration test: update a row, verify `updated_at` changed | Yes |

---

## Phase 6: Template Engine (`templates/`)

> **Goal:** Jinja2 sandboxed template rendering for code generation by the Refactor and TestGenerator agents.

### Checklist

- [ ] **6.1** Implement `templates/engine.py` — `TemplateEngine` class: creates `SandboxedEnvironment`, `render(template_path, context)`, `render_string(template_str, context)`, `validate_template(template_path)`
- [ ] **6.2** Create example Jinja2 templates: `regulations/examples/templates/audit_log.j2`, `regulations/examples/templates/audit_log_test.j2`. These extend the example plugin created in Phase 3.5 — the plugin's `remediation.template` and `test_template` fields should reference these paths
- [ ] **6.3** Wire template validation back into `PluginLoader.validate()` — add an optional `validate_templates()` pass that calls `TemplateEngine.validate_template()` for each rule's `remediation.template` and `test_template`. This resolves the deferred validation noted in Phase 3.2
- [ ] **6.4** Write unit tests for template rendering, sandboxing (no access to dangerous builtins), validation, and PluginLoader template validation integration (`tests/unit/test_templates.py`)

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-6.1 | `TemplateEngine.render()` renders a Jinja2 template with context variables and returns the output string | `pytest tests/unit/test_templates.py` — render example template with known context, assert output | Yes |
| AC-6.2 | `TemplateEngine` uses `SandboxedEnvironment` — accessing dangerous builtins (`os`, `subprocess`, `__import__`) raises `SecurityError` | Unit test: attempt `{{ ''.__class__.__mro__ }}` and similar, assert exception | Yes |
| AC-6.3 | `render_string()` renders inline template strings (not files) | Unit test: `render_string("Hello {{ name }}", {"name": "World"}) == "Hello World"` | Yes |
| AC-6.4 | `validate_template()` returns empty list for valid templates and error descriptions for invalid ones (syntax errors, undefined variables) | Unit test with valid and broken template files | Yes |
| AC-6.5 | Example templates (`audit_log.j2`, `audit_log_test.j2`) render without errors against a synthetic context | Unit test: render each example template with a fixture context dict | Yes |
| AC-6.6 | `PluginLoader.validate()` now validates templates when `TemplateEngine` is available (Phase 6.3 wiring) | Unit test: create plugin referencing a broken template, verify `validate()` reports template error | Yes |
| AC-6.7 | Template rendering preserves indentation and does not introduce trailing whitespace | Unit test: render template, check output against expected string with exact whitespace | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-7.1 | `GitClient.clone()` clones a repository to a specified path; `create_branch()`, `checkout()`, `add()`, `commit()`, `push()`, `diff()`, `log()` all execute without error on a temp repo | `pytest tests/integration/test_git_client.py -m integration` — real temp repo lifecycle | Yes |
| AC-7.2 | `GitClient` uses async subprocess — all methods are `async def` and do not block the event loop | Code review + unit test: mock `asyncio.create_subprocess_exec`, verify awaited | Yes |
| AC-7.3 | `create_git_provider()` factory returns `GitHubClient` for `github.com` URLs and `GitLabClient` for `gitlab.com` URLs | `pytest tests/unit/test_git_client.py` — parametrized factory test | Yes |
| AC-7.4 | `ASTEngine.parse()` produces a tree-sitter `Tree` for both Python and Java source files | `pytest tests/unit/test_ast_engine.py` — parse sample .py and .java content | Yes |
| AC-7.5 | `ASTEngine.find_classes()`, `find_annotations()`, `find_methods()`, `check_implements()` return correct results for known source code | Unit test with fixture source files containing known classes/annotations/methods | Yes |
| AC-7.6 | `ASTEngine._detect_language()` correctly identifies Python (`.py`) and Java (`.java`) from file extensions | Unit test: parametrized with various extensions | Yes |
| AC-7.7 | `TestRunner.execute()` builds a Docker command with `--network=none --read-only --memory=512m --cpus=1` flags | `pytest tests/unit/test_test_runner.py` — mock Docker, inspect command args | Yes |
| AC-7.8 | `TestRunner` static AST pre-analysis rejects test files that import `os`, `subprocess`, or `socket` | Unit test: create test file with `import os`, assert rejection | Yes |
| AC-7.9 | `SearchClient.ensure_index()` creates both `rak-regulations` and `rak-regulation-context` indexes with correct mappings | `pytest tests/integration/test_search_client.py -m integration` — testcontainers ES, inspect index mappings | Yes |
| AC-7.10 | `SearchClient` gracefully degrades when Elasticsearch is unavailable: `search_rules()` and `search_context()` return empty lists, log a warning | Unit test: mock ES client to raise `ConnectionError`, verify empty result + warning log | Yes |
| AC-7.11 | `create_notifier()` factory returns `SlackNotifier` for `checkpoint_mode="slack"`, `EmailNotifier` for `"email"`, `WebhookNotifier` for `"webhook"` | `pytest tests/unit/test_notification.py` — parametrized factory test | Yes |
| AC-7.12 | All notification methods (`send_checkpoint_request`, `send_pipeline_complete`, `send_error`) are callable and accept the expected arguments | Unit test with mock httpx/smtp clients | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-8.1 | `AuditLogger.log_llm_call()` creates an `AuditEntry` with `event_type="llm_call"`, signs it, and inserts via `AuditRepository` | `pytest tests/unit/test_audit_logger.py` — mock repo and signer, verify `insert()` called with signed entry | Yes |
| AC-8.2 | All 5 `AuditLogger` methods (`log_llm_call`, `log_tool_invocation`, `log_state_transition`, `log_human_decision`, `log_conflict_detected`) produce entries with correct `event_type` values | Unit test: call each method, assert `event_type` in the inserted entry | Yes |
| AC-8.3 | Every audit entry produced by `AuditLogger` has a non-empty `signature` field | Unit test: mock signer to return known signature, verify it appears in the entry | Yes |
| AC-8.4 | WAL buffers entries to a local file when the primary store is unavailable | `pytest tests/unit/test_wal.py` — simulate repo failure, verify entries written to WAL file | Yes |
| AC-8.5 | WAL replays buffered entries on reconnection without duplicates | Unit test: write N entries to WAL, replay, verify all N inserted and WAL file is emptied/rotated | Yes |
| AC-8.6 | WAL handles corruption gracefully (truncated file, invalid JSON) — skips corrupt entries, logs warning, continues | Unit test: write corrupt data to WAL file, replay, verify partial recovery + warning logged | Yes |
| AC-8.7 | `AuditArchiver.export_partition()` exports audit entries for a given year/month | `pytest tests/unit/test_storage.py` — mock storage backend, verify upload called with correct path | Yes |
| AC-8.8 | `AuditArchiver` in Lite Mode writes to local filesystem instead of S3/GCS | Unit test: configure Lite Mode, call `export_partition()`, verify local file created | Yes |
| AC-8.9 | `StorageBackend` Protocol is implemented by at least one concrete backend (S3 or local filesystem) | Unit test: instantiate backend, call upload method | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-9.1 | `EventSource` Protocol defines `start()` and `stop()` methods; all 4 implementations satisfy the protocol | Unit test: `assert isinstance(source, EventSource)` for each | Yes |
| AC-9.2 | `FileEventSource` detects a new JSON file in the watched directory and produces a `RegulatoryEvent` | `pytest tests/unit/test_file_event_source.py` — create temp dir, drop JSON file, verify event produced | Yes |
| AC-9.3 | `FileEventSource` ignores non-JSON files and malformed JSON (logs warning, does not crash) | Unit test: drop `.txt` file and invalid JSON file, verify no event produced + warning logged | Yes |
| AC-9.4 | `WebhookEventSource` validates HMAC signatures and rejects requests with invalid/missing signatures | `pytest tests/unit/test_webhook_event_source.py` — send request with correct and incorrect HMAC | Yes |
| AC-9.5 | `WebhookEventSource` parses valid JSON body into `RegulatoryEvent` and calls `WorkflowStarter.start_pipeline()` | Unit test: mock WorkflowStarter, send valid webhook, verify `start_pipeline()` called | Yes |
| AC-9.6 | `KafkaEventSource` deserializes Kafka messages into `RegulatoryEvent` objects | `pytest tests/unit/test_kafka_event_source.py` — mock Consumer, verify deserialization | Yes |
| AC-9.7 | `KafkaEventSource` handles deserialization errors gracefully (logs error, continues consuming) | Unit test: mock Consumer returning corrupt message, verify no crash + error logged | Yes |
| AC-9.8 | `SQSEventSource` polls SQS and deletes messages after successful processing | `pytest tests/unit/test_sqs_event_source.py` — mock boto3, verify `delete_message()` called on success | Yes |
| AC-9.9 | `WorkflowStarter.start_pipeline()` starts a Temporal workflow with a deterministic workflow ID | `pytest tests/unit/test_workflow_starter.py` — mock Temporal client, verify `start_workflow()` called with expected ID | Yes |
| AC-9.10 | `WorkflowStarter.signal_approval()` sends a Temporal signal to a running workflow | Unit test: mock client, verify `signal()` called with correct signal name and payload | Yes |
| AC-9.11 | `WorkflowStarter.cancel()` sends a cancellation request to a running workflow | Unit test: mock client, verify `cancel()` called | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-10.1 | `AnalyzerAgent` has `result_type=ImpactMap` and only read-only tools bound (clone, parse, search — no write tools) | `pytest tests/unit/test_agents.py` — inspect agent tool list, assert no write tools present | Yes |
| AC-10.2 | `RefactorAgent` has `result_type=ChangeSet` and has read-write tools (branch, commit, template render) | Unit test: inspect agent tool list | Yes |
| AC-10.3 | `TestGeneratorAgent` has `result_type=TestResult` and only sandboxed tools (test run, read, template render) | Unit test: inspect agent tool list | Yes |
| AC-10.4 | `ReporterAgent` has `result_type=ReportBundle` and external tools (PR create, notify, template render) | Unit test: inspect agent tool list | Yes |
| AC-10.5 | Each agent produces a valid Pydantic model as output when given a mock LLM response | Unit test: use PydanticAI test utilities to mock LLM, run agent, assert output type | Yes |
| AC-10.6 | Tool isolation is enforced: `AnalyzerAgent` cannot access `git_commit` or `git_push`; `TestGeneratorAgent` cannot access `git_pr_create` | Unit test: verify tool names in each agent's tool set do not include forbidden tools | Yes |
| AC-10.7 | Agent system prompts are regulation-agnostic (contain no hardcoded regulation names or rule IDs) | Unit test: inspect system prompt strings, assert no known regulation IDs appear | Yes |
| AC-10.8 | All tool functions in `agents/tools.py` are decorated with `@agent.tool` and have type annotations | `mypy src/regulatory_agent_kit/agents/` passes | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-11.1 | All 5 activities (`estimate_cost`, `analyze_repository`, `refactor_repository`, `test_repository`, `report_results`) are decorated with `@activity.defn` | `pytest tests/unit/test_activities.py` — verify activity registration | Yes |
| AC-11.2 | `CompliancePipeline` workflow implements the full state machine from LLD Section 4.1: PENDING → COST_ESTIMATION → ANALYZING → AWAITING_IMPACT_REVIEW → REFACTORING → TESTING → AWAITING_MERGE_REVIEW → REPORTING → COMPLETED | `pytest tests/integration/test_workflows.py -m integration` — Temporal test server end-to-end | Yes |
| AC-11.3 | Human checkpoints are non-bypassable: the workflow durably pauses at AWAITING_IMPACT_REVIEW and AWAITING_MERGE_REVIEW until a signal is received | Integration test: start workflow, verify it stays in awaiting state until signal sent | Yes |
| AC-11.4 | `approve_impact_review` and `approve_merge_review` signal handlers resume the workflow with the provided `CheckpointDecision` | Integration test: send approval signal, verify workflow proceeds to next phase | Yes |
| AC-11.5 | `query_status` query handler returns a valid `PipelineStatus` at any point during execution | Integration test: query during different phases, verify response structure | Yes |
| AC-11.6 | `RepositoryProcessor` child workflow processes a single repo through analyze → refactor → test | Unit test with mock activities | Yes |
| AC-11.7 | Fan-out/fan-in: `CompliancePipeline` spawns N child workflows and waits for all to complete | Integration test: start pipeline with 3 repos, verify all 3 are processed | Yes |
| AC-11.8 | Lite Mode SQLite adapter: `create_tables()` creates all required tables; all 4 repository implementations pass the same CRUD tests as the PostgreSQL versions | `pytest tests/unit/test_lite_db.py` — CRUD cycle for each repository | Yes |
| AC-11.9 | Lite Mode executor runs the full pipeline sequentially without Temporal, using SQLite and terminal checkpoints | `pytest tests/unit/test_lite_mode.py` — mock agents, verify all phases execute in order | Yes |
| AC-11.10 | Lite Mode executor handles `SearchClient` graceful degradation (empty results when ES unavailable) | Unit test: verify Lite Mode proceeds without Elasticsearch, no exceptions | Yes |
| AC-11.11 | Temporal worker (`orchestration/worker.py`) registers all workflows and activities and connects to the Temporal server | Integration test: start worker, verify it polls the task queue | Yes |
| AC-11.12 | Pipeline transitions to FAILED state on unrecoverable activity errors, and records the error in `repository_progress` | Integration test: mock activity to raise, verify FAILED state + error message | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-12.1 | `POST /events` accepts a valid `RegulatoryEvent` JSON body and returns 202 with `workflow_id` | `pytest tests/unit/test_api.py` — httpx.AsyncClient, mock Temporal | Yes |
| AC-12.2 | `POST /events` returns 422 for invalid event body (missing required fields, wrong types) | Unit test: send malformed JSON, assert 422 + Pydantic error details | Yes |
| AC-12.3 | `POST /approvals/{run_id}` accepts a valid `CheckpointDecision`, signs it, persists to DB, sends Temporal signal | Unit test: mock DB + Temporal + signer, verify all three called | Yes |
| AC-12.4 | `POST /approvals/{run_id}` returns 404 for unknown `run_id` | Unit test: mock DB returning None for `get()`, assert 404 | Yes |
| AC-12.5 | `GET /runs/{run_id}` returns pipeline status combining DB status and Temporal phase | Unit test: mock both sources, verify combined response | Yes |
| AC-12.6 | `GET /runs` returns a list of pipeline runs with optional status filter | Unit test: mock `list_by_status()`, verify filter applied | Yes |
| AC-12.7 | `GET /health` returns 200 with service health status (existing endpoint) | Unit test: call health endpoint, assert 200 | Yes |
| AC-12.8 | `RakAuthMiddleware` rejects requests without a valid Bearer token when configured | Unit test: send request without token, assert 401; send with valid token, assert passes through | Yes |
| AC-12.9 | API startup lifecycle creates DB pool, Temporal connection, and MLflow setup; shutdown closes them | Unit test: mock lifespan events, verify startup/shutdown hooks called | Yes |
| AC-12.10 | `uvicorn regulatory_agent_kit.api.main:app` starts without import errors | Smoke test: start uvicorn with `--check` or import `app` object in test | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-13.1 | `rak --help` lists all commands: `run`, `status`, `retry-failures`, `rollback`, `resume`, `cancel`, `plugin`, `db` | `pytest tests/unit/test_cli.py` — `CliRunner.invoke(app, ["--help"])`, assert all command names in output | Yes |
| AC-13.2 | `rak run --lite --regulation <path> --repos <path> --checkpoint-mode terminal` executes end-to-end against a fixture repo | Integration test: run CLI in Lite Mode with example plugin and test repo | Yes |
| AC-13.3 | `rak run --config rak-config.yaml` loads regulation, repos, model, checkpoint_mode from YAML | Unit test: create temp YAML config, invoke `rak run --config`, verify settings loaded | Yes |
| AC-13.4 | CLI flags override `rak-config.yaml` values (e.g., `--checkpoint-mode slack` overrides YAML `checkpoint_mode: terminal`) | Unit test: set YAML value, pass conflicting CLI flag, verify CLI flag wins | Yes |
| AC-13.5 | `rak status --run-id <uuid>` displays a Rich-formatted table with pipeline status and per-repo progress | Unit test: mock DB/Temporal, invoke command, assert output contains expected fields | Yes |
| AC-13.6 | `rak retry-failures --run-id <uuid>` identifies failed repos and triggers re-dispatch | Unit test: mock DB returning failed repos, verify signal sent | Yes |
| AC-13.7 | `rak rollback --run-id <uuid>` reads rollback manifest and performs cleanup actions (close PRs, delete branches) | Unit test: mock manifest and GitProviderClient, verify cleanup actions called | Yes |
| AC-13.8 | `rak rollback --run-id <uuid> --dry-run` previews actions without executing them | Unit test: invoke with `--dry-run`, verify no mutations, output describes planned actions | Yes |
| AC-13.9 | `rak cancel --run-id <uuid>` sends cancellation signal in Temporal mode and sets status in Lite Mode | Unit test: mock WorkflowStarter.cancel(), verify called; mock SQLite, verify status set | Yes |
| AC-13.10 | `rak plugin validate <path>` reports validation errors for invalid plugins with clear error messages | Unit test: invoke with broken plugin YAML, assert non-zero exit code + error in output | Yes |
| AC-13.11 | `rak plugin init --name <name>` creates a scaffold directory with YAML, templates, tests, and README | Unit test: invoke in temp dir, verify directory structure created | Yes |
| AC-13.12 | `rak db clean-cache` invokes `FileAnalysisCacheRepository.delete_expired()` | Unit test: mock repository, verify `delete_expired()` called | Yes |
| AC-13.13 | `rak db create-partitions` creates next N months of `audit_entries` partitions | Unit test: mock DB, verify DDL executed for correct partition names | Yes |
| AC-13.14 | No use of `print()` in CLI code — all output uses `typer.echo()` or Rich console | `grep -rn "^\s*print(" src/regulatory_agent_kit/cli.py` returns 0 matches | Yes |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-14.1 | `docker/Dockerfile.worker` builds successfully with multi-stage build, runs as non-root user `rak` (UID 1000) | `tests/smoke/test_docker_compose.sh` — `docker compose build worker` succeeds; `docker compose exec worker whoami` returns `rak` | Yes |
| AC-14.2 | `docker/Dockerfile.api` builds successfully with multi-stage build, runs as non-root user | Smoke test: `docker compose build api` succeeds | Yes |
| AC-14.3 | `docker/Dockerfile.mlflow` builds and `mlflow server` starts on port 5000 | Smoke test: `curl http://localhost:5000/health` returns 200 | Yes |
| AC-14.4 | All stateful services (postgres, elasticsearch, temporal) have health checks in `docker-compose.yml` | Smoke test: `docker compose ps` shows `healthy` for all stateful services within 120s | Yes |
| AC-14.5 | `docker compose up -d` starts all 10 services without errors | Smoke test: all containers in `running` state | Yes |
| AC-14.6 | PostgreSQL has 3 databases created: `rak` (from POSTGRES_DB), `temporal`, `mlflow` (from init-db.sql) | Smoke test: `psql -c "\l"` lists all 3 databases | Yes |
| AC-14.7 | PostgreSQL has `rak_admin` and `rak_app` roles created by init-db.sql | Smoke test: `psql -c "\du"` shows both roles | Yes |
| AC-14.8 | LiteLLM proxy responds on port 4000 and accepts the configured model list | Smoke test: `curl http://localhost:4000/health` returns 200 | Yes |
| AC-14.9 | Prometheus scrapes configured targets and has metrics available | Smoke test: `curl http://localhost:9090/api/v1/targets` shows targets UP | Yes |
| AC-14.10 | Grafana starts on port 3000 with Prometheus datasource auto-provisioned | Smoke test: `curl http://localhost:3000/api/datasources` returns Prometheus | Yes |
| AC-14.11 | `rak run` from inside the worker container can connect to all services (Temporal, PostgreSQL, ES, LiteLLM) | Smoke test: submit event via API, verify workflow started in Temporal UI | Yes |
| AC-14.12 | Named volumes persist data across `docker compose down` + `docker compose up` (without `-v`) | Smoke test: create data, restart, verify data exists | Yes |
| AC-14.13 | No secrets are baked into Docker images — all secrets injected via `.env` file or environment variables | Dockerfile review: no `ENV *_KEY=` or `COPY .env` in any Dockerfile | Manual |

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

### Acceptance Criteria

| # | Criterion | Validation Method | Automated? |
|---|-----------|-------------------|------------|
| AC-15.1 | Lite Mode E2E test: load example plugin → run against fixture repo → verify impact map produced → verify refactored code compiles → verify tests pass → verify audit trail exists with signed entries | `pytest tests/integration/test_e2e_lite.py -m integration` | Yes |
| AC-15.2 | Docker Compose E2E test: submit event via `POST /events` → wait for pipeline to reach AWAITING_IMPACT_REVIEW → send approval → wait for COMPLETED → verify PRs created (mock Git provider) → verify audit entries in PostgreSQL | `pytest tests/integration/test_e2e_docker.py -m integration` | Yes |
| AC-15.3 | `ruff check src/ tests/` exits with code 0 (no lint violations) | `make check` or CI step | Yes |
| AC-15.4 | `ruff format --check src/ tests/` exits with code 0 (all code formatted) | `make check` or CI step | Yes |
| AC-15.5 | `mypy src/` exits with code 0 in strict mode (no type errors) | `make check` or CI step | Yes |
| AC-15.6 | `pytest tests/ --cov=regulatory_agent_kit --cov-report=term-missing` reports >= 80% line coverage | CI step with `--cov-fail-under=80` | Yes |
| AC-15.7 | No test takes longer than 30 seconds (global timeout enforced) | `pytest --timeout=30` — all tests pass within limit | Yes |
| AC-15.8 | All integration tests are marked with `@pytest.mark.integration` and can be skipped independently | `pytest tests/ -m "not integration"` runs only unit tests successfully | Yes |
| AC-15.9 | `README.md` contains: installation instructions, quickstart (Lite Mode), architecture diagram link, and link to `CONTRIBUTING.md` | Manual review | Manual |
| AC-15.10 | `CONTRIBUTING.md` contains: development setup (uv sync, Docker), coding standards reference, testing instructions, PR process | Manual review | Manual |
| AC-15.11 | `make check` (or `just check`) runs all quality gates (lint + format + typecheck + tests with coverage) in a single command | Invoke `make check`, verify all 4 steps execute | Yes |

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
