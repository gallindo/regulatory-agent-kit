# Operational Runbook

**Audience:** Platform engineers, SRE, on-call operators
**Related:** [`system-design.md` Section 9 — HA and Disaster Recovery](../system-design.md), [`infrastructure.md`](../infrastructure.md)

---

## Severity Matrix

Use this matrix to assess urgency when responding to incidents:

| Severity | Auto-Recovers? | Response | Examples |
|---|---|---|---|
| **P1 — Critical** | No | Immediate action required | PostgreSQL primary crash, Temporal server down, LiteLLM proxy outage |
| **P2 — High** | Partially | Investigate within 30 min | Elevated repo failure rate (>20%), Elasticsearch cluster yellow, worker OOM |
| **P3 — Medium** | Yes (usually) | Investigate within 2 hours | Single worker pod crash (Temporal replays), high LLM latency, checkpoint timeout |
| **P4 — Low** | Yes | Next business day | Cache hit rate drop, non-critical log volume spike, MLflow UI slow |

**Healthy baselines:** LLM latency <3s p95, repo failure rate <5%, activities/min 50-200, Temporal schedule-to-start <1s.

## 1. Pipeline Failure Scenarios

### 1.1 Pipeline Stuck (No Progress for > 2 Hours)

**Symptoms:** Pipeline run shows `status: running` but no `audit_entries` are being written. Temporal UI shows workflow in `Running` state with no recent events.

**Diagnosis:**

```bash
# Check pipeline status
rak status --run-id <run_id>

# Check Temporal workflow state
temporal workflow describe --workflow-id rak/compliance/<regulation_id>/<run_id_prefix>

# Check worker pods are running
kubectl get pods -n rak -l app=rak-worker

# Check worker logs for errors
kubectl logs -n rak -l app=rak-worker --tail=100
```

**Resolution:**

1. **Worker pod crashed:** Temporal auto-recovers — the workflow replays when a new worker picks it up. Verify worker pods are healthy and wait for auto-recovery.
2. **Worker stuck on LLM call:** Check LiteLLM proxy logs (`kubectl logs -n rak -l app=litellm-proxy`). If the LLM provider is down, LiteLLM's fallback routing should activate. If all providers are down, the activity will timeout per the retry policy and enter `FAILED` state.
3. **Waiting at human checkpoint:** Check if a notification was sent (Slack/email). The workflow blocks on `workflow.wait_condition()` until a human signals approval via `POST /approvals/{run_id}`.
4. **Database connection exhaustion:** Check PostgreSQL connections (`SELECT count(*) FROM pg_stat_activity;`). If near `max_connections`, see Section 3.1.

### 1.2 Repository Processing Failures

**Symptoms:** Some repositories show `status: failed` while others completed.

**Diagnosis:**

```bash
# List failed repos for a run
rak status --run-id <run_id> --filter failed

# Check the error field
psql -c "SELECT repo_url, error FROM rak.repository_progress WHERE run_id = '<run_id>' AND status = 'failed';"
```

**Resolution:**

```bash
# Retry only the failed repositories (successes are not re-processed)
rak retry-failures --run-id <run_id>
```

Common failure causes:
- **Git clone timeout:** Repository too large or Git provider rate-limited. Increase timeout or reduce concurrent clone parallelism.
- **AST parse failure:** Syntactically invalid file. The Analyzer Agent should handle partial ASTs via tree-sitter's error recovery, but edge cases exist. Check the audit log for the specific file.
- **LLM context too large:** File exceeds model context window. The Analyzer Agent should chunk, but very large files may fail. Check audit entries for `error` event_type.

### 1.3 Full Pipeline Rollback

**Symptoms:** Changes were merged or PRs were created, but need to be reversed (e.g., incorrect regulation interpretation).

```bash
# Rollback all changes from a pipeline run
# This closes open PRs, deletes branches, and creates revert PRs for merged changes
rak rollback --run-id <run_id>
```

The rollback manifest is stored in the `audit_entries` table and in S3 (if configured). It records every branch, PR, and commit created by the run.

---

## 2. Infrastructure Failures

### 2.1 Temporal Server Crash

**Impact:** Running workflows pause. No data loss — Temporal is event-sourced.

**Recovery:** Temporal pods auto-restart via Kubernetes. Workflows automatically replay from the last recorded event. No manual intervention required.

**Verification:**

```bash
kubectl get pods -n temporal
temporal workflow list --query "ExecutionStatus = 'Running'"
```

### 2.2 PostgreSQL Primary Crash

**Impact:** All writes fail. Temporal, rak, and MLflow are affected.

**Recovery (with Patroni HA):** Patroni promotes the standby to primary within ~30 seconds. Applications reconnect via the Patroni endpoint.

