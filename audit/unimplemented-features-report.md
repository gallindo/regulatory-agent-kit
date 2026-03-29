# Unimplemented Features Report

> **Date:** 2026-03-28
> **Scope:** All features described in `docs/` verified against the codebase in `src/regulatory_agent_kit/`
> **Project Version:** 0.1.0 (Alpha)

---

## Legend

| Status | Meaning |
|--------|---------|
| **STUB** | Code structure exists but returns mock/dummy data |
| **MISSING** | No code exists at all |
| **PARTIAL** | Some logic exists but incomplete |

---

## 1. ~~CLI Pipeline Commands~~ (DONE)

**Completed:** 2026-03-29

All CLI commands have been implemented with real logic:

| Command | Implementation |
|---------|---------------|
| `rak run` | Lite Mode: executes `LiteModeExecutor` end-to-end, displays run ID, phases, cost. Temporal: connects to server, starts workflow via `WorkflowStarter`, returns workflow ID |
| `rak status --run-id` | Queries Lite Mode SQLite for run info + repo progress, displays Rich tables with cost and per-repo status. Supports `--filter` flag |
| `rak retry-failures --run-id` | Queries SQLite for failed repos, lists them with error messages |
| `rak rollback --run-id` | Loads rollback manifest from filesystem or audit trail, displays planned actions per repo. Supports `--dry-run` |
| `rak resume --run-id` | Queries SQLite for run state, reports current status and terminal state detection |
| `rak cancel --run-id` | Updates run status to `cancelled` in SQLite, handles terminal state detection |
| `rak plugin test <path> --repo` | Loads plugin, globs repo files against rule patterns, reports match counts per rule |
| `rak plugin search <query>` | Searches local `regulations/` directory by ID, name, jurisdiction, authority; displays Rich table |
| `rak db clean-cache` | Calls `FileAnalysisCacheRepository.delete_expired()` via PostgreSQL pool |
| `rak db create-partitions` | Creates monthly range partitions for `rak.audit_entries` via PostgreSQL |

---

## 2. Agent Tool Implementations (STUB)

**Doc references:** `architecture.md` Section 4.3, `sad.md` Section 10, `lld.md` Section 2.4

All 13 agent tools in `agents/tools.py` return dummy dictionaries instead of delegating to real service implementations:

**Analyzer (read-only) tools:**
- `git_clone()` — returns stub dict
- `ast_parse()` — returns stub dict
- `ast_search()` — returns stub dict
- `es_search()` — returns stub dict

**Refactor (read-write) tools:**
- `git_branch()` — returns stub dict
- `git_commit()` — returns stub dict
- `ast_transform()` — returns stub dict
- `jinja_render()` — returns stub dict

**TestGenerator (sandboxed) tools:**
- `git_read()` — returns stub dict
- `run_tests()` — returns stub dict
- `jinja_render_test()` — returns stub dict

**Reporter (external) tools:**
- `git_pr_create()` — returns stub dict
- `notification_send()` — returns stub dict
- `jinja_render_report()` — returns stub dict

---

## 3. Temporal Orchestration Activities (STUB)

**Doc references:** `lld.md` Section 2.3, `sad.md` Section 9, `architecture.md` Section 4

All 5 activity implementations in `orchestration/activities.py` return mock data instead of invoking real agents:

| Activity | Stub Behavior |
|----------|---------------|
| `estimate_cost()` | Returns hardcoded cost estimate using `ESTIMATED_COST_PER_REPO_USD` constant |
| `analyze_repository()` | Returns empty `ImpactMap` with no file impacts |
| `refactor_repository()` | Returns empty `ChangeSet` with no diffs |
| `test_repository()` | Returns mock `TestResult` with 100% pass rate |
| `report_results()` | Returns mock `ReportBundle` with placeholder file paths |

---

## 4. ~~Alembic Database Migrations~~ (DONE)

**Completed:** 2026-03-29

Alembic migrations were already scaffolded under `migrations/` (not `alembic/`, which caused the
original report to miss them). The implementation has been completed with:

