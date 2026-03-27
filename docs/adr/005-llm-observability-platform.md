# ADR-005: LLM Observability Platform Selection

**Status:** Accepted
**Date:** 2026-03-27
**Decision Makers:** Engineering Team
**Related:** [ADR-002](002-langgraph-vs-temporal-pydanticai.md) (Temporal + PydanticAI), [ADR-004](004-python-stack.md) (Python stack)

---

## Context

`regulatory-agent-kit` requires full observability of every LLM interaction as a first-class output, not a side effect (`architecture.md` SS7). In a regulated environment, the observability platform must capture:

| Observable Event | Data Captured | Retention |
|---|---|---|
| LLM call initiated | Model + version, prompt (sanitized), temperature, max_tokens | Configurable (default: 90 days) |
| LLM response received | Full output, token count, latency, cost, confidence score | Configurable |
| Tool invocation | Tool name, input parameters, output | Configurable |
| Agent state transition | From state, to state, trigger condition, timestamp | Permanent |
| Human checkpoint decision | Actor, decision, rationale, timestamp, cryptographic signature | Permanent |
| Cost tracking | Per-call cost, cumulative pipeline cost, budget threshold | Permanent |

The architecture originally specified Langfuse. This ADR evaluates whether Langfuse (self-hosted) remains the best choice, or whether Opik or MLflow provides a better fit given the stack decisions in ADR-002 (Temporal + PydanticAI) and ADR-003 (PostgreSQL as single database).

### Integration Requirements

The selected platform must integrate with:

| Component | Integration Type | Priority |
|---|---|---|
| **LiteLLM** | Callback/hook on every LLM call (automatic, no per-call instrumentation) | Critical |
| **PydanticAI** | Agent step tracing (tool calls, model interactions, structured outputs) | Critical |
| **Temporal** | Workflow/activity-level spans (complement operational OTel traces) | High |
| **OpenTelemetry** | Accept or export OTLP spans for unified trace view | High |
| **FastAPI** | Request-level tracing for webhook/API endpoints | Medium |

### Infrastructure Constraints

ADR-003 selected PostgreSQL as the single application database to minimize operational complexity. The observability platform's infrastructure requirements are evaluated against this principle: **every additional service must justify its operational cost.**

---

## Options

### Option A: Langfuse (Self-Hosted)

**License:** MIT (all product features). Enterprise security features (SCIM, audit log retention) require a commercial license key.

**Architecture:**
```
+-----------------+     +------------------+     +-------------------+
| Python Workers  |---->|  Langfuse Server |---->|   PostgreSQL      |
| (LiteLLM +      |     |  (Next.js app)   |     |   (metadata)      |
|  PydanticAI)    |     +------------------+     +-------------------+
|                 |             |
|  - @observe     |             v
|  - callbacks    |     +-------------------+
|  - OTel export  |     |   ClickHouse      |
+-----------------+     |   (trace storage)  |
                        +-------------------+
```

**Infrastructure required:** Langfuse server (Node.js/Next.js) + PostgreSQL + ClickHouse.

**Integration details:**

| Component | How | Quality |
|---|---|---|
| LiteLLM | Native callback: `success_callback=["langfuse"]` in LiteLLM config. Zero-code instrumentation. | Excellent — first-class, maintained by both teams |
| PydanticAI | Via OpenTelemetry. PydanticAI emits OTel spans; Langfuse's native OTel endpoint ingests them. Requires `OTEL_EXPORTER_OTLP_ENDPOINT` pointed at Langfuse. | Good — OTel bridge, not native SDK integration |
| Temporal | Via OpenTelemetry. Temporal's OTel interceptor exports workflow/activity spans to Langfuse's OTel endpoint. | Good — same OTel bridge |
| OpenTelemetry | Native OTLP endpoint (since Feb 2025). Accepts gRPC and HTTP OTLP exports. | Excellent — first-class |

**Features relevant to this project:**

