# Unimplemented Features Report

> **Date:** 2026-03-29
> **Scope:** All features described in `docs/` verified against the codebase in `src/regulatory_agent_kit/`
> **Project Version:** 0.1.0 (Alpha)
> **Method:** Exhaustive cross-reference of all 20 documentation files against actual source code

---

## Legend

| Status | Meaning |
|--------|---------|
| **STUB** | Code structure exists but returns mock/dummy/placeholder data |
| **MISSING** | No code exists at all |
| **PARTIAL** | Some logic exists but incomplete vs. documentation |

---

## 1. PydanticAI Agents Not Invoked in Pipeline (STUB)

**Doc references:** `architecture.md` §4.3, `sad.md` §10, `lld.md` §2.3

The four PydanticAI agents are **defined** (`agents/analyzer.py`, `agents/refactor.py`, `agents/test_generator.py`, `agents/reporter.py`) with correct system prompts, output types, and tool bindings. However, the Temporal activities and Lite Mode phases **never call them**:

| Activity | What docs say | What code does |
|----------|--------------|----------------|
| `analyze_repository` | Runs `AnalyzerAgent` with LLM to evaluate condition DSL against AST | Clones repo, runs `glob()` pattern matching against plugin rules — no LLM call, no AST condition evaluation |
| `refactor_repository` | Runs `RefactorAgent` with LLM to generate compliant code via AST transforms and Jinja2 templates | Builds diffs with placeholder content: `"# Remediation: {strategy} for {rule_id}"` — no LLM call, no actual code transformation |
| `test_repository` | Runs `TestGeneratorAgent` with LLM to generate and execute tests in Docker sandbox | Generates test name strings and passes/fails based on confidence threshold — no LLM call, no test file generation, no Docker sandbox execution |
| `report_results` | Runs `ReporterAgent` with LLM to create PRs and compliance reports | Delegates to `ComplianceReportGenerator` directly — no LLM call (this one is reasonably functional without LLM) |

**Impact:** The core value proposition of the project — LLM-driven regulatory compliance automation — is not wired end-to-end. The agents exist but are dead code from the pipeline's perspective.

---

## 2. DORA Regulation Plugin (MISSING)

**Doc references:** `regulatory-agent-kit.md` §4.2, `architecture.md` §3, `regulations/dora/README.md`

- `regulations/dora/README.md` exists with detailed documentation covering all 5 DORA pillars, example YAML structure, and 4 planned plugins
- **No actual `dora-ict-risk-2025.yaml` plugin file exists** — no YAML, no Jinja2 templates, no test fixtures
- Only 1 example plugin exists (`regulations/examples/example.yaml`)
- DORA is referenced throughout docs as the primary use case and is in the project name's raison d'être

---

## 3. MLflow PydanticAI Autolog Integration (MISSING)

**Doc references:** `adr/005-llm-observability-platform.md`, `sad.md` §13, `architecture.md` §7

Documentation states:
> Native PydanticAI agent tracing via `mlflow.pydantic_ai.autolog()`

No call to `mlflow.pydantic_ai.autolog()` exists anywhere in the codebase. The observability setup (`observability/setup.py`) configures OpenTelemetry but does not set up MLflow's PydanticAI auto-instrumentation.

---

## 4. MLflow Evaluation Framework (MISSING)

**Doc references:** `adr/005-llm-observability-platform.md`

Documentation describes:
- `mlflow.genai.evaluate()` with 20+ metrics (DeepEval/RAGAS)
- LLM-as-a-judge scorers
- Experiment/A-B prompt comparison

No evaluation framework code exists. No calls to `mlflow.genai.evaluate()`, no scorer definitions, no experiment comparison logic.

---

## 5. Temporal OpenTelemetry Interceptor (MISSING)

**Doc references:** `adr/004-python-stack.md` §L19, `sad.md` §13

Documentation states:
> Temporal OTel interceptor (`temporalio.contrib.opentelemetry`) — auto-traces all workflow/activity operations

No import of `temporalio.contrib.opentelemetry` or OTel interceptor configuration exists in the worker or workflow code.

---

## 6. Grafana Pre-Built Dashboards (MISSING)

**Doc references:** `local-development.md` §3, `architecture.md` §7

Documentation describes:
> Pre-built Grafana dashboards: pipeline throughput, error rates, LLM cost tracking

Only a Prometheus datasource provisioning file exists (`docker/grafana/provisioning/datasources/prometheus.yml`). No dashboard JSON files exist for the documented pipeline throughput, error rate, or LLM cost dashboards.