- `alembic.ini` — configured with `version_table_schema = rak` and `rak_admin` role for DDL
- `migrations/env.py` — supports `DATABASE_URL` env var override, offline/online modes,
  version table stored in `rak` schema
- `migrations/versions/001_initial_schema.py` — creates all 6 tables with full constraints:
  - `pipeline_runs` (CHECK constraints, valid_completion, UNIQUE temporal_workflow_id)
  - `repository_progress` (FK CASCADE, UNIQUE run_id+repo_url, updated_at trigger)
  - `audit_entries` (partitioned by month, composite PK, 3 initial partitions)
  - `checkpoint_decisions` (FK CASCADE, CHECK constraints, UNIQUE)
  - `conflict_log` (FK CASCADE, resolution_requires_decision constraint)
  - `file_analysis_cache` (CHAR(64) PK, TTL-based expiration)
- All 12 indexes from `data-model.md` Section 4.1 including the expression index `idx_audit_model`
- Role grants: `rak_admin` (full DDL), `rak_app` (DML-only, append-only on audit_entries)
- Downgrade drops the entire `rak` schema via CASCADE

---

## 5. ~~API Routes — Real Backend Integration~~ (DONE)

**Completed:** 2026-03-29

All API routes now integrate with the database and Temporal when available, with
graceful in-memory fallback for tests and Lite Mode:

| Endpoint | Implementation |
|----------|---------------|
| `POST /events` | Creates `pipeline_runs` row via `PipelineRunRepository`, starts Temporal workflow via `WorkflowStarter` when client is available, returns `run_id` alongside `workflow_id` |
| `POST /approvals/{run_id}` | Persists decision to `checkpoint_decisions` via `CheckpointDecisionRepository`, validates run exists in `pipeline_runs`, signals Temporal workflow. Falls back to in-memory for tests |
| `GET /runs/{run_id}` | Queries `pipeline_runs` + `repository_progress.count_by_status()` from PostgreSQL, returns `PipelineStatus` with cost summary and repo counts |
| `GET /runs` | Queries `pipeline_runs` by status from PostgreSQL, supports `status_filter` parameter |

Additional changes:
- `lifespan()` in `main.py` now initialises DB pool, Temporal client, audit signer, and settings on startup with graceful degradation
- `dependencies.py` provides `get_db_pool`, `get_temporal_client`, `get_audit_signer`, `get_settings` via FastAPI `Depends()` injection
- All routes accept injected dependencies and branch on availability (DB present → query DB; DB absent → in-memory fallback)

---

## 6. DORA Regulation Plugin (MISSING)

**Doc references:** `regulatory-agent-kit.md` Section 4.2, `regulations/dora/README.md`

- `regulations/dora/README.md` exists with detailed documentation covering all 5 DORA pillars
- **No actual `dora-ict-risk-2025.yaml` plugin file exists**
- Only 1 example plugin exists (`regulations/examples/example.yaml`)
- The DORA plugin is referenced throughout the docs as the primary use case but has no implementation

---

## 7. Shift-Left / CI/CD Integration (MISSING)

**Doc references:** `architecture.md` Section 5.3

| Feature | Status |
|---------|--------|
| GitHub Action / GitLab CI step that blocks merges on compliance violations | MISSING |
| PR review bot — agent comments on pull requests with compliance impact analysis | MISSING |
| Pre-commit hook — lightweight Analyzer flags violations before code is pushed | MISSING |

---

## 8. ~~Compliance Report Generation~~ (DONE)

**Completed:** 2026-03-29

A full compliance report generator now produces the three artefacts described in
data-model.md Section 7.1:

| Artefact | Path | Content |
|----------|------|---------|
| HTML report | `{run_id}/report.html` | Styled compliance report with pipeline summary, per-repo results (status, impact, tests, branch), checkpoint decisions, cross-regulation conflicts, PR links, cost estimate |
| Audit log | `{run_id}/audit-log.jsonld` | Newline-delimited JSON export of all audit entries with JSON-LD `@context`/`@type` fields |
| Rollback manifest | `{run_id}/rollback-manifest.json` | JSON manifest with per-repo branch, commit SHA, PR URL, PR state, and files changed |