| Feature | Available (Self-Hosted MIT)? | Relevance |
|---|---|---|
| LLM call tracing (prompts, completions, tokens, cost, latency) | Yes | Critical — core audit requirement |
| Nested spans (agent -> tool -> LLM call hierarchy) | Yes | Critical — understanding agent decision chains |
| Cost tracking (per-call, cumulative) | Yes | High — cost estimation gate |
| LLM-as-a-judge evaluations | Yes | High — automated quality scoring of agent outputs |
| Prompt management (versioning, deployment) | Yes | Medium — useful for agent prompt iteration |
| Datasets and experiments | Yes | Medium — regression testing of agent behavior |
| Annotation queues | Yes | Medium — human review of agent outputs |
| SSO / project-level RBAC | Yes | Medium — team access control |
| Playground | Yes | Low — interactive prompt testing |
| SCIM provisioning | No (enterprise license) | Not needed |
| Audit log retention policies | No (enterprise license) | Application handles its own audit log (ADR-003) |

**Strengths:**
- Most mature LLM-specific observability platform (~24k GitHub stars).
- Best LiteLLM integration (native callback, maintained by both teams).
- Native OTel endpoint unifies LLM traces + Temporal workflow traces + PydanticAI agent traces in a single UI.
- Purpose-built UI for LLM debugging: prompt/completion diff view, token usage visualization, cost dashboards, latency distributions.
- Active development with strong community. YC W23 backed.

**Weaknesses:**
- **ClickHouse dependency.** Langfuse requires ClickHouse for trace storage (high-cardinality, columnar analytics). This adds a stateful service to the infrastructure stack, conflicting with ADR-003's principle of minimizing database services. ClickHouse is not trivial to operate in production (memory-hungry, requires tuning for write-heavy workloads).
- **Node.js server.** Langfuse is a Next.js application — introduces a Node.js runtime into an otherwise Python-only stack. Operational concern (different runtime, different monitoring, different dependency management).
- **PydanticAI integration is indirect.** Goes through OTel, not a native SDK. Agent-level semantics (tool calls, structured outputs) may require manual span annotation to display correctly in Langfuse's UI.

---

### Option B: Opik (by Comet)

**License:** Apache 2.0. Fully permissive, no feature gates.

**Architecture:**
```
+-----------------+     +------------------+     +-------------------+
| Python Workers  |---->|   Opik Server    |---->|   MySQL /         |
| (LiteLLM +      |     |  (Java/Kotlin)   |     |   PostgreSQL      |
|  PydanticAI)    |     +------------------+     +-------------------+
|                 |             |
|  - opik.track   |             v
|  - callbacks    |     +-------------------+
|  - decorators   |     |   ClickHouse      |
+-----------------+     |   (trace storage)  |
                        +-------------------+
```

**Infrastructure required:** Opik server (Java/Kotlin) + MySQL or PostgreSQL + ClickHouse + Redis.

**Integration details:**

| Component | How | Quality |
|---|---|---|
| LiteLLM | Native callback: `success_callback=["opik"]` in LiteLLM config. | Good — documented, maintained |
| PydanticAI | Via Logfire/OTel bridge. Less direct than Langfuse's OTel endpoint. Documented but requires more configuration. | Adequate — indirect integration |
| Temporal | Via OpenTelemetry export to Opik. Less documented than Langfuse's OTel ingestion. | Adequate — possible but not a primary use case |
| OpenTelemetry | Partial. Opik is not natively OTel-first. Accepts some OTel data but the integration is less mature than Langfuse's native endpoint. | Partial — not first-class |

**Features relevant to this project:**

| Feature | Available (Self-Hosted)? | Relevance |
|---|---|---|
| LLM call tracing | Yes | Critical |
| Nested spans | Yes | Critical |
| Cost tracking | Yes | High |
| LLM-as-a-judge evaluations | Yes (stronger than Langfuse — hallucination, moderation, RAG metrics, custom scorers) | High |
| Automated prompt/tool optimization | Yes | Medium |
| Datasets and experiments | Yes | Medium |
| Production monitoring dashboards | Yes | Medium |

**Strengths:**
- Apache 2.0 — fully permissive, no caveats.
- Strongest evaluation capabilities among the three options: built-in hallucination detection, moderation, RAG assessment, custom LLM-as-a-judge scorers, and automated optimization.
- Large and growing community (~18.5k stars). Backed by Comet ML.
- Native LiteLLM callback.

