# Documentation Audit Report

**Project:** regulatory-agent-kit
**Scope:** `docs/` directory — 7 primary documents + 5 ADRs
**Date:** 2026-03-27
**Auditor:** Senior Technical Writer & Systems Architect (AI-assisted)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [CRITICAL — Direct Contradictions](#critical--direct-contradictions)
3. [MISSING — Key Areas Lacking Documentation](#missing--key-areas-lacking-documentation)
4. [REDUNDANT — Suggested Areas for Consolidation](#redundant--suggested-areas-for-consolidation)
5. [SUGGESTIONS — Minor Clarity and Formatting Improvements](#suggestions--minor-clarity-and-formatting-improvements)
6. [Summary Table](#summary-table)
7. [Root Cause Analysis](#root-cause-analysis)

---

## Executive Summary

| Category       | Count | Severity                                         |
|----------------|-------|--------------------------------------------------|
| **CRITICAL**   | 7     | Will cause implementation errors if not resolved  |
| **MISSING**    | 9     | Gaps that will block or confuse implementers      |
| **REDUNDANT**  | 7     | DRY violations creating drift risk                |
| **SUGGESTIONS**| 7     | Polish items                                      |

The critical contradictions (C1-C4) all stem from the same root cause: `architecture.md` and `regulatory-agent-kit.md` were **not updated** after ADR-002 (Temporal + PydanticAI), ADR-004 (Python 3.12+), and ADR-005 (MLflow) were accepted. The HLD, LLD, SAD, data-model, and infrastructure docs were written *after* the ADRs and are internally consistent with each other. Updating the two stale documents would resolve 4 of 7 critical issues and most redundancy concerns.

### Documents Audited

| Document                       | Path                                  | Role                        |
|--------------------------------|---------------------------------------|-----------------------------|
| Product Requirements (PRD)     | `docs/regulatory-agent-kit.md`        | Why — market & product      |
| Architecture                   | `docs/architecture.md`                | What — system design         |
| High-Level Design (HLD)        | `docs/hld.md`                         | How — operational            |
| Low-Level Design (LLD)         | `docs/lld.md`                         | How — in code                |
| Software Architecture (SAD)    | `docs/sad.md`                         | How — architecturally        |
| Data Model                     | `docs/data-model.md`                  | Data layer                   |
| Infrastructure                 | `docs/infrastructure.md`              | Deployment                   |
| ADR-001                        | `docs/adr/001-agent-orchestration-framework.md` | Decision record    |
| ADR-002                        | `docs/adr/002-langgraph-vs-temporal-pydanticai.md` | Decision record |
| ADR-003                        | `docs/adr/003-database-selection.md`  | Decision record              |
| ADR-004                        | `docs/adr/004-python-stack.md`        | Decision record              |
| ADR-005                        | `docs/adr/005-llm-observability-platform.md` | Decision record       |

---

## CRITICAL — Direct Contradictions

### C1. Orchestration Framework: LangGraph vs Temporal + PydanticAI

The most severe contradiction across the documentation suite.

| Document | Claims |
|---|---|
| `regulatory-agent-kit.md` (PRD) | "**LangGraph Multi-Agent Orchestration**", references `langgraph-checkpoint-postgres`, `StateGraph` |
| `architecture.md` | "Stateful **LangGraph StateGraph**", `langgraph-checkpoint-postgres` |
| `adr/001-*.md` | Selects LangGraph — **Status: Superseded by ADR-002** |
| `adr/002-*.md` | **Selects Temporal + PydanticAI**, explicitly replacing LangGraph |
| `hld.md` | Uses **Temporal** throughout (Temporal Server, Temporal Workers, temporalio SDK) |
| `lld.md` | Uses **Temporal** throughout (workflow signals, activities, retry policies) |
| `sad.md` | Uses **Temporal + PydanticAI** throughout; states "Replaces LangChain entirely" |
| `infrastructure.md` | Uses **Temporal** throughout (temporal namespace, temporal-server, temporal-ui pods) |
| `data-model.md` | References `temporal_workflow_id` field, Temporal schema |

**Impact:** `regulatory-agent-kit.md` and `architecture.md` still describe the **superseded** LangGraph architecture. They reference `langgraph-checkpoint-postgres`, `StateGraph`, `interrupt_before`/`interrupt_after`, and `Send` API — none of which exist in the Temporal + PydanticAI stack. An implementer starting from the PRD or architecture doc will build the wrong system.

**Recommendation:** Update `regulatory-agent-kit.md` and `architecture.md` to reflect Temporal + PydanticAI as selected in ADR-002.

---

### C2. Python Version: 3.11+ vs 3.12+

| Document | Python Version |
|---|---|
| `regulatory-agent-kit.md` | **3.11+** |
| `architecture.md` | **3.11+** (Lite Mode section) |
| `hld.md` | **3.12+** |
| `lld.md` | **3.12** (Docker image `python:3.12-slim`) |
| `sad.md` | **3.12+** (mandatory) |
| `infrastructure.md` | **3.12** |
| `adr/004-*.md` | Evaluates 3.11 vs 3.12 vs 3.13; likely selects **3.12** |

**Impact:** Installing on Python 3.11 would fail if the codebase uses 3.12 features (e.g., `type` statement, improved `f-string` parsing). Two documents give a wrong minimum version.

**Recommendation:** Update `regulatory-agent-kit.md` and `architecture.md` to specify Python 3.12+.

---

### C3. PostgreSQL Version: 14+ vs 16+

| Document | PostgreSQL Version |
|---|---|
| `regulatory-agent-kit.md` | **14+** |
| `architecture.md` | **14+** |
| `hld.md` | **16+** |
| `lld.md` | **16** (DDL uses `gen_random_uuid()` without extension) |
| `sad.md` | **16+** |
| `data-model.md` | **16+** |
| `infrastructure.md` | **16** (`postgres:16-alpine`) |
| `adr/003-*.md` | Selects PostgreSQL (version determined by later ADRs) |

**Impact:** PostgreSQL 14 does not support some features used in the DDL. An operator deploying PG 14/15 based on the PRD or architecture doc may encounter failures.

**Recommendation:** Update `regulatory-agent-kit.md` and `architecture.md` to specify PostgreSQL 16+.

---

### C4. Observability Platform: Langfuse vs MLflow

| Document | Primary Trace Collector |
|---|---|
| `regulatory-agent-kit.md` | **Langfuse** (cloud or self-hosted); references Langfuse API keys, WAL buffering for Langfuse outages |
| `architecture.md` | **Langfuse**; references `langfuse-langchain` callback handler |
| `adr/005-*.md` | **Selects MLflow**, replacing Langfuse |
| `hld.md` | **MLflow 2.18+** (self-hosted, PostgreSQL + S3 backend) |
| `lld.md` | **MLflow** (PydanticAI autolog, LiteLLM callbacks) |
| `sad.md` | **MLflow >= 2.18.0**; states "No ClickHouse dependency" |
| `infrastructure.md` | **MLflow** (mlflow-server pod, port 5000) |
| `data-model.md` | **mlflow schema** in PostgreSQL |

**Impact:** The PRD and architecture doc reference a completely different observability stack (Langfuse with ClickHouse-based storage) than what the implementation docs describe (MLflow on PostgreSQL + S3). Integration code, deployment manifests, and configuration will all differ.

**Recommendation:** Update `regulatory-agent-kit.md` and `architecture.md` to reference MLflow as selected in ADR-005.

---

### C5. Pipeline Run Status Values vs State Machine

| Source | Status Values |
|---|---|
| `lld.md` state machine | `PENDING`, `COST_ESTIMATION`, `ANALYZING`, `AWAITING_IMPACT_REVIEW`, `REFACTORING`, `TESTING`, `AWAITING_MERGE_REVIEW`, `REPORTING`, `COMPLETED`, `FAILED`, `REJECTED`, `COST_REJECTED` (12 states) |
| `data-model.md` / `lld.md` DB CHECK | `pending`, `running`, `cost_rejected`, `completed`, `failed`, `rejected`, `cancelled` (7 values) |

**Impact:** The database cannot represent the intermediate workflow states (e.g., `analyzing`, `refactoring`, `testing`). Either the state machine or the DB schema is wrong. Additionally:
- `cancelled` exists in the DB but not the state machine.
- `COST_ESTIMATION`, `ANALYZING`, `REFACTORING`, `TESTING`, `REPORTING` exist in the state machine but not the DB.

**Recommendation:** Reconcile by either:
- (a) Adding intermediate states to the DB CHECK constraint, or
- (b) Documenting that Temporal manages granular state and the DB `status` field only tracks coarse lifecycle states (with a mapping table).

---

### C6. Conflict Handling: "Never Auto-Resolves" vs Auto-Resolution Options

- `regulatory-agent-kit.md` Section 4.6: *"the kit **never** attempts to automatically resolve regulation conflicts, as these are legal decisions"*
- `architecture.md` Section 8.2: *"the engine **never** automatically resolves regulation conflicts"*
- Same documents define `conflict_handling` enum with: `escalate_to_human` | **`apply_both`** | **`defer_to_referenced`**

**Impact:** `apply_both` and `defer_to_referenced` are automatic resolution strategies, directly contradicting the "never auto-resolves" claim. Implementers will not know whether to build automatic resolution or always escalate.

**Recommendation:** Either:
- (a) Remove `apply_both` and `defer_to_referenced` from the enum and always escalate, or
- (b) Soften the "never auto-resolves" language to "conflicts are escalated by default; plugin authors may opt into `apply_both` or `defer_to_referenced` for well-understood relationships."

---

### C7. Database Constraint Bug: `branch_when_active` Is a Tautology

`lld.md` defines the `branch_when_active` constraint on `repository_progress` as:

```sql
(status IN ('completed','in_progress') AND branch_name IS NOT NULL)
OR status NOT IN ('completed','in_progress')
OR branch_name IS NOT NULL
```

The third clause (`OR branch_name IS NOT NULL`) makes the entire constraint **always true** regardless of data. The intended constraint is likely:

```sql
(status IN ('completed','in_progress') AND branch_name IS NOT NULL)
OR status NOT IN ('completed','in_progress')
```

**Impact:** The constraint provides zero data integrity protection. Rows with `status = 'in_progress'` and `branch_name = NULL` will be accepted silently.

**Recommendation:** Remove the redundant third clause from the CHECK constraint definition in `lld.md`.

---

## MISSING — Key Areas Lacking Documentation

### M1. `architecture.md` Not Updated After ADR Decisions

`architecture.md` was not updated to reflect ADR-002 (Temporal), ADR-004 (Python 3.12+, specific library choices), or ADR-005 (MLflow). It remains frozen at the pre-ADR state, making it unreliable as an architecture reference.

**Recommendation:** Perform a full pass on `architecture.md` incorporating all accepted ADR decisions.

---

### M2. `regulatory-agent-kit.md` (PRD) Not Updated After ADR Decisions

Same as M1 — the PRD still references LangGraph, Langfuse, Python 3.11+, and PostgreSQL 14+. It should be the authoritative product document but describes a different system than what the HLD/LLD/SAD specify.

**Recommendation:** Update technology references in the PRD to match accepted ADRs, or add a notice that technical details are governed by the ADRs and downstream docs.

---

### M3. Lite Mode Feature Parity Not Documented

Multiple documents reference Lite Mode (`rak run --lite`) but none specify which features are unavailable. Open questions:

- Can Lite Mode handle cross-regulation conflicts?
- Is Elasticsearch required for the Analyzer Agent, and if so, what happens without it?
- How does Lite Mode handle human checkpoints without Temporal signals?
- `hld.md` says "No Temporal (direct function calls)" — but no document describes this fallback path.

**Recommendation:** Add a "Lite Mode Limitations" section to `infrastructure.md` or `architecture.md` with a feature-by-feature comparison.

---

### M4. Missing ADR for Elasticsearch Selection

Elasticsearch 8.x is used across all docs but has no ADR. `adr/003-*.md` explicitly states: "Elasticsearch — already specified in the architecture... Not in scope for this ADR." No evaluation of alternatives (OpenSearch, Typesense, Meilisearch, PostgreSQL full-text search) was documented.

**Recommendation:** Create ADR-006 documenting the Elasticsearch selection and rationale.

---

### M5. No Error Recovery / Operational Runbook

While `rak resume`, `rak retry-failures`, and `rak rollback` are mentioned across multiple documents, there is no dedicated operational runbook or troubleshooting guide. The HLD notes failure modes (Section 9.1) but there is no centralized error recovery procedure.

**Recommendation:** Create `docs/operations/runbook.md` covering common failure scenarios, diagnostic steps, and recovery commands.

---

### M6. `rak` CLI Command Reference Missing

CLI commands appear scattered across documents (`rak run`, `rak plugin init/validate/test/search`, `rak status`, `rak retry-failures`, `rak rollback`, `rak resume`). No single CLI reference document exists.

**Recommendation:** Create `docs/cli-reference.md` with all commands, flags, and examples consolidated in one place.

---

### M7. Jinja2 Template Authoring Guide Missing

The plugin system depends heavily on Jinja2 templates for remediation and test generation. No document describes the template context variables, available filters, or how to author templates for new regulations.

**Recommendation:** Create `docs/plugin-template-guide.md` covering template context, available variables, and worked examples.

---

### M8. Condition DSL Implementation Details Missing in LLD

`architecture.md` defines the Condition DSL operators (`AND`, `OR`, `NOT`, `implements`, `has_annotation`, etc.). The LLD references `ConditionDSL` and `ConditionAST` classes but does not specify the parsing algorithm, operator precedence, or how AST-unevaluable conditions are delegated to the LLM.

**Recommendation:** Add a dedicated subsection in `lld.md` covering the Condition DSL parser implementation, operator precedence rules, and the LLM delegation mechanism.

---

### M9. HLD PostgreSQL `max_connections` Arithmetic Error

`hld.md` Section 4.6 states `max_connections = 200` but the allocation totals **250**:

| Consumer       | Connections |
|----------------|-------------|
| Temporal        | 50          |
| Workers (5x30) | 150         |
| MLflow          | 20          |
| Headroom        | 30          |
| **Total**       | **250**     |

The text acknowledges "250 (headroom above max_connections triggers PgBouncer)" but this contradicts the stated `max_connections = 200` setting. It is unclear whether PgBouncer is mandatory or optional.

**Recommendation:** Either increase `max_connections` to >= 250 in the documentation, or explicitly state that PgBouncer is mandatory and document its configuration.

---

## REDUNDANT — Suggested Areas for Consolidation

### R1. Plugin Schema Defined in 4 Places

The regulation plugin YAML schema is fully or partially defined in:

1. `architecture.md` Section 3.2 (generic example) + Section 12 (full schema reference)
2. `regulatory-agent-kit.md` Section 4.2 (DORA-specific example)
3. `lld.md` (Pydantic model definitions)
4. `sad.md` (references architecture.md)

**Recommendation:** Define the canonical schema once in `architecture.md` Section 12 (or a standalone `docs/plugin-schema.md`) and have all other documents reference it by link.

---

### R2. Workflow State Machine Diagram in 4 Places

The state machine (`IDLE -> COST_ESTIMATION -> ANALYZING -> ...`) appears in:

1. `architecture.md` Section 4.1
2. `regulatory-agent-kit.md` Section 4.3
3. `hld.md` Section 5.1
4. `sad.md` (workflow section)

All four versions are slightly different (architecture.md uses LangGraph terminology; HLD/SAD use Temporal terminology).

**Recommendation:** Single source of truth in `architecture.md` (once updated for Temporal); other docs reference it by link.

---

### R3. Agent Contracts Table Repeated in 4+ Places

The four-agent table (Analyzer, Refactor, TestGenerator, Reporter) with input/output contracts appears in `architecture.md`, `regulatory-agent-kit.md`, `hld.md`, `lld.md`, and `sad.md`.

**Recommendation:** Define canonical contracts in `architecture.md`; the LLD adds implementation-level details only (class names, method signatures).

---

### R4. Security Boundaries Listed in 4 Places

The 8 security boundaries are repeated nearly identically in:

1. `architecture.md` Section 9
2. `regulatory-agent-kit.md` (security section)
3. `sad.md` (security section)
4. `hld.md` (partial)

**Recommendation:** Single source in `architecture.md`; other docs reference it.

---

### R5. Deployment Options Table in 5 Places

Lite Mode / Docker Compose / Kubernetes / AWS ECS / Serverless options appear in:

1. `architecture.md` Section 11
2. `regulatory-agent-kit.md` Section 5
3. `hld.md` Section 3
4. `sad.md` (deployment section)
5. `infrastructure.md` Section 1

**Recommendation:** `infrastructure.md` should be the single source for deployment details. Other docs link to it with a brief one-line summary.

---

### R6. Event Schema and Event Sources in 3 Places

The event JSON schema and the four event source types (Kafka, Webhook, SQS, File) are repeated in:

1. `architecture.md` Section 5
2. `regulatory-agent-kit.md` Section 4.4
3. `sad.md` (event architecture section)

**Recommendation:** Consolidate into `architecture.md` Section 5; other docs reference it.

---

### R7. Integration Reference Table in 3 Places

The full integration table (Kafka, Webhook, SQS, Elasticsearch, PostgreSQL, Git providers, notifications, storage, CI/CD, secrets) appears in:

1. `architecture.md` Section 11
2. `hld.md` (integration section)
3. `sad.md` (integration section)

**Recommendation:** Consolidate into `infrastructure.md`; other docs reference it.

---

## SUGGESTIONS — Minor Clarity and Formatting Improvements

### S1. `architecture.md` Final Line References Non-Existent File

Line 671 of `architecture.md` references:

> `see docs/regulatory-agent-kit-v2.md`

The actual file is `docs/regulatory-agent-kit.md` (no `-v2` suffix).

**Recommendation:** Fix the link to `regulatory-agent-kit.md`.

---

### S2. ADR Numbering Gap for PostgreSQL Version Selection

ADRs are numbered 001-005 but the specific PostgreSQL **version** (16+) selection appears undocumented. ADR-003 covers relational vs NoSQL but does not specify 16+ as a minimum version.

**Recommendation:** Add a "Version Selection" section to ADR-003 or ADR-004 documenting why PG 16+ was chosen over PG 14/15.

---

### S3. PCI-DSS v4.0 Timeline Inconsistency in PRD

`regulatory-agent-kit.md` states the PCI-DSS v4.0 deadline was **March 31, 2025** but schedules the PCI-DSS plugin for **April-June 2026** (Phase 2). Given the document date of 2026-03-26, the deadline has already passed by 12 months.

**Recommendation:** Add a note acknowledging the deadline has passed and explaining why the plugin is still valuable (e.g., ongoing compliance maintenance, audit remediation).

---

### S4. LLD Checkpoint Decision Uniqueness Constraint

The `UNIQUE (run_id, checkpoint_type, decided_at)` constraint on `checkpoint_decisions` includes `decided_at`, meaning re-reviews create new rows (timestamps will always differ). The doc says "last decision wins" but the schema does not enforce single-decision-per-type.

**Recommendation:** Clarify whether this is intentional (preserving audit trail of all decisions) or whether the constraint should be `UNIQUE (run_id, checkpoint_type)`.

---

### S5. HLD and Infrastructure Should Cross-Reference Versions

`hld.md` specifies `LiteLLM >= 1.40+` and `MLflow >= 2.18+` but `infrastructure.md` uses `ghcr.io/berriai/litellm:main` (unpinned tag).

**Recommendation:** Pin container image tags in `infrastructure.md` to match the version requirements stated in `hld.md` and `sad.md`.

---

### S6. `data-model.md` Audit Entry FK Note Missing from LLD

`data-model.md` correctly notes that `audit_entries.run_id` is **not** a foreign key due to PostgreSQL partitioning limitations and is enforced at the application level. This important constraint is not mentioned in `lld.md` where the schema first appears.

**Recommendation:** Add a note in `lld.md` at the `audit_entries` table definition explaining the partitioning FK limitation.

---

### S7. No Document Hierarchy or Suggested Reading Order

No document explains which doc to read first or how they relate to each other. Suggested reading order:

1. `regulatory-agent-kit.md` — Why (market context, product requirements)
2. `architecture.md` — What (system design, contracts)
3. `docs/adr/` — Decisions (technology selections with rationale)
4. `sad.md` — How, architecturally (quality attributes, design principles)
5. `hld.md` — How, operationally (deployment topology, scaling, failure modes)
6. `lld.md` — How, in code (classes, algorithms, schemas)
7. `data-model.md` — Data layer (tables, indexes, access control)
8. `infrastructure.md` — Deployment (Docker, Kubernetes, cloud providers, CI/CD)

**Recommendation:** Add a `docs/README.md` or a "How to Read This Documentation" section at the top of `architecture.md`.

---

## Summary Table

| ID  | Category       | Title                                          | Affected Documents                                     |
|-----|----------------|------------------------------------------------|--------------------------------------------------------|
| C1  | **CRITICAL**   | LangGraph vs Temporal + PydanticAI             | `regulatory-agent-kit.md`, `architecture.md`           |
| C2  | **CRITICAL**   | Python 3.11+ vs 3.12+                          | `regulatory-agent-kit.md`, `architecture.md`           |
| C3  | **CRITICAL**   | PostgreSQL 14+ vs 16+                          | `regulatory-agent-kit.md`, `architecture.md`           |
| C4  | **CRITICAL**   | Langfuse vs MLflow                             | `regulatory-agent-kit.md`, `architecture.md`           |
| C5  | **CRITICAL**   | Pipeline status values vs state machine        | `lld.md`, `data-model.md`                              |
| C6  | **CRITICAL**   | "Never auto-resolves" vs auto-resolution enum  | `regulatory-agent-kit.md`, `architecture.md`           |
| C7  | **CRITICAL**   | `branch_when_active` constraint is a tautology | `lld.md`                                               |
| M1  | **MISSING**    | `architecture.md` not updated after ADRs       | `architecture.md`                                      |
| M2  | **MISSING**    | PRD not updated after ADRs                     | `regulatory-agent-kit.md`                              |
| M3  | **MISSING**    | Lite Mode feature parity undocumented          | All deployment-referencing docs                        |
| M4  | **MISSING**    | No ADR for Elasticsearch selection             | `docs/adr/`                                            |
| M5  | **MISSING**    | No operational runbook                         | (new doc needed)                                       |
| M6  | **MISSING**    | No CLI command reference                       | (new doc needed)                                       |
| M7  | **MISSING**    | No Jinja2 template authoring guide             | (new doc needed)                                       |
| M8  | **MISSING**    | Condition DSL implementation details           | `lld.md`                                               |
| M9  | **MISSING**    | PostgreSQL max_connections arithmetic error     | `hld.md`                                               |
| R1  | **REDUNDANT**  | Plugin schema in 4 places                      | `architecture.md`, `regulatory-agent-kit.md`, `lld.md`, `sad.md` |
| R2  | **REDUNDANT**  | State machine in 4 places                      | `architecture.md`, `regulatory-agent-kit.md`, `hld.md`, `sad.md` |
| R3  | **REDUNDANT**  | Agent contracts in 4+ places                   | `architecture.md`, `regulatory-agent-kit.md`, `hld.md`, `lld.md`, `sad.md` |
| R4  | **REDUNDANT**  | Security boundaries in 4 places                | `architecture.md`, `regulatory-agent-kit.md`, `sad.md`, `hld.md` |
| R5  | **REDUNDANT**  | Deployment options in 5 places                 | `architecture.md`, `regulatory-agent-kit.md`, `hld.md`, `sad.md`, `infrastructure.md` |
| R6  | **REDUNDANT**  | Event schema in 3 places                       | `architecture.md`, `regulatory-agent-kit.md`, `sad.md` |
| R7  | **REDUNDANT**  | Integration table in 3 places                  | `architecture.md`, `hld.md`, `sad.md`                  |
| S1  | **SUGGESTION** | Broken file reference in `architecture.md`     | `architecture.md`                                      |
| S2  | **SUGGESTION** | ADR numbering gap for PG version               | `docs/adr/`                                            |
| S3  | **SUGGESTION** | PCI-DSS timeline inconsistency                 | `regulatory-agent-kit.md`                              |
| S4  | **SUGGESTION** | Checkpoint uniqueness constraint ambiguity      | `lld.md`                                               |
| S5  | **SUGGESTION** | Unpinned container image tags                  | `infrastructure.md`, `hld.md`                          |
| S6  | **SUGGESTION** | Audit FK note missing from LLD                 | `lld.md`                                               |
| S7  | **SUGGESTION** | No document hierarchy or reading order         | (new section needed)                                   |

---

## Root Cause Analysis

The critical contradictions (C1-C4) share a single root cause:

> **`architecture.md` and `regulatory-agent-kit.md` were not updated after ADR-002, ADR-004, and ADR-005 were accepted.**

The ADR process worked correctly — decisions were documented with full rationale and alternatives. The downstream documents (`hld.md`, `lld.md`, `sad.md`, `data-model.md`, `infrastructure.md`) were all written *after* the ADRs and are internally consistent with each other.

The two upstream documents (`architecture.md` and `regulatory-agent-kit.md`) remain frozen at the pre-ADR state, creating a split where:

- **Pre-ADR documents** describe: LangGraph + Langfuse + Python 3.11+ + PostgreSQL 14+
- **Post-ADR documents** describe: Temporal + PydanticAI + MLflow + Python 3.12+ + PostgreSQL 16+

### Recommended Fix Priority

1. **Immediate (blocks implementation):** Update `architecture.md` and `regulatory-agent-kit.md` to reflect all accepted ADR decisions (resolves C1, C2, C3, C4).
2. **High (data integrity):** Fix `branch_when_active` constraint (C7) and reconcile pipeline status values (C5).
3. **High (design clarity):** Resolve conflict handling semantics (C6).
4. **Medium (reduces drift):** Consolidate redundant content (R1-R7) to prevent future inconsistencies.
5. **Low (polish):** Address missing docs (M3-M8) and suggestions (S1-S7) as part of regular documentation maintenance.