Implementation:
- `ComplianceReportGenerator` class in `templates/report_generator.py` with `generate()` method
- Jinja2 HTML template at `templates/reports/compliance_report.html.j2` using `SandboxedEnvironment`
- `ReportArtefacts` class with `to_report_bundle_dict()` for integration with `ReportBundle` model
- 20 tests covering HTML content, audit log JSONL format, rollback manifest structure, and directory layout

---

## 9. ~~JSON-LD Audit Log Format~~ (DONE)

**Completed:** 2026-03-29

All audit payloads are now enriched with JSON-LD fields matching data-model.md Section 5:

- `_enrich_payload()` prepends `@context` (`https://schema.org`) and `@type` to every
  payload before signing and storage, respecting any caller-provided overrides
- `JSONLD_TYPE_MAP` maps all 9 event types to their documented `@type` values:
  `LLMCall`, `ToolInvocation`, `StateTransition`, `HumanDecision`, `ConflictDetected`,
  `CostEstimation`, `TestExecution`, `MergeRequest`, `Error`
- 4 missing `log_*` methods added: `log_cost_estimation()`, `log_test_execution()`,
  `log_merge_request()`, `log_error()` — now all 9 event types have dedicated methods
- The signer receives the enriched (JSON-LD) payload, so signatures cover the
  `@context` and `@type` fields for tamper detection

---

## 10. ~~Object Storage Integration~~ (DONE)

**Completed:** 2026-03-29

All storage backends and the audit archiver are now fully implemented:

| Component | Implementation |
|-----------|---------------|
| `StorageBackend` protocol | Implemented (unchanged) |
| `LocalStorageBackend` | Implemented (unchanged) |
| `S3StorageBackend` | Implemented — uses boto3 `put_object`/`get_object`, supports bucket + prefix, standard AWS credential chain |
| `GCSStorageBackend` | Implemented — uses `google-cloud-storage` with Application Default Credentials, optional import with `_HAS_GCS` guard |
| `AzureBlobStorageBackend` | Implemented — uses `azure-storage-blob` with connection string auth, optional import with `_HAS_AZURE` guard |
| `create_storage_backend()` | Factory function creates the right backend from a `backend_type` string (`local`, `s3`, `gcs`, `azure`) |
| `AuditArchiver.export_partition()` | Real implementation — serialises entries list to JSONL, falls back to metadata placeholder when no entries provided |
| `AuditArchiver.archive_partition()` | New method — combines export + upload in one call following `data-model.md` Section 7.1 bucket structure (`audit-archives/{year}/{month}/`) |

All three cloud backends follow the optional-import pattern (same as `sqs.py`), raising `ImportError` with install instructions when the SDK is missing.

---

## 11. ~~Rollback Manifests~~ (DONE)

**Completed:** 2026-03-29

Full rollback pipeline from manifest generation through execution:

| Component | Implementation |
|-----------|---------------|
| **Manifest generation** | `ComplianceReportGenerator._write_rollback_manifest()` writes JSON with per-repo `repo_url`, `branch_name`, `commit_sha`, `pr_url`, `pr_state`, `files_changed` (done in item 8) |
| **Manifest loading** | `load_manifest_from_file()` loads from `compliance-reports/{run_id}/rollback-manifest.json` or `/tmp/rak/{run_id}/`. `load_manifest_from_audit_trail()` searches Lite Mode SQLite for `@type: RollbackManifest` or `merge_request` event |
| **Action planning** | `determine_action()` maps PR state to action: `open` → close PR + delete branch, `merged` → create revert PR, `closed` → skip (idempotent), unknown → delete branch |
| **`plan_rollback()`** | Produces a list of typed `RollbackAction` dataclasses from a manifest |
| **`RollbackExecutor`** | Executes actions via `GitProviderClient`: closes open PRs with comment, creates revert PRs for merged changes with descriptive body, deletes orphan branches. Supports `--dry-run` for preview |
| **`rak rollback` CLI** | Now uses `plan_rollback()` + `RollbackExecutor`. Shows Rich table with repo, branch, PR, state, action. Displays per-repo results with success/failure detail |
| **Audit logging** | `format_rollback_summary()` produces JSON-LD `@type: RollbackExecution` payload with per-action results for audit trail |
| **Edge cases** | Already-closed PRs skipped. Missing token reports clear error. Provider errors caught per-repo without aborting others |

