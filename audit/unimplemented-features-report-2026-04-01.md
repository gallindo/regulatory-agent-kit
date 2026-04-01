# Unimplemented Features Report — Third Audit

> **Date:** 2026-04-01
> **Scope:** All features in `docs/` cross-referenced against codebase in `src/regulatory_agent_kit/`
> **Previous audits:** `unimplemented-features-report-2026-03-29.md` (20 gaps — 19 implemented, 1 skipped), `unimplemented-features-report-2026-03-31.md` (3 gaps — all implemented)
> **Method:** Exhaustive read of all doc files (architecture.md, sad.md, hld.md, lld.md, regulatory-agent-kit.md, cli-reference.md, infrastructure.md, data-model.md, local-development.md, getting-started.md, plugin-template-guide.md, glossary.md, all ADRs, all operations guides) cross-referenced against source code, Grafana dashboards, Prometheus config, Helm charts, and Terraform files.

---

## Legend

| Status | Meaning |
|--------|---------|
| **IMPLEMENTED** | Gap identified and fully implemented |
| **ROADMAP** | Documented as an option but explicitly Phase 2 / not yet planned |

---

## Gaps Found and Resolved

### GAP-1: Prometheus Metrics Instrumentation — IMPLEMENTED

**Doc references:** `infrastructure.md` §11.1 (Metric Sources diagram), §11.2 (Key Dashboards)

**Issue:** Grafana dashboards referenced `rak_*` metrics but no `prometheus_client` instrumentation existed in the codebase. No `/metrics` endpoint on the FastAPI app.

**Resolution:**
- Created `src/regulatory_agent_kit/observability/metrics.py` with `MetricsRegistry` dataclass containing all 11 metric families (Counters + Histograms) matching Grafana dashboard queries exactly.
- Added `GET /metrics` endpoint to `src/regulatory_agent_kit/api/main.py` using `prometheus_client.generate_latest()`.
- Instrumented all 17 agent tools in `src/regulatory_agent_kit/agents/tools.py` with `@instrumented_tool` decorator (records `rak_tool_invocations_total` and `rak_tool_invocation_duration`).
- Instrumented orchestration activities in `src/regulatory_agent_kit/orchestration/activities.py` (`record_pipeline_started`, `record_repo_processed`, `record_pipeline_completed`).
- Instrumented approval routes in `src/regulatory_agent_kit/api/routes/approvals.py` (`record_checkpoint_decision`).
- Added `prometheus_client>=0.21.0` dependency to `pyproject.toml`.
- Re-exported all metrics symbols from `src/regulatory_agent_kit/observability/__init__.py`.
- 22 new unit tests in `tests/unit/test_metrics.py`.

---

### GAP-2: Prometheus Alert Rules — IMPLEMENTED

**Doc references:** `infrastructure.md` §11.3 (Alert Rules, lines 1444–1536)

**Issue:** No Prometheus alert rules file, no Alertmanager configuration, and no Alertmanager service in Docker Compose.

**Resolution:**
- Created `docker/prometheus/rules/rak-alerts.yml` with two rule groups matching documentation exactly:
  - **rak-critical:** PipelineStuck, WorkerDown, PostgreSQLDown, TemporalFrontendDown
  - **rak-warning:** HighActivityFailureRate, LLMLatencyHigh, PostgreSQLConnectionsHigh, AuditPartitionNearFull, TaskQueueBacklog, LLMCostSpike
- Created `docker/alertmanager.yml` with routing config: severity=critical → rak-critical, severity=warning → rak-warning, default → rak-default. Includes inhibit rules.
- Updated `docker/prometheus.yml` with `rule_files` and `alerting` sections.
- Added `alertmanager` service to `docker-compose.yml` (port 9093, health check, depends on prometheus).
- Added `docker/prometheus/rules` volume mount to prometheus service.

---

### GAP-3: PgBouncer Deployment Artifacts — IMPLEMENTED

**Doc references:** `hld.md` §4.6 (lines 539–553), `operations/runbook.md` §3.1 (line 166), `adr/003-database-selection.md` (lines 192, 343)

**Issue:** PgBouncer documented as mandatory for >3 workers but no configuration, Docker Compose service, or Helm template existed.

**Resolution:**
- Created `docker/pgbouncer.ini` with transaction pool mode, pool sizes matching `hld.md` §4.6 (max_client_conn=200, default_pool_size=20, min/reserve=5).
- Created `docker/pgbouncer-userlist.txt` with development credentials and hash generation instructions.
- Added profile-gated `pgbouncer` service to `docker-compose.yml` (profiles: ["pgbouncer"], port 6432, depends on postgres healthy).
- Created `helm/regulatory-agent-kit/templates/pgbouncer.yaml` with ConfigMap + Deployment + Service in `data` namespace, gated by `.Values.pgbouncer.enabled`.
- Added `pgbouncer` section to `helm/regulatory-agent-kit/values.yaml` (disabled by default, full pool configuration).

---

## Previously Identified — Still Roadmap

These items from prior audits remain roadmap/future items and are **not gaps**:

| Item | Description | Status |
|------|-------------|--------|
| Plugin Registry backend | Central cloud-hosted registry for community plugins | ROADMAP — local + GitHub search only |
| Serverless deployment | Lambda + EventBridge | ROADMAP — no Lambda functions |
| ECS + MSK deployment | Managed containers + Kafka on AWS | ROADMAP — no ECS task definitions |
| DORA Regulation Plugin | Full five-pillar DORA plugin | SKIPPED — excluded per user instructions |

---

## Verification

- **Full test suite:** 1133 unit tests passing, 0 failures (2 pre-existing integration test failures unrelated to this work)
- **Lint:** All modified files pass `ruff check`
- **All 25 features** from all three audits are implemented (19 from first audit + 3 from second audit + 3 from this audit)
