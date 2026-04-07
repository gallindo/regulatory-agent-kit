# ADR-003: Database Selection — Relational vs NoSQL

**Status:** Accepted
**Date:** 2026-03-27
**Decision Makers:** Engineering Team
**Related:** [ADR-002](002-langgraph-vs-temporal-pydanticai.md) (Temporal + PydanticAI selection)

---

## Context

`regulatory-agent-kit` requires persistent storage for several distinct data categories. [ADR-002](002-langgraph-vs-temporal-pydanticai.md) selected Temporal + PydanticAI as the orchestration framework, which constrains certain storage decisions (Temporal server requires a relational backend). This ADR evaluates whether the remaining application-level storage needs are best served by a relational database, a NoSQL database, or a combination.

### Data Categories

Analysis of `framework-spec.md` and the product requirements identifies six distinct storage concerns:

| # | Data Category | Shape | Access Pattern | Retention | Volume |
|---|---|---|---|---|---|
| D1 | **Temporal workflow state** | Event-sourced history (append-only) | Write-heavy during execution; read on replay/query | Configurable retention | High — every workflow action is an event |
| D2 | **Pipeline run metadata** | Structured records: `{run_id, regulation_id, status, created_at, repositories[], cost}` | Write-once, read-many; query by status, regulation, date range | Permanent | Low — one record per pipeline run |
| D3 | **Per-repository progress** | Structured records: `{repo_url, run_id, status, branch_name, commit_sha}` | Frequent status updates; query by run_id, status | Permanent | Moderate — one record per repo per run |
| D4 | **Audit trail** | Immutable, append-only JSON-LD documents; cryptographically signed | Write-once, never updated; query by run_id, regulation_id, date range; legally required to be tamper-evident | Permanent (regulatory requirement) | High — every agent decision, LLM call, human approval |
| D5 | **Human checkpoint decisions** | Structured records: `{actor, decision, rationale, timestamp, signature, run_id, checkpoint_type}` | Write-once; query by run_id, actor, date; used in audit reports | Permanent | Low — 2 per pipeline run |
| D6 | **Cross-regulation conflict log** | Semi-structured: `{conflicting_rule_ids[], affected_code_regions[], resolution, human_decision}` | Write-once; query by regulation_id, run_id | Permanent | Low — only on conflicts |

**Not in scope for this ADR:**
- **Elasticsearch** — already specified in the architecture as the search/knowledge base for regulatory documents. This is a read-optimized search index, not a primary data store.
- **Object storage** (S3/GCS/Azure Blob) — already specified for permanent trace replication and compliance report storage.
- **Langfuse** — external trace collector with its own storage. Application writes to it but does not manage its database.

---

## Options

### Option A: PostgreSQL Only (Single Relational Database)

All six data categories stored in a single PostgreSQL instance. Temporal uses it for workflow state. Application tables handle pipeline metadata, progress tracking, audit trails, and conflict logs.

```
+-------------------------------------------+
|              PostgreSQL 16+               |
|                                           |
|  +-------------------------------------+ |
|  | temporal schema                      | |
|  | (workflow events, visibility, tasks) | |
|  +-------------------------------------+ |
|                                           |
|  +-------------------------------------+ |
|  | rak schema                           | |
|  |  - pipeline_runs          (D2)       | |
|  |  - repository_progress    (D3)       | |
|  |  - audit_entries          (D4)       | |
|  |  - checkpoint_decisions   (D5)       | |
|  |  - conflict_log           (D6)       | |
|  +-------------------------------------+ |
+-------------------------------------------+
```

### Option B: PostgreSQL + MongoDB (Relational + Document Store)

PostgreSQL for Temporal and structured application data. MongoDB for audit trails and semi-structured data.

```
+---------------------------+    +---------------------------+
|      PostgreSQL 16+       |    |       MongoDB 7+          |
|                           |    |                           |
|  temporal schema          |    |  audit_entries     (D4)   |
|  pipeline_runs     (D2)  |    |  conflict_log      (D6)   |
|  repo_progress     (D3)  |    |                           |
|  checkpoint_decisions(D5)|    |                           |
+---------------------------+    +---------------------------+
```

### Option C: PostgreSQL + DynamoDB (Relational + Key-Value/Document)

PostgreSQL for Temporal and structured data. DynamoDB for audit trails (append-only, high-write).

```
+---------------------------+    +---------------------------+
|      PostgreSQL 16+       |    |       DynamoDB            |
|                           |    |                           |
|  temporal schema          |    |  audit_entries     (D4)   |
|  pipeline_runs     (D2)  |    |  conflict_log      (D6)   |
|  repo_progress     (D3)  |    |                           |
|  checkpoint_decisions(D5)|    |                           |
+---------------------------+    +---------------------------+
```

### Option D: PostgreSQL + Cassandra (Relational + Wide-Column)