---

## 12. Cost Estimation (STUB)

**Doc references:** `architecture.md` Section 4.2, `lld.md` Section 2.3 (`CostEstimationActivity`)

- `estimate_cost()` activity returns hardcoded values using a constant multiplier
- No real token estimation per repository based on file count/size
- No model-aware cost calculation (different rates per LLM provider/model)
- `CostEstimate` model is fully defined but never populated with real data

---

## 13. File Analysis Cache (MISSING)

**Doc references:** `data-model.md` Section 3.6, `architecture.md` Section 10

- `file_analysis_cache` table schema is documented in `data-model.md`
- `util/hashing.py` has `compute_cache_key()` using `SHA256(content + plugin_version + agent_version)`
- **No cache read/write integration exists in the analysis pipeline**
- No cache eviction logic (`rak db clean-cache` is a stub)
- SQLite Lite Mode schema in `database/lite.py` does not include a cache table

---

## 14. Data Residency / Region-Based LLM Routing (MISSING)

**Doc references:** `architecture.md` Section 6, `sad.md` Section 12

- No implementation of region-based model routing via LiteLLM
- No content classification logic for determining data residency requirements
- No GDPR-aware routing (e.g., EU data to EU-region models)
- LiteLLM config in `docker/litellm-config.yaml` defines models but no routing rules

---

## 15. Sandboxed Test Execution (PARTIAL)

**Doc references:** `architecture.md` Section 9, `lld.md` Section 2.3 (`TestActivity`)

| Component | Status |
|-----------|--------|
| `DockerCommand` fluent builder for `--network=none --read-only` | Implemented |
| `_DANGEROUS_MODULES` blocklist for static analysis | Implemented |
| `TestRunner` end-to-end execution | PARTIAL — class exists but not fully integrated |
| Static AST analysis before test execution | MISSING |
| CPU/memory/time limits enforcement | PARTIAL — `DockerCommand` supports it but no orchestration |

---

## 16. Elasticsearch Index Setup & RAG (PARTIAL)

**Doc references:** `architecture.md` Sections 2, 5; `sad.md` Section 8; `data-model.md` Section 6

| Component | Status |
|-----------|--------|
| `SearchClient` with strategy pattern | Implemented |
| `RulesSearchStrategy` and `ContextSearchStrategy` | Implemented |
| Elasticsearch index creation and mapping setup | MISSING |
| Regulation document ingestion pipeline | MISSING |
| RAG integration with Analyzer agent | MISSING |
| Semantic vector search (kNN) configuration | MISSING |

---

## 17. ~~OpenTelemetry Metrics Export~~ (DONE)

**Completed:** 2026-03-29

`OtelSetup` replaced with full TracerProvider + MeterProvider + OTLP export:

| Component | Implementation |
|-----------|---------------|
| `OtelSetup.configure()` | Creates `TracerProvider` with `BatchSpanProcessor` → OTLP gRPC exporter, `MeterProvider` with `PeriodicExportingMetricReader` → OTLP gRPC exporter, `Resource` with `service.name`/`service.version` |
| OTLP export | Both traces and metrics exported via gRPC to configurable endpoint (default `localhost:4317`), 15s metric export interval |
| Pipeline metrics | 11 instruments: `rak.pipeline.runs.total/completed/failed`, `rak.llm.calls.total`, `rak.llm.call.duration` (histogram), `rak.llm.tokens.total`, `rak.llm.cost.total`, `rak.tool.invocations.total`, `rak.tool.invocation.duration` (histogram), `rak.repos.processed.total`, `rak.checkpoint.decisions.total` |
| Recording helpers | `record_pipeline_started/completed/failed()`, `record_llm_call()`, `record_tool_invocation()`, `record_repo_processed()`, `record_checkpoint_decision()` — all no-op safe when unconfigured |
| FastAPI instrumentation | `instrument_fastapi()` applies auto-instrumentation for HTTP request spans via `FastAPIInstrumentor` |
| `ObservabilitySetup` facade | Updated with `otel` accessor, `instrument_fastapi()` delegation |