**Weaknesses:**
- **ClickHouse + Redis + MySQL/PostgreSQL.** Even heavier infrastructure footprint than Langfuse. Four services (Opik server + ClickHouse + Redis + MySQL/PostgreSQL) vs. Langfuse's three.
- **Java/Kotlin server.** Introduces a JVM runtime into an otherwise Python-only stack. Higher memory baseline, different operational tooling.
- **OTel integration is not first-class.** Temporal and PydanticAI traces via OTel require more manual work than with Langfuse.
- **PydanticAI integration is indirect.** Documented via Logfire bridge but less mature than Langfuse's OTel path.

---

### Option C: MLflow (with LLM Tracing)

**License:** Apache 2.0. Linux Foundation project. Zero feature gates.

**Architecture:**
```
+-----------------+     +------------------+     +-------------------+
| Python Workers  |---->|  MLflow Server   |---->|   PostgreSQL      |
| (LiteLLM +      |     |  (Python/Flask)  |     |   (metadata)      |
|  PydanticAI)    |     +------------------+     +-------------------+
|                 |             |
|  - mlflow.trace |             v
|  - autolog()    |     +-------------------+
|  - callbacks    |     |   S3 / Local FS   |
+-----------------+     |   (artifacts)     |
                        +-------------------+
```

**Infrastructure required:** MLflow tracking server (Python/Flask) + PostgreSQL + artifact storage (S3/GCS/local filesystem).

**No ClickHouse. No Redis. No MySQL. Just PostgreSQL + object storage.**

**Integration details:**

| Component | How | Quality |
|---|---|---|
| LiteLLM | Native callback: `success_callback=["mlflow"]` in LiteLLM config. | Good — documented, maintained |
| PydanticAI | Native autolog: `mlflow.pydantic_ai.autolog()`. Captures agent steps, tool calls, model interactions automatically. Sync and async supported. | Excellent — first-class native integration, not an OTel bridge |
| Temporal | Via OpenTelemetry. MLflow accepts OTLP traces. Temporal's OTel interceptor exports to MLflow. | Good — OTel-compatible |
| OpenTelemetry | Full OTLP compatibility. Can export traces via OTLP and ingest OTLP spans. | Good |

**Features relevant to this project:**