PostgreSQL for Temporal and structured data. Cassandra for audit trails (high-write, append-only, time-series-like).

```
+---------------------------+    +---------------------------+
|      PostgreSQL 16+       |    |       Cassandra 4+        |
|                           |    |                           |
|  temporal schema          |    |  audit_entries     (D4)   |
|  pipeline_runs     (D2)  |    |  conflict_log      (D6)   |
|  repo_progress     (D3)  |    |                           |
|  checkpoint_decisions(D5)|    |                           |
+---------------------------+    +---------------------------+
```

---

## Analysis

### Constraint: Temporal Requires a Relational Database

Temporal server supports **PostgreSQL**, **MySQL**, and **Cassandra** as persistence backends. For production deployments, Temporal recommends PostgreSQL or Cassandra. Since the application already requires PostgreSQL for Temporal (D1), the question is not "relational vs NoSQL" but rather **"PostgreSQL alone vs PostgreSQL + a NoSQL store for specific data categories."**

This is the central framing for this decision.

### Evaluating Each Data Category

#### D2, D3, D5 — Pipeline Runs, Repository Progress, Checkpoint Decisions

These are **strongly relational**: structured records with foreign key relationships (run_id links runs to repos to checkpoints), status enums, frequent filtering and joins (e.g., "all failed repositories for run X"), and transactional consistency requirements (status updates must be atomic).

| | PostgreSQL | MongoDB | DynamoDB | Cassandra |
|---|---|---|---|---|
| Schema enforcement | Strong (DDL + constraints) | Application-level | Application-level | Partial (CQL) |
| Foreign keys | Native | Not supported | Not supported | Not supported |
| Complex queries | Full SQL (joins, aggregates, window functions) | Aggregation pipeline | Limited (scan-heavy) | Limited (partition key queries) |
| Transactions | Full ACID | Multi-doc transactions (slower) | Limited (single-item or tx table) | Lightweight transactions only |
| Fit | Excellent | Adequate but no advantage | Poor fit | Poor fit |

**Verdict:** PostgreSQL is the natural and optimal choice. No NoSQL database provides an advantage for structured, relational, transactional data with complex query patterns.

#### D4 — Audit Trail

This is the only data category where NoSQL databases have a plausible advantage. Audit entries are:
- **Append-only** — never updated or deleted
- **JSON-LD documents** — semi-structured, with variable fields depending on event type
- **Cryptographically signed** — each entry is self-contained
- **High-volume** — every LLM call, tool invocation, and state transition generates an entry
- **Query patterns:** primarily by `run_id` (get all entries for a run), `regulation_id`, and date range

**Can PostgreSQL handle this?**

| Concern | PostgreSQL Capability |
|---|---|
| JSON-LD documents | `JSONB` column type with indexing (GIN indexes for full JSON path queries) |
| Append-only | `INSERT`-only table with no `UPDATE`/`DELETE` grants; or partitioned table with immutable partitions |
| Write throughput | PostgreSQL handles thousands of inserts/second with batch inserts and partitioning; well within this application's needs |
| Tamper evidence | Application-level cryptographic signatures (stored in the record itself); database-level: append-only table with row-level security and restricted `DELETE`/`UPDATE` permissions |
| Time-range queries | Table partitioning by date (`PARTITION BY RANGE(created_at)`) with partition pruning |
| Retention management | Drop old partitions efficiently (`DROP PARTITION` is O(1)) |
| Scale ceiling | A single PostgreSQL instance comfortably handles tens of millions of audit rows. This application produces at most thousands of entries per pipeline run. |

**Would MongoDB/DynamoDB/Cassandra be better?**

| Advantage Claimed | Reality for This Application |
|---|---|
| "Schema flexibility for JSON documents" | PostgreSQL `JSONB` provides equivalent flexibility with optional schema validation via `CHECK` constraints. |
| "Better write throughput" | The application produces hundreds to low thousands of audit entries per pipeline run, not millions per second. PostgreSQL's write throughput is not a bottleneck. |
| "Native append-only semantics" | No NoSQL database provides true append-only guarantees at the database level either. Immutability is enforced by application-level cryptographic signatures in all cases. |
| "Horizontal write scaling" | Not needed. Audit write volume scales linearly with pipeline runs, not with user traffic. A single PostgreSQL instance is sufficient for years of operation. |

**Verdict:** PostgreSQL handles the audit trail workload without strain. Adding a second database for this category introduces operational complexity (backup coordination, monitoring, connection management, failure modes) without a concrete performance or capability benefit.

#### D6 — Cross-Regulation Conflict Log

Low-volume, semi-structured records. PostgreSQL `JSONB` is more than adequate. No case for a separate database.

---

### Operational Cost of a Second Database

Adding MongoDB, DynamoDB, or Cassandra introduces:

| Cost | Impact |
|---|---|
| **Infrastructure** | Additional server/cluster to provision, monitor, patch, and back up |
| **Networking** | Cross-service latency; firewall rules; TLS certificates |
| **Backup coordination** | Two backup schedules; point-in-time recovery must be coordinated across both stores for consistency |
| **Monitoring** | Additional dashboards, alerts, and on-call runbooks |
| **Developer experience** | Two query languages; two ORMs/drivers; two connection pools; two failure modes to handle |
| **Docker Compose / Helm** | Additional services in dev and production stacks (the stack already includes Temporal server, PostgreSQL, Elasticsearch, Langfuse, Prometheus/Grafana) |
| **Credential management** | Additional credentials in the secrets manager |
| **Disaster recovery** | Cross-database consistency during restore; more complex RTO/RPO guarantees |

The architecture already specifies 7+ infrastructure services (Temporal server, PostgreSQL, Elasticsearch, Langfuse, Prometheus, Grafana, event source). Adding a second database increases operational burden with no demonstrated benefit.

---

### When Would a Second Database Be Justified?

A NoSQL store for audit data would become justified if:

1. **Write volume exceeds PostgreSQL's capacity** — unlikely unless the application processes thousands of pipeline runs concurrently, each with hundreds of repositories. At that scale, PostgreSQL partitioning and connection pooling (PgBouncer) should be evaluated first.

2. **Multi-region replication is required** — if audit data must be replicated across geographic regions for regulatory reasons (e.g., EU data must stay in EU, US data in US), a globally distributed database like CockroachDB or DynamoDB Global Tables might be warranted. However, the architecture already addresses data residency at the LLM layer (LiteLLM region-based routing), and audit data residency can be handled by deploying region-specific PostgreSQL instances.

3. **Immutable ledger requirements** — if a regulator requires a cryptographically verifiable ledger (beyond application-level signatures), a purpose-built ledger database (AWS QLDB, or a blockchain-anchored solution) might be needed. This is not currently a requirement.

None of these conditions apply today.

---

## Decision

**Use PostgreSQL 16+ as the single database for all application data.**

### Version Selection

PostgreSQL 16 is the minimum required version. Key features used:

- **`gen_random_uuid()`** — native UUID generation without the `pgcrypto` extension (available since PG 13, but PG 16 is required for other reasons)
- **Improved partitioning performance** — partition pruning optimizations in PG 14–16 are critical for the `audit_entries` table
- **Logical replication improvements** — PG 16 supports logical replication from standby servers, useful for exporting audit partitions without impacting the primary
- **`GRANT` on schemas** — PG 16 simplifies schema-level permission management for the three-schema design (temporal, rak, mlflow)
- **Temporal server compatibility** — Temporal requires PG 13+ but recommends PG 15+; PG 16 is fully supported

### Schema Design

> **Note:** This DDL is a decision-time snapshot. For the canonical schema with all constraints, indexes, and security grants, see [`data-model.md`](../data-model.md).

```sql
-- Separate schema from Temporal's internal tables
CREATE SCHEMA rak;

-- D2: Pipeline run metadata
CREATE TABLE rak.pipeline_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    regulation_id   TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed','cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    total_repos     INTEGER NOT NULL,
    estimated_cost  NUMERIC(10,4),
    actual_cost     NUMERIC(10,4),
    config_snapshot JSONB NOT NULL  -- plugin version, model versions, parameters
);

-- D3: Per-repository progress
CREATE TABLE rak.repository_progress (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID NOT NULL REFERENCES rak.pipeline_runs(run_id),
    repo_url    TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed','failed','skipped')),
    branch_name TEXT,
    commit_sha  TEXT,
    pr_url      TEXT,
    error       TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, repo_url)
);

-- D4: Audit trail (partitioned, append-only)
CREATE TABLE rak.audit_entries (
    entry_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL,
    event_type      TEXT NOT NULL,  -- 'llm_call','tool_invocation','state_transition','human_decision',...
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload         JSONB NOT NULL,  -- event-type-specific data (JSON-LD)
    signature       TEXT NOT NULL,   -- cryptographic signature of payload
    PRIMARY KEY (timestamp, entry_id)
) PARTITION BY RANGE (timestamp);

-- Create partitions (automated via pg_partman or application code)
-- Example: monthly partitions
CREATE TABLE rak.audit_entries_2026_03 PARTITION OF rak.audit_entries
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- D5: Human checkpoint decisions
CREATE TABLE rak.checkpoint_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES rak.pipeline_runs(run_id),
    checkpoint_type TEXT NOT NULL CHECK (checkpoint_type IN ('impact_review','merge_review')),
    actor           TEXT NOT NULL,
    decision        TEXT NOT NULL CHECK (decision IN ('approved','rejected','modifications_requested')),
    rationale       TEXT,
    signature       TEXT NOT NULL,  -- cryptographic signature
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- D6: Cross-regulation conflict log
CREATE TABLE rak.conflict_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES rak.pipeline_runs(run_id),
    conflicting_rules   JSONB NOT NULL,  -- [{regulation_id, rule_id}, ...]
    affected_regions    JSONB NOT NULL,  -- [{file, start_line, end_line}, ...]
    resolution          TEXT,
    human_decision_id   UUID REFERENCES rak.checkpoint_decisions(id),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX idx_pipeline_runs_status ON rak.pipeline_runs(status);
CREATE INDEX idx_pipeline_runs_regulation ON rak.pipeline_runs(regulation_id);
CREATE INDEX idx_repo_progress_run ON rak.repository_progress(run_id);
CREATE INDEX idx_repo_progress_status ON rak.repository_progress(status);
CREATE INDEX idx_audit_run ON rak.audit_entries(run_id);
CREATE INDEX idx_audit_type ON rak.audit_entries(event_type);
CREATE INDEX idx_audit_payload ON rak.audit_entries USING GIN(payload);
CREATE INDEX idx_checkpoint_run ON rak.checkpoint_decisions(run_id);
```