**Not implemented** (infrastructure, not application code):
- Temporal interceptor for span export — requires Temporal worker integration at deployment time
- Grafana pre-built dashboards — provisioning JSON, not Python code

---

## 18. ~~Kubernetes / Helm Chart~~ (DONE)

**Completed:** 2026-03-29

Full Helm chart at `helm/regulatory-agent-kit/` matching `infrastructure.md` Section 5 and `hld.md` Section 2.2:

| Resource | Template | Namespace | Spec |
|----------|----------|-----------|------|
| `rak-api` | Deployment + Service + ServiceAccount | `rak` | 2 replicas, health probes, env from secrets |
| `rak-worker` | Deployment + ServiceAccount + HPA + PDB | `rak` | 2-10 replicas, CPU-based HPA with scale-up/down policies, PodDisruptionBudget `minAvailable: 1` |
| `litellm-proxy` | Deployment + Service + ServiceAccount | `rak` | 2 replicas, health probes |
| `mlflow-server` | Deployment + Service + ServiceAccount | `rak` | 1 replica, health probes |
| `postgresql` | StatefulSet + Service | `data` | 100Gi PVC, pg_isready probes |
| `elasticsearch` | StatefulSet + Service | `data` | 3 replicas, 50Gi PVC each, cluster health probe |
| `prometheus` | StatefulSet + Service | `monitoring` | 50Gi PVC, readiness probe |
| `grafana` | Deployment + Service | `monitoring` | Configurable admin password |
| Namespaces | `rak`, `temporal`, `data`, `monitoring` | — | Conditionally created |
| Secrets | `rak-secrets`, `db-credentials`, `signing-keys` | `rak` | LLM keys, Git tokens, DB URL, Ed25519 key |
| Ingress | Ingress | `rak` | Configurable class, TLS, host-based routing to API/Temporal UI/MLflow/Grafana |

`values.yaml` has all per-pod resource requests/limits from `hld.md` Section 3.4, all toggleable via `enabled` flags.

**Not included** (use dedicated Helm charts): Temporal server components — deploy via the official `temporalio/helm-charts` into the `temporal` namespace.

---

## 19. Supply Chain Security (MISSING)

**Doc references:** `architecture.md` Section 9, `sad.md` Section 14

| Feature | Status |
|---------|--------|
| SBOM generation (Syft/CycloneDX) | MISSING |
| `pip-audit` in CI pipeline | MISSING |
| Signed container images (Sigstore/cosign) | MISSING |
| `pip install --require-hashes` | MISSING |
| CI/CD pipeline definition (GitHub Actions / GitLab CI) | MISSING |

---

## 20. ~~Secrets Manager Integration~~ (DONE)

**Completed:** 2026-03-29

Pluggable secrets backends matching architecture.md Section 9.2:

| Backend | Implementation |
|---------|---------------|
| `EnvVarSecretsBackend` | Default — reads from `os.environ`, suitable for development/Lite Mode |
| `AWSSecretsManagerBackend` | Uses boto3 `get_secret_value`, standard AWS credential chain, configurable region |
| `GCPSecretManagerBackend` | Uses `google-cloud-secret-manager`, Application Default Credentials, supports full resource names and short names with project_id |
| `VaultSecretsBackend` | Uses `hvac` for HashiCorp Vault KV v2, configurable URL/token/mount_point |
| `create_secrets_backend()` | Factory function creates backend from type string (`env`, `aws`, `gcp`, `vault`) |
| `resolve_secret()` | URI-based routing: `vault://`, `aws-sm://`, `gcp-sm://`, `env://` schemes, with fallback to literal values or pre-configured backend |

All cloud backends follow the optional-import pattern with `_HAS_*` guards and clear install instructions on `ImportError`.

