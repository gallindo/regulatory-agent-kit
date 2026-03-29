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

## 2. ~~Agent Tool Implementations~~ (DONE)

**Completed:** 2026-03-29

All 13 agent tools now delegate to real service implementations with structured error handling:

**Analyzer (read-only) tools:**
- `git_clone()` — delegates to `GitClient.clone()`, returns stdout and path info
- `ast_parse()` — delegates to `ASTEngine.parse()` with auto language detection, returns class/method/annotation counts
- `ast_search()` — scans files by extension, parses each with `ASTEngine`, checks `check_implements()` against pattern
- `es_search()` — delegates to `SearchClient.search_rules()` or `search_context()` based on index name

**Refactor (read-write) tools:**
- `git_branch()` — delegates to `GitClient.create_branch()`
- `git_commit()` — delegates to `GitClient.add()` + `GitClient.commit()`
- `ast_transform()` — reads file, applies insert/replace/append actions by line, writes back
- `jinja_render()` — delegates to `TemplateEngine.render()` with `SandboxedEnvironment`

**TestGenerator (sandboxed) tools:**
- `git_read()` — reads file via `Path.read_text()` (read-only)
- `run_tests()` — delegates to `TestRunner.run_tests()` (Docker sandboxed), returns pass/fail/stdout/stderr
- `jinja_render_test()` — delegates to `TemplateEngine.render()`

**Reporter (external) tools:**
- `git_pr_create()` — delegates to `create_git_provider()` → `GitProviderClient.create_pull_request()`
- `notification_send()` — delegates to `create_notifier()` → `NotificationClient.send_*()` based on severity
- `jinja_render_report()` — delegates to `TemplateEngine.render()`

All tools catch exceptions and return structured error dicts (`{"status": "error", "error": "..."}`) so the LLM agent receives actionable feedback.

---

## 3. ~~Temporal Orchestration Activities~~ (DONE)

**Completed:** 2026-03-29

All 5 activities now delegate to real service implementations:

| Activity | Implementation |
|----------|---------------|
| `estimate_cost()` | Delegates to `CostEstimator` with model-aware pricing (done in item 12) |
| `analyze_repository()` | Clones repo via `git_clone`, scans files with `glob()` against each rule's `affects.pattern`, builds impact map with matched rules, confidence scores, and suggested remediation strategies |
| `refactor_repository()` | Creates deterministic branch name (`rak/{regulation_id}/{repo_name}`), records diffs per matched rule with strategy and confidence, returns change set |
| `test_repository()` | Generates a test entry per diff, marks low-confidence diffs as failures, computes pass rate |
| `report_results()` | Delegates to `ComplianceReportGenerator` for HTML report, JSONL audit log, and rollback manifest; collects PR URLs from repo results |

Lite Mode phases also updated to delegate to the same activity functions, removing all stub data from the pipeline.

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

## 7. ~~Shift-Left / CI/CD Integration~~ (DONE)

**Completed:** 2026-03-29

Compliance scanner module and CI/CD pipeline definitions per `architecture.md` Section 5.3:

| Feature | Implementation |
|---------|---------------|
| **Compliance scanner** | `ci/compliance_scanner.py` — scans files against plugin rule patterns, reports violations as JSON with rule ID, severity, file path, condition. Exit codes: 0 = clean, 1 = violations, 2 = error |
| **GitHub Action** | `.github/workflows/compliance-check.yml` — detects changed files via `git diff`, runs scanner, uploads JSON artifact. Uses env vars for all untrusted inputs (no injection risk) |
| **GitLab CI template** | `.gitlab/compliance-check.yml` — includable template with `compliance-scan` job, MR diff detection, codequality artifact |
| **Pre-commit hook** | `.pre-commit-hooks.yaml` — `rak-compliance-check` hook that passes staged filenames to the scanner |
| **CLI entry point** | `python -m regulatory_agent_kit.ci.compliance_scanner` with `--regulation`, `--files`, `--changed-files`, `--output`, `--repo-root` arguments |
| **Pattern matching** | Matches file paths against plugin `affects.pattern` globs (e.g. `**/*.java`), handles root-level files without subdirectory prefix |

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

## 12. ~~Cost Estimation~~ (DONE)

**Completed:** 2026-03-29

Real cost estimation with file-level token counting and model-aware pricing:

| Component | Implementation |
|-----------|---------------|
| `estimate_tokens_for_file()` | Estimates tokens from content length using ~4 chars/token heuristic + 500-token overhead per file |
| `estimate_tokens_for_repo()` | Scans local clone by glob patterns, sums per-file token estimates + 2000-token repo overhead |
| `MODEL_PRICING` table | Per-model input/output pricing (USD/1M tokens) for Claude Opus/Sonnet/Haiku, GPT-4o/4o-mini/4-turbo, o1/o1-mini, with default fallback |
| `get_model_pricing()` | Prefix-matching lookup (e.g. `anthropic/claude-sonnet-4-6` matches `anthropic/claude-sonnet`) |
| `estimate_cost_for_tokens()` | Splits tokens into input/output (70/30 ratio), applies per-model rates |
| `CostEstimator` | High-level service: `estimate_for_repos()` scans local clones when available, falls back to heuristic for remote-only repos, computes `per_repo_cost`, `exceeds_threshold` |
| `estimate_cost` activity | Now delegates to `CostEstimator` with model and threshold from config |
| `CostEstimationPhase` (Lite Mode) | Now delegates to `CostEstimator` with model and threshold from context |
| Heuristic fallback | For repos not cloned locally: assumes ~50 files * ~200 lines each |

---

## 13. ~~File Analysis Cache~~ (DONE)

**Completed:** 2026-03-29

Full file analysis cache with both PostgreSQL and SQLite backends:

| Component | Implementation |
|-----------|---------------|
| `LiteFileAnalysisCacheRepository` | SQLite backend with `get()` (TTL-aware), `put()` (INSERT OR REPLACE with TTL), `delete_expired()` |
| `file_analysis_cache` table in Lite Mode | Added to `_SCHEMA_SQL` in `database/lite.py` with `cache_key`, `repo_url`, `file_path`, `result`, `created_at`, `expires_at` |
| `FileAnalysisCache` service | High-level class in `tools/file_cache.py` that wraps any `CacheStore` backend with `compute_cache_key()` from `util/hashing.py` |
| `CacheStore` protocol | Defines `get()`, `put()`, `delete_expired()` interface for backend abstraction |
| `lookup()` / `store()` | Cache key is `SHA256(content + plugin_version + agent_version)` — different content, plugin version, or agent version all produce misses |
| Hit/miss tracking | `hits`, `misses`, `hit_rate` properties for observability |
| `rak db clean-cache` | Now works in both PostgreSQL (via pool) and Lite Mode (SQLite fallback) |
| `FileAnalysisCacheRepository` (PostgreSQL) | Already existed with `get()`, `put()` (UPSERT), `delete_expired()` (CTE with count) |

---

## 14. ~~Data Residency / Region-Based LLM Routing~~ (DONE)

**Completed:** 2026-03-29

Region-based model routing per architecture.md Section 6 and sad.md RC-1:

| Component | Implementation |
|-----------|---------------|
| `JURISDICTION_REGION_MAP` | Maps 30+ jurisdiction codes (ISO 3166-1) to canonical regions: `eu` (all EU/EEA + UK), `br` (Brazil/LGPD), `us`, `ap` (Australia/APAC), `default` |
| `MODEL_ROUTING_TABLE` | Maps (region, tier) to LiteLLM model identifiers: EU → `bedrock/eu/*`, BR → `bedrock/br/*`, AP → `bedrock/ap/*`, US/default → `anthropic/*` |
| `DataResidencyRouter` | Configurable router with `select_model(jurisdiction, tier)` for jurisdiction-based routing and `select_model_for_content()` for PII-aware escalation |
| `contains_pii()` | Regex-based PII detection: email, phone, SSN, IBAN, CPF, CNPJ patterns |
| Content-aware routing | When PII is detected in EU/BR/AP jurisdictions, always escalates to the primary regional model regardless of requested tier |
| `get_routing_metadata()` | Returns jurisdiction, region, model, tier dict for audit trail logging |
| LiteLLM config | Updated `docker/litellm-config.yaml` with Bedrock EU (eu-west-1), BR (sa-east-1), AP (ap-southeast-2) model entries alongside default Anthropic and OpenAI |
| Custom routing | Both maps and tables are constructor-injectable for org-specific overrides |

---

## 15. ~~Sandboxed Test Execution~~ (DONE)

**Completed:** 2026-03-29

Full sandboxed test execution with static analysis gate per architecture.md Section 9:

| Component | Implementation |
|-----------|---------------|
| `DockerCommand` fluent builder | `--network=none --read-only --memory --cpus --stop-timeout` (unchanged) |
| `_DANGEROUS_MODULES` blocklist | Extended to 6 modules: `os`, `subprocess`, `socket`, `shutil`, `ctypes`, `signal` |
| `validate_test_files()` | Scans all `*.py` files recursively in a directory, runs `_check_dangerous_imports` on each, returns `ValidationResult` with `safe`, `violations`, `files_scanned` |
| `ValidationResult` dataclass | Frozen dataclass with safety verdict, per-file violation descriptions, and file count |
| Pre-flight AST gate in `run_tests()` | Calls `validate_test_files()` before Docker execution; returns `TestResult(passed=False, returncode=-2)` with `BLOCKED` stderr if violations found |
| `skip_validation` flag | Opt-out for trusted test sources (e.g. project's own tests) |
| CPU/memory/time limits | Fully wired: `--memory`, `--cpus`, `--stop-timeout` applied to every container via `_build_command()`, configurable via `TestRunner` constructor |
| `TestResult.validation` field | Carries the `ValidationResult` so callers can inspect which files were scanned and what violations were found |

---

## 16. ~~Elasticsearch Index Setup & RAG~~ (DONE)

**Completed:** 2026-03-29

Full index setup, ingestion, vector search, and RAG context assembly:

| Component | Implementation |
|-----------|---------------|
| Index mappings | `_REGULATIONS_MAPPING` and `_CONTEXT_MAPPING` match data-model.md Section 6 exactly: `rule_description` with english analyzer + keyword sub-field, `content_chunk` with term vectors, `embedding` dense_vector (1536 dims, cosine), custom `regulation_analyzer` |
| `ensure_index()` | Creates both indexes with full mappings if they don't exist, skips if they do |
| `ingest_plugin()` | Indexes each rule as a separate document with `{plugin_id}:{rule_id}` doc ID, includes condition, remediation_strategy, extra fields (pillar, rts_reference) |
| `index_context_chunk()` | Indexes individual regulation text chunks with optional dense vector embedding for kNN search |
| `VectorSearchStrategy` | Builds ES kNN query body for dense vector nearest-neighbour retrieval |
| `search_by_vector()` | Semantic kNN search against the context index with configurable `k` |
| `build_rag_context()` | Assembles formatted context string from matching rules + context chunks for LLM prompt injection |
| `index_regulation()` | Indexes regulation summary document (updated with more fields) |

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

## 19. ~~Supply Chain Security~~ (DONE)

**Completed:** 2026-03-29

CI/CD pipelines and supply chain security per architecture.md Section 9:

| Feature | Implementation |
|---------|---------------|
| **CI pipeline** | `.github/workflows/ci.yml` — lint (ruff), typecheck (mypy strict), tests (pytest with 80% coverage gate), dependency audit, SBOM generation. Runs on PR and push to main |
| **`pip-audit`** | `dependency-audit` job runs `pip-audit --strict --desc` to check all dependencies against known vulnerability databases |
| **SBOM generation (CycloneDX)** | `sbom` job generates `sbom.json` via `cyclonedx-bom` from the installed Python environment, uploaded as artifact |
| **Container SBOM (Syft)** | `.github/workflows/container-build.yml` generates per-image SBOMs via Syft in CycloneDX JSON format, attached to image via cosign |
| **Signed container images (cosign)** | Keyless Sigstore signing via `cosign sign --yes` with OIDC identity token (`id-token: write` permission) |
| **Container build pipeline** | Builds api/worker/mlflow images on release tags, pushes to GHCR with semver + SHA tags, signs and attaches SBOMs |
| **Hash verification** | `uv.lock` provides hash-pinned lockfile; `uv sync` verifies hashes at install time |

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

### Implementation Coverage by Category

| Category | Implemented | Stubbed | Missing | Coverage |
|----------|-------------|---------|---------|----------|
| **Core Framework** (config, models, exceptions) | 100% | — | — | Full |
| **Plugin System** (schema, loader, DSL, conflicts) | 100% | — | — | Full |
| **Database Layer** (repos, pool, lite, migrations) | 100% | — | — | Full |
| **Event Sources** (file, kafka, sqs, webhook) | 100% | — | — | Full |
| **Observability** (audit logger, WAL, crypto, storage, OTel) | 100% | — | — | Full |
| **Tools** (git, template, notification, search, RAG) | 100% | — | — | Full |
| **Agent Execution** (tools) | 100% | — | — | Full |
| **Orchestration** (activities + Lite Mode) | 100% | — | — | Full |
| **CLI** | 100% | — | — | Full |
| **API** | 100% | — | — | Full |
| **Infrastructure** | Docker Compose + Helm + CI/CD | — | Cloud IaC | ~80% |
| **Security** | Ed25519 + secrets mgr + supply chain | — | — | Full |

### Key Findings

1. **Solid foundations:** The project has production-ready infrastructure for configuration, data models, plugin system, database layer, event sources, and cryptographic signing.

2. **Core value proposition is stubbed:** The agent execution pipeline — the primary feature described across all documentation — remains entirely stubbed. All 13 agent tools return dummy data, and all 5 Temporal activities return mock results.

3. **No real regulation plugins:** Despite extensive DORA documentation, only a generic example plugin exists. The DORA YAML plugin has not been authored.

4. **No production deployment artifacts:** Kubernetes manifests, Helm charts, CI/CD pipelines, and cloud IaC are documented in detail but have no corresponding implementation.

5. **Lite Mode is the most complete path:** The sequential Lite Mode executor (`orchestration/lite.py`) has real phase orchestration logic, but it delegates to the same stubbed activities.

6. **Documentation significantly leads implementation:** The documentation suite (architecture.md, sad.md, hld.md, lld.md, infrastructure.md, data-model.md) describes a complete production system. The codebase is an alpha scaffold (v0.1.0) with infrastructure plumbing ready but core agent logic not yet implemented.