**Recovery (without HA):** Restore from the latest backup.

```bash
# Check Patroni cluster state
kubectl exec -n data postgresql-0 -- patronictl list

# Verify rak-worker can connect
kubectl logs -n rak -l app=rak-worker --tail=20 | grep "connection"
```

### 2.3 Elasticsearch Cluster Node Failure

**Impact:** Search queries may be slower but remain available (with replication factor >= 1).

**Recovery:** Elasticsearch self-heals — replica shards are promoted on the remaining nodes. Replace the failed node and let shard rebalancing complete.

```bash
kubectl get pods -n data -l app=elasticsearch
curl -s http://elasticsearch:9200/_cluster/health | python -m json.tool
```

### 2.4 MLflow Server Crash

**Impact:** LLM traces are temporarily lost (fire-and-forget callbacks). The PostgreSQL audit trail (system of record) is unaffected.

**Recovery:** MLflow pods auto-restart. Traces resume on next LLM call. Lost traces during downtime are acceptable (MLflow is secondary; the audit trail in PostgreSQL is authoritative).

### 2.5 LiteLLM Proxy Outage

**Impact:** All LLM calls fail. Pipeline activities will timeout and retry.

**Recovery:** LiteLLM pods auto-restart (2+ replicas provide redundancy). If both replicas are down, check for configuration errors in the LiteLLM config.

```bash
kubectl get pods -n rak -l app=litellm-proxy
kubectl logs -n rak -l app=litellm-proxy --tail=50
```

---

## 3. Resource Exhaustion

### 3.1 PostgreSQL Connection Exhaustion

**Symptoms:** `FATAL: too many connections for role "rak_app"` in worker logs.

**Diagnosis:**

```sql
SELECT usename, count(*) FROM pg_stat_activity GROUP BY usename ORDER BY count DESC;
SELECT count(*) FROM pg_stat_activity;
SHOW max_connections;
```

**Resolution:**
1. If running > 3 workers without PgBouncer: deploy PgBouncer (see [`system-design.md` Section 4.6](../system-design.md)).
2. Check for connection leaks: `SELECT * FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '1 hour';`
3. Temporary: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < now() - interval '10 minutes';`

### 3.2 Disk Space (Audit Partition Growth)

**Symptoms:** `ERROR: could not extend file` or audit partition exceeds 5 GB alert.

**Resolution:**

```sql
-- Check partition sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(oid))
FROM pg_class
WHERE relname LIKE 'audit_entries_%'
ORDER BY pg_total_relation_size(oid) DESC;
```

1. Export old partitions to S3: follow the partition export procedure in [`data-model.md`](../data-model.md).
2. Drop exported partitions: `DROP TABLE rak.audit_entries_2025_01;` (only after confirming S3 export with checksum).
3. Pre-create upcoming partitions if `pg_partman` is not configured.

### 3.3 LLM Rate Limiting

**Symptoms:** `429 Too Many Requests` in LiteLLM logs. Pipeline slows significantly.

**Resolution:**
1. LiteLLM's token bucket rate limiter should prevent this. Check LiteLLM config for correct `rpm` and `tpm` limits.
2. Reduce worker concurrency: scale down `rak-worker` replicas.
3. Enable fallback routing: ensure a secondary LLM provider is configured in LiteLLM.

---

## 4. Maintenance Procedures

### 4.1 Database Migrations

Migrations run automatically via an init container (`alembic upgrade head`) before worker/api pods start. For manual migration:

```bash
kubectl exec -n rak deployment/rak-api -- alembic upgrade head
```

### 4.2 Audit Partition Rotation

Monthly partitions should be pre-created. With `pg_partman`:

```sql
SELECT partman.run_maintenance('rak.audit_entries');
```

Without `pg_partman`, manually create the next month's partition before the 1st:

```sql
CREATE TABLE rak.audit_entries_2026_05
  PARTITION OF rak.audit_entries
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

### 4.3 Cache Cleanup

Expired file analysis cache entries can be cleaned up:

```sql
DELETE FROM rak.file_analysis_cache WHERE expires_at < now();
```

This is safe to run at any time — cache misses simply re-trigger analysis.

### 4.4 Credential Rotation

| Credential | Rotation Procedure | Downtime |
|---|---|---|
| LLM API keys | Update in secrets manager; LiteLLM picks up on next request | None |
| Git tokens (GitHub App) | Tokens auto-expire in 1h; no manual rotation needed | None |
| PostgreSQL password | Update in secrets manager; restart rak-worker pods | Brief (pod restart) |
| Elasticsearch API key | Update in secrets manager; restart rak-worker pods | Brief (pod restart) |
| Ed25519 signing key | **Do not rotate** without archiving the old key — signatures on existing audit entries must remain verifiable | None (additive) |