---

## 7. Email Notification Client (STUB)

**Doc references:** `architecture.md` §2, `lld.md` §2.4

`EmailNotifier` class exists in `tools/notification.py` but is explicitly a stub:
```python
class EmailNotifier:
    """Send notifications via email (stub implementation)."""
```

All three methods (`send_checkpoint_request`, `send_pipeline_complete`, `send_error`) log messages only — no SMTP connection, no SES integration, no actual email sending.

---

## 8. `rak retry-failures` — Re-dispatch Logic (PARTIAL)

**Doc references:** `cli-reference.md`

The CLI command identifies failed repos from SQLite and displays them, but the docstring says:
> "Re-dispatch is not yet available"

No actual re-dispatch to Temporal or Lite Mode executor occurs. The command is informational only.

---

## 9. `rak resume` — WAL Replay Integration (PARTIAL)

**Doc references:** `cli-reference.md`

The command reads SQLite state and detects terminal states, but outputs:
> "Full resume logic requires the WAL replay integration."

The WAL (`observability/wal.py`) has `write()` and `replay()` methods, but the resume command does not call `replay()` or re-enter the Lite Mode executor from the last checkpoint.

---

## 10. Custom Jinja2 Template Filters (MISSING)

**Doc references:** `plugin-template-guide.md` §4

Documentation describes 5 custom Jinja2 filters:
- `basename`, `dirname`, `snake_case`, `camel_case`, `pascal_case`

The `TemplateEngine` in `templates/engine.py` creates a bare `SandboxedEnvironment` without registering any custom filters.

---

## 11. API Authentication — OAuth2/JWT for Production (MISSING)

**Doc references:** `architecture.md` §9.3

Documentation describes three auth tiers:
- Lite Mode: none
- Docker Compose dev: Bearer token ← **implemented** (`RakAuthMiddleware`)
- Kubernetes prod: OAuth2/OIDC via API gateway or FastAPI JWT middleware ← **not implemented**

Only the simple Bearer-token middleware exists. No OAuth2, OIDC, or JWT support is implemented.

---

## 12. `rak cancel` — Temporal Workflow Cancellation (PARTIAL)

**Doc references:** `cli-reference.md`

The `cancel` command only updates SQLite status to `cancelled`. It does not signal the Temporal workflow to cancel (via `WorkflowStarter.cancel()`), which is documented as the primary cancellation mechanism for non-Lite Mode runs.

---

## 13. Cloud Infrastructure-as-Code (MISSING)

**Doc references:** `infrastructure.md` §2–4

Documentation provides detailed deployment architectures for:

| Cloud | Described Services | Implementation |
|-------|--------------------|----------------|
| **AWS** | EKS + RDS + OpenSearch + S3 + MSK + Secrets Manager + SES + ECR | No Terraform/CloudFormation/CDK |
| **GCP** | GKE Autopilot + Cloud SQL + GCS + Secret Manager + Artifact Registry | No Terraform/Pulumi |
| **Azure** | AKS + Azure DB for PostgreSQL + Blob + Key Vault + ACR + Event Hubs | No Terraform/Bicep |

Only the Helm chart and Docker Compose exist. No cloud-specific IaC templates.

---

## 14. PR Review Bot / CI Comment Integration (MISSING)

**Doc references:** `architecture.md` §5.3

Documentation describes:
> PR review bot — Agent comments on pull requests with compliance impact analysis

No code implements automatic PR commenting. The compliance scanner (`ci/compliance_scanner.py`) outputs JSON results but does not post comments to GitHub/GitLab PRs.

---

## 15. Rate Limit Management (MISSING)

**Doc references:** `architecture.md` §6

Documentation describes:
> Rate limit management (token bucket rate limiter)

No token bucket or rate limiter implementation exists in the codebase. This is expected to be handled by LiteLLM's built-in rate limiting, but no configuration for it exists in `docker/litellm-config.yaml` beyond model routing.

---

## 16. Fallback Model Routing (MISSING)

**Doc references:** `architecture.md` §6

Documentation describes:
> Fallback routing (automatic failover to secondary models on outage)

The `DataResidencyRouter` (`tools/data_residency.py`) handles jurisdiction-based routing but has no fallback/failover logic. LiteLLM supports fallbacks via config, but no `fallbacks` key exists in `docker/litellm-config.yaml`.

---

## 17. Plugin Certification Tiers (MISSING)

**Doc references:** `architecture.md` §3.6