| Feature | Available (Self-Hosted)? | Relevance |
|---|---|---|
| LLM call tracing (prompts, completions, tokens, cost, latency) | Yes | Critical |
| Nested spans (agent -> tool -> LLM call) | Yes | Critical |
| Cost tracking | Yes | High |
| LLM-as-a-judge evaluations | Yes (`mlflow.genai.evaluate()` with 20+ metrics via DeepEval/RAGAS) | High |
| Prompt engineering / comparison | Yes (side-by-side trace comparison) | Medium |
| Datasets and experiments | Yes (MLflow Experiments — the platform's original core feature) | Medium |
| Model registry | Yes | Low (not needed for this project, but available) |
| In-progress trace streaming | Yes (live view of traces during execution) | Medium |

**Strengths:**
- **PostgreSQL + S3 only.** No ClickHouse, no Redis, no additional databases. Aligns directly with ADR-003's single-database principle. The MLflow tracking server stores metadata in PostgreSQL and artifacts (trace data, evaluation results) in object storage. The same PostgreSQL instance used by Temporal and the application can host MLflow's metadata (in a separate schema).
- **Python server.** MLflow is a Python/Flask application — no Node.js, no JVM. Consistent with the Python-only stack in ADR-004. Same runtime, same monitoring, same dependency management.
- **Native PydanticAI integration.** `mlflow.pydantic_ai.autolog()` is a first-class, SDK-level integration — not an OTel bridge. Automatically captures agent steps, tool calls, and model interactions without manual annotation.
- **Native LiteLLM callback.** Same zero-code instrumentation as Langfuse and Opik.
- **Apache 2.0 + Linux Foundation.** The strongest open-source governance among the three options. No VC-driven relicensing risk. No feature gates.
- **Massive community.** ~20k+ stars, 900+ contributors. The most battle-tested platform of the three (originally released in 2018).
- **Experiment/evaluation framework.** `mlflow.genai.evaluate()` provides 20+ built-in metrics with DeepEval/RAGAS integration, custom scorers, and multi-turn conversation evaluation. Evaluation results are stored alongside traces, enabling "did this prompt change improve quality?" analysis.

**Weaknesses:**
- **LLM tracing is newer.** MLflow's core strength is ML experiment tracking (since 2018). LLM-specific tracing (`mlflow.tracing`) was added in MLflow 2.x/3.x (2024-2025). The UI is improving but is still more ML-oriented than Langfuse's purpose-built LLM debugging interface.
- **No dedicated prompt management.** Langfuse has a prompt versioning and deployment system. MLflow manages prompts as artifacts within experiments, which is functional but less specialized.
- **No annotation queues.** Langfuse supports human annotation workflows for reviewing LLM outputs. MLflow lacks this feature — human review would be handled by the application's own checkpoint system (which already exists in the pipeline).
- **OTel ingestion is less polished than Langfuse.** Langfuse's native OTel endpoint provides clean LLM-semantic span rendering. MLflow's OTel support works but the UI rendering of OTel-sourced traces is less refined.

---

## Detailed Comparison

### Infrastructure Footprint

| | Langfuse | Opik | MLflow |
|---|---|---|---|
| Server runtime | Node.js (Next.js) | Java/Kotlin (JVM) | Python (Flask) |
| Metadata database | PostgreSQL | MySQL or PostgreSQL | PostgreSQL |
| Trace/analytics store | **ClickHouse** | **ClickHouse** | **PostgreSQL** (same instance) |
| Cache | None | **Redis** | None |
| Artifact storage | None (traces in ClickHouse) | None | S3 / GCS / local filesystem |
| **Total new services** | **2** (Langfuse server + ClickHouse) | **3** (Opik server + ClickHouse + Redis) | **1** (MLflow server) |
| Can share existing PostgreSQL? | Yes (metadata only) | Yes (metadata only) | **Yes (metadata + traces)** |
| Docker Compose additions | 2 containers | 3-4 containers | 1 container |

**Winner: MLflow** — one additional service (Python Flask server), no new databases. ClickHouse is the single largest operational burden in both Langfuse and Opik, and MLflow eliminates it entirely.

### Integration Quality with Current Stack

| Integration | Langfuse | Opik | MLflow |
|---|---|---|---|
| LiteLLM | Native callback (excellent) | Native callback (good) | Native callback (good) |
| PydanticAI | OTel bridge (good) | Logfire/OTel bridge (adequate) | **Native autolog (excellent)** |
| Temporal OTel spans | Native OTel endpoint (excellent) | Partial OTel support (adequate) | OTel-compatible (good) |
| Combined stack integration | Very good | Adequate | **Best** |

**Winner: MLflow** — the only platform with native (non-OTel-bridge) PydanticAI integration. LiteLLM integration is equivalent across all three. Langfuse has a slight edge on Temporal OTel ingestion.

### LLM Debugging UI

| Capability | Langfuse | Opik | MLflow |
|---|---|---|---|
| Prompt/completion display | Excellent — purpose-built | Good | Good (improving) |
| Token usage visualization | Excellent | Good | Good |
| Cost dashboards | Excellent | Good | Good |
| Latency distribution | Excellent | Good | Good |
| Trace tree visualization | Excellent | Good | Good |
| Side-by-side comparison | Good | Good | Good |
| Live trace streaming | No | No | **Yes** |

**Winner: Langfuse** — its UI is purpose-built for LLM debugging and is the most polished. MLflow's in-progress trace streaming is a useful differentiator for long pipeline runs.

### Evaluation Capabilities

| Capability | Langfuse | Opik | MLflow |
|---|---|---|---|
| LLM-as-a-judge | Yes | **Yes (strongest)** | Yes |
| Built-in metrics | Moderate set | **Extensive** (hallucination, moderation, RAG) | **Extensive** (20+ via DeepEval/RAGAS) |
| Custom scorers | Yes | Yes | Yes |
| Datasets | Yes | Yes | **Yes (experiments — core feature)** |
| A/B prompt comparison | Yes | Yes | Yes |
| Automated optimization | No | **Yes** | No |
| Annotation queues (human review) | **Yes** | No | No |

**Winner: Tie (Opik/MLflow)** for automated evaluation. **Langfuse** for human annotation workflows (but the application already has its own human checkpoint system).

### Licensing and Governance

| | Langfuse | Opik | MLflow |
|---|---|---|---|
| License | MIT | Apache 2.0 | Apache 2.0 |
| Governance | VC-backed startup (YC W23) | VC-backed company (Comet ML) | **Linux Foundation** |
| Relicensing risk | Low (MIT) but company-controlled | Low (Apache 2.0) but company-controlled | **Lowest** (LF governance) |
| Feature gates | Enterprise security only | None | **None** |
| Long-term stability | Good (VC-funded, growing) | Good (VC-funded, growing) | **Excellent** (LF, 7+ years, 900+ contributors) |

**Winner: MLflow** — Linux Foundation governance provides the strongest long-term stability guarantee. No company can unilaterally relicense it.

---

## Summary Matrix

| Criterion | Weight | Langfuse | Opik | MLflow |
|---|---|---|---|---|
| Infrastructure simplicity | **Critical** | 2 new services + ClickHouse | 3 new services + ClickHouse + Redis | **1 new service, no new DBs** |
| LiteLLM integration | Critical | Excellent | Good | Good |
| PydanticAI integration | Critical | Good (OTel bridge) | Adequate (indirect) | **Excellent (native autolog)** |
| Temporal OTel integration | High | **Excellent** (native OTel endpoint) | Adequate | Good |
| LLM debugging UI | High | **Best** | Good | Good (improving) |
| Evaluation capabilities | High | Good | **Best** | Very good |
| License / governance | High | MIT / VC startup | Apache 2.0 / VC company | **Apache 2.0 / Linux Foundation** |
| Server runtime consistency | Medium | Node.js (foreign to Python stack) | JVM (foreign to Python stack) | **Python (native to stack)** |
| Community / maturity | Medium | ~24k stars, 3 years | ~18.5k stars, 2 years | **~20k+ stars, 7+ years** |
| Prompt management | Low | **Best** | Good | Basic |
| Annotation queues | Low | **Yes** | No | No |

---

## Decision

**Use MLflow (self-hosted) as the LLM observability platform.**

### Rationale

The deciding factors align with the architectural principles established in previous ADRs:

1. **Infrastructure simplicity (ADR-003 alignment).** MLflow is the only option that does not require ClickHouse. It stores metadata in PostgreSQL (the same instance already running for Temporal and application data, in a separate schema) and artifacts in object storage (S3/GCS, already specified in the architecture for audit log replication). Adding MLflow means adding one Python container — not a ClickHouse cluster, not a Redis instance, not a JVM or Node.js server.

2. **Native PydanticAI integration.** `mlflow.pydantic_ai.autolog()` is a first-class, SDK-level integration that automatically captures agent steps, tool calls, and model interactions. Langfuse and Opik both require an OTel bridge for PydanticAI, which adds configuration overhead and may lose agent-level semantics in the translation.

3. **Python-native server (ADR-004 alignment).** MLflow's tracking server is a Python/Flask application. The entire `regulatory-agent-kit` stack — Temporal workers, PydanticAI agents, FastAPI endpoints, and now the observability server — runs on a single runtime. One monitoring approach, one dependency management system, one team skill set.

4. **Linux Foundation governance.** For a tool used in regulated financial environments, long-term platform stability is a hard requirement. MLflow's LF governance means no single company can relicense it, abandon it, or gate features behind a paywall. This is the strongest continuity guarantee among the three options.

5. **LiteLLM integration parity.** All three platforms have native LiteLLM callbacks. This is not a differentiator.

### Acknowledged Trade-offs

- **Langfuse has a better LLM debugging UI.** MLflow's LLM tracing UI is functional and rapidly improving, but Langfuse's purpose-built interface (prompt diff view, token visualization, cost dashboards) is more polished today. For the `regulatory-agent-kit`, the primary observability consumer is the audit trail (stored in PostgreSQL per ADR-003), not an interactive debugging UI — the UI is a development convenience, not a compliance artifact.

- **Langfuse has better Temporal OTel ingestion.** Langfuse's native OTel endpoint renders OTel-sourced spans with better fidelity than MLflow. However, Temporal workflow observability is already handled by Temporal's own Web UI (workflow history, pending activities, signal tracking). The LLM observability platform needs to trace LLM and agent interactions, not duplicate Temporal's operational visibility.

- **Langfuse has annotation queues.** MLflow lacks built-in human annotation workflows. This is mitigated by the pipeline's own human-in-the-loop checkpoints (non-bypassable, cryptographically signed), which serve as the primary human review mechanism. A dedicated annotation queue in the observability tool is a nice-to-have, not a requirement.

- **MLflow's LLM features are newer.** MLflow has tracked ML experiments since 2018, but LLM-specific tracing was added in 2024-2025. Langfuse was built LLM-first. However, MLflow's LLM tracing has matured rapidly (in-progress streaming, PydanticAI autolog, DeepEval/RAGAS integration), and the pace of development shows no signs of slowing.

---

## Consequences

1. **Infrastructure:** Add one MLflow tracking server container to Docker Compose and Kubernetes deployments. Configure it to use the existing PostgreSQL instance (separate `mlflow` schema) and the existing object storage (S3/GCS) for artifact storage.

2. **LLM tracing:** Configure LiteLLM with `success_callback=["mlflow"]`. All LLM calls are automatically traced with zero per-call instrumentation.

3. **Agent tracing:** Add `mlflow.pydantic_ai.autolog()` at application startup. All PydanticAI agent executions are automatically traced with agent steps, tool calls, and model interactions.

4. **Temporal tracing:** Temporal workflow/activity spans are exported via OpenTelemetry to MLflow's OTLP endpoint, providing a unified trace view of orchestration + agent + LLM interactions.

5. **Evaluation:** Use `mlflow.genai.evaluate()` with custom scorers to assess agent output quality. Evaluation results are stored alongside traces in MLflow experiments.

6. **Operational metrics remain separate.** OpenTelemetry -> Prometheus -> Grafana handles operational metrics (pipeline latency, error rates, queue depths). MLflow handles LLM-specific observability (prompts, completions, token usage, cost, agent decisions). This separation is intentional — operational dashboards and LLM audit trails serve different audiences and have different retention requirements.

7. **ADR-004 update.** The `L19 — Observability SDK` section in ADR-004 should be updated to replace `langfuse` with `mlflow` as the LLM tracing platform. The OpenTelemetry SDK remains unchanged.

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| MLflow LLM tracing UI is less polished than Langfuse | MEDIUM | MLflow's UI is improving rapidly. For compliance purposes, the audit trail in PostgreSQL (ADR-003) is the authoritative record, not the UI. Custom Grafana dashboards can supplement MLflow's UI for specific views. |
| MLflow PydanticAI autolog does not yet support streaming | LOW | Streaming is a PydanticAI feature, not a pipeline requirement. Agent activities in Temporal are request/response, not streamed. |
| MLflow tracking server becomes a bottleneck | LOW | MLflow supports horizontal scaling (multiple tracking server replicas behind a load balancer). For this application's volume (hundreds to low thousands of traces per pipeline run), a single instance is sufficient. |
| Migration from MLflow if a better LLM-specific tool emerges | LOW | LLM traces are also captured in the application's own audit trail (PostgreSQL, ADR-003). MLflow is the visualization and analysis layer, not the system of record. Migrating to a different observability tool does not affect the audit trail. |

---

## References

- [MLflow LLM Tracing Documentation](https://mlflow.org/docs/latest/genai/tracing/)
- [MLflow PydanticAI Autolog](https://mlflow.org/docs/latest/tracing/integrations/pydantic_ai/)
- [MLflow LiteLLM Integration](https://docs.litellm.ai/docs/observability/mlflow)
- [MLflow GenAI Evaluate](https://mlflow.org/docs/latest/genai/eval/)
- [MLflow License (Apache 2.0)](https://github.com/mlflow/mlflow/blob/master/LICENSE.txt)
- [MLflow Linux Foundation Announcement](https://lfaidata.foundation/projects/mlflow/)
- [Langfuse Self-Hosting](https://langfuse.com/self-hosting)
- [Langfuse Open Source Strategy (June 2025)](https://langfuse.com/changelog/2025-06-04-open-sourcing-langfuse)
- [Opik Documentation](https://www.comet.com/docs/opik/)
- [Opik GitHub](https://github.com/comet-ml/opik)
- [`docs/architecture.md`](../architecture.md) — Framework architecture specification
- [ADR-003](003-database-selection.md) — PostgreSQL selection
- [ADR-004](004-python-stack.md) — Python stack selection