---

## Summary

  ┌─────────────────────────────────────────┬────────────────┬────────────────┬─────────────────────┐
  │                Category                 │  Implemented   │    Stubbed     │       Missing       │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Core Framework (config, models,         │ 100%           │ —              │ —                   │
  │ exceptions)                             │                │                │                     │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Plugin System (schema, loader, DSL,     │ 100%           │ —              │ —                   │
  │ conflicts)                              │                │                │                     │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Database Layer (repos, pool, lite)      │ 100%           │ —              │ Alembic migrations  │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Event Sources (file, kafka, sqs,        │ 100%           │ —              │ —                   │
  │ webhook)                                │                │                │                     │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Observability (audit logger, WAL,       │ 90%            │ OTel           │ S3 storage, JSON-LD │
  │ crypto)                                 │                │                │                     │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Tools (git, template, notification)     │ 80%            │ —              │ Search/RAG          │
  │                                         │                │                │ integration         │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Agent Execution                         │ 20%            │ All 13 tools   │ Real LLM            │
  │                                         │                │                │ integration         │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Orchestration                           │ 40%            │ All 5          │ Pipeline execution  │
  │                                         │                │ activities     │                     │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ CLI                                     │ 25%            │ 6 commands     │ 2 commands          │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ API                                     │ 40%            │ —              │ DB-backed routes    │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Infrastructure                          │ Docker only    │ —              │ K8s, Helm, CI/CD    │
  ├─────────────────────────────────────────┼────────────────┼────────────────┼─────────────────────┤
  │ Security                                │ Ed25519        │ —              │ SBOM, secrets mgr   │
  │                                         │ signing        │                │                     │
  └─────────────────────────────────────────┴────────────────┴────────────────┴─────────────────────┘



### Implementation Coverage by Category

| Category | Implemented | Stubbed | Missing | Coverage |
|----------|-------------|---------|---------|----------|
| **Core Framework** (config, models, exceptions) | 100% | — | — | Full |
| **Plugin System** (schema, loader, DSL, conflicts) | 100% | — | — | Full |
| **Database Layer** (repos, pool, lite, migrations) | 100% | — | — | Full |
| **Event Sources** (file, kafka, sqs, webhook) | 100% | — | — | Full |
| **Observability** (audit logger, WAL, crypto, storage, OTel) | 100% | — | — | Full |
| **Tools** (git, template, notification, provider) | ~80% | — | Search/RAG integration | ~80% |
| **Agent Execution** | ~20% | All 13 tool functions | Real LLM integration | ~20% |
| **Orchestration** | ~40% | All 5 activities | Real pipeline execution | ~40% |
| **CLI** | 100% | — | — | Full |
| **API** | 100% | — | — | Full |
| **Infrastructure** | Docker Compose + Helm chart | — | CI/CD, cloud IaC | ~60% |
| **Security** | Ed25519 signing + secrets mgr | — | SBOM, supply chain | ~40% |

### Key Findings

1. **Solid foundations:** The project has production-ready infrastructure for configuration, data models, plugin system, database layer, event sources, and cryptographic signing.

2. **Core value proposition is stubbed:** The agent execution pipeline — the primary feature described across all documentation — remains entirely stubbed. All 13 agent tools return dummy data, and all 5 Temporal activities return mock results.

3. **No real regulation plugins:** Despite extensive DORA documentation, only a generic example plugin exists. The DORA YAML plugin has not been authored.

4. **No production deployment artifacts:** Kubernetes manifests, Helm charts, CI/CD pipelines, and cloud IaC are documented in detail but have no corresponding implementation.

5. **Lite Mode is the most complete path:** The sequential Lite Mode executor (`orchestration/lite.py`) has real phase orchestration logic, but it delegates to the same stubbed activities.

6. **Documentation significantly leads implementation:** The documentation suite (architecture.md, sad.md, hld.md, lld.md, infrastructure.md, data-model.md) describes a complete production system. The codebase is an alpha scaffold (v0.1.0) with infrastructure plumbing ready but core agent logic not yet implemented.