Documentation describes three certification tiers:
- `Technically Valid` — automated CI validation
- `Community Reviewed` — 2+ domain expert reviews
- `Official` — core team certified

No certification tier field exists in the plugin schema (`plugins/schema.py`), and no certification workflow or CI validation is implemented.

---

## 18. Audit Partition Auto-Rotation (PARTIAL)

**Doc references:** `data-model.md` §8, `operations/runbook.md` §4.2, `hld.md` §9

Documentation describes automated partition management via `pg_partman` or application-level cron. The `rak db create-partitions` CLI command creates partitions manually, but:
- No `pg_partman` extension setup exists
- No automated monthly partition pre-creation (cron job, init container, or scheduled task)
- No automated export-to-S3-then-drop-partition workflow

---

## 19. Temporal Workflow Cancel Signal in Workflows (PARTIAL)

**Doc references:** `lld.md` §2.3, `architecture.md` §4.2

The `CompliancePipeline` workflow defines signal handlers for `approve_impact_review` and `approve_merge_review`, but no `cancel` signal handler exists. The docs describe graceful cancellation with Temporal's built-in cancellation scope, but the workflow does not handle `CancelledError` or clean up on cancellation.

---

## 20. Condition DSL Static Evaluation at Pipeline Time (MISSING)

**Doc references:** `architecture.md` §3.3, `lld.md` §2.2

The condition DSL parser (`plugins/condition_dsl.py`) is fully implemented with:
- Recursive descent parser, tokenizer, AST
- `StaticEvaluabilityVisitor` — determines if a condition can be evaluated without LLM
- `LLMPromptVisitor` — generates prompts for LLM-dependent conditions

However, the `analyze_repository` activity never calls the DSL evaluator. Conditions are stored as raw strings in the impact map but never actually evaluated against file ASTs during pipeline execution.

---

## 21. Kafka Credential Rotation Without Restart (MISSING)

**Doc references:** `architecture.md` §9.2

Documentation states:
> Kafka credentials: SASL/SCRAM or mTLS; rotatable without restart

The `KafkaEventSource` accepts credentials at construction time but has no hot-reload mechanism for credential rotation.

---

## Summary

### Unimplemented Features by Severity

| Severity | Count | Features |
|----------|-------|----------|
| **Critical** (core value prop) | 2 | Agents not invoked in pipeline (#1), DORA plugin (#2) |
| **High** (documented capabilities) | 6 | MLflow autolog (#3), MLflow evaluation (#4), Condition DSL evaluation (#20), PR review bot (#14), retry-failures re-dispatch (#8), resume WAL replay (#9) |
| **Medium** (production readiness) | 8 | Temporal OTel interceptor (#5), Grafana dashboards (#6), Email notifier (#7), OAuth2/JWT auth (#11), cancel Temporal signal (#12, #19), fallback routing (#16), rate limiting (#15) |
| **Low** (nice-to-have) | 5 | Cloud IaC (#13), custom Jinja2 filters (#10), plugin certification (#17), partition auto-rotation (#18), Kafka credential rotation (#21) |

### Documentation vs. Implementation Gap Analysis

| Category | Documented | Implemented | Gap |
|----------|-----------|-------------|-----|
| **Agent Pipeline** (LLM-driven analysis/refactor/test) | Full end-to-end | Agents defined but not called | **Critical** |
| **Regulation Plugins** | DORA (5 pillars, 4 plugins) | 1 example plugin only | **Critical** |
| **LLM Observability** (MLflow) | Autolog + evaluation + experiments | OTel metrics only | **High** |
| **CLI Commands** | 10 commands fully functional | 8 functional, 2 partial (retry/resume) | **Medium** |
| **API** | 4 endpoints + OAuth2 | 4 endpoints + Bearer only | **Medium** |
| **Infrastructure** | Docker + Helm + 3 cloud IaC | Docker + Helm only | **Low** |
| **Plugin System** | Schema + DSL + conflict engine + certification | Schema + DSL + conflict (no cert, no runtime eval) | **High** |
| **Security** | Ed25519 + secrets + supply chain + sandboxing | All implemented | **Full** |
| **Database** | 6 tables + migrations + repos + partitioning | All implemented (auto-rotation missing) | **Near-full** |
| **Event Sources** | 4 sources (Kafka, SQS, Webhook, File) | All implemented | **Full** |
| **Notifications** | Slack + Email + Webhook | Slack + Webhook real, Email stub | **Near-full** |
| **Observability** | OTel + MLflow + Grafana | OTel real, MLflow partial, Grafana missing dashboards | **Medium** |