### Audit Trail Immutability Enforcement

```sql
-- Prevent UPDATE and DELETE on audit_entries via row-level security
ALTER TABLE rak.audit_entries ENABLE ROW LEVEL SECURITY;

-- Application role can only INSERT and SELECT
CREATE ROLE rak_app;
GRANT INSERT, SELECT ON rak.audit_entries TO rak_app;
-- No UPDATE or DELETE granted

-- Partition management role (for dropping old partitions if retention policy allows)
CREATE ROLE rak_admin;
GRANT ALL ON rak.audit_entries TO rak_admin;
```

---

## Consequences

1. **Single database to operate** — PostgreSQL serves Temporal's event store, application data, and audit trails. One backup strategy, one monitoring stack, one connection pool.

2. **Transactional consistency** — Pipeline run metadata, repository progress, and checkpoint decisions are in the same database, enabling atomic operations (e.g., updating repo status and writing an audit entry in a single transaction).

3. **JSONB for semi-structured data** — Audit entries (`JSONB` payload) and conflict logs (`JSONB` arrays) use PostgreSQL's JSON capabilities with GIN indexing, avoiding the need for a document store.

4. **Partitioned audit table** — Time-based partitioning enables efficient retention management (drop old partitions) and query performance (partition pruning on date ranges).

5. **Immutability via access control** — The audit trail's append-only property is enforced by PostgreSQL role permissions (no `UPDATE`/`DELETE` grants) and application-level cryptographic signatures.

6. **Future migration path** — If audit volume eventually exceeds PostgreSQL's capacity, the `audit_entries` table can be migrated to a dedicated store (e.g., TimescaleDB for time-series optimization, or a separate PostgreSQL instance) without affecting other application data. The partitioned table design makes this migration straightforward.

7. **Alignment with deployment options** — The "lite mode" (`rak run --lite`) can use SQLite for the `rak` schema (with the same table structure), while production deployments use PostgreSQL. Temporal also supports SQLite for development.

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| PostgreSQL as single point of failure | HIGH | Standard HA deployment: streaming replication with automatic failover (Patroni, pg_auto_failover, or managed PostgreSQL with HA). Temporal supports PostgreSQL HA configurations. |
| Audit table grows unbounded | MEDIUM | Time-based partitioning with `pg_partman` for automated partition creation. Retention policy drops partitions older than the configured period (default: permanent for regulatory data, but configurable). Cold partitions can be exported to object storage. |
| Connection pool exhaustion (Temporal + app sharing one database) | MEDIUM | Separate connection pools: Temporal server uses its own pool (configured in Temporal's `persistence` config); application uses PgBouncer. Different PostgreSQL schemas provide logical isolation. |
| JSONB query performance at scale | LOW | GIN indexes on `payload` column. For specific high-frequency queries, expression indexes on extracted JSON paths (e.g., `CREATE INDEX ON rak.audit_entries ((payload->>'model_id'))`). |

---

## References

- [Temporal Persistence Configuration](https://docs.temporal.io/self-hosted-guide/defaults#persistence)
- [PostgreSQL JSONB Documentation](https://www.postgresql.org/docs/16/datatype-json.html)
- [PostgreSQL Table Partitioning](https://www.postgresql.org/docs/16/ddl-partitioning.html)
- [pg_partman — Partition Management](https://github.com/pgpartman/pg_partman)
- [`docs/framework-spec.md`](../framework-spec.md) — Framework architecture specification
- [ADR-002](002-langgraph-vs-temporal-pydanticai.md) — Temporal + PydanticAI selection
