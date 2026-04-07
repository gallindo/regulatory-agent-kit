# ADR-002: LangGraph vs Temporal + PydanticAI

**Status:** Accepted
**Date:** 2026-03-27
**Decision Makers:** Engineering Team
**Supersedes:** Refines [ADR-001](001-agent-orchestration-framework.md) (which selected LangGraph over CrewAI and AutoGen)

---

## Context

[ADR-001](001-agent-orchestration-framework.md) selected LangGraph as the orchestration framework. During review, a concern was raised about LangGraph's licensing model. Investigation confirmed that the **core `langgraph` library is MIT-licensed and free**; only LangGraph Platform/Cloud (managed hosting, assistants API, cron jobs) is a paid commercial product. However, the review surfaced a legitimate architectural question: should the project use an AI-specific graph framework (LangGraph) or a general-purpose durable workflow engine combined with a dedicated agent framework (Temporal + PydanticAI)?

This ADR compares these two approaches in depth against the specific requirements of `regulatory-agent-kit`.

### Requirements Recap

The orchestration layer must support:

| ID | Requirement | Source |
|---|---|---|
| R1 | Explicit stateful workflow with defined states (IDLE, COST_ESTIMATION, ANALYZING, IMPACT_REVIEW, REFACTORING, TESTING, MERGE_REVIEW, REPORTING, COMPLETE, ERROR) | `framework-spec.md` SS4.1 |
| R2 | Durable state persistence to PostgreSQL with crash recovery and `rak resume --run-id` | `framework-spec.md` SS4.2 |
| R3 | Non-bypassable human-in-the-loop checkpoints with cryptographic signatures at two gates (post-analysis, pre-merge) | `framework-spec.md` SS4.2 |
| R4 | Fan-out/fan-in parallelism for processing N repositories concurrently | `framework-spec.md` SS4.4 |
| R5 | Conditional routing (cost approved/rejected, tests pass/fail with retry, human approve/reject/modify) | `framework-spec.md` SS4.1 |
| R6 | Per-repository progress tracking and repository-level locking | `framework-spec.md` SS4.2 |
| R7 | Dead letter queue for failed repositories with selective retry | `framework-spec.md` SS4.2 |
| R8 | Rollback manifests recording all branches, PRs, commits | `framework-spec.md` SS4.2 |
| R9 | Full observability via Langfuse (LLM traces) and OpenTelemetry (operational metrics) | `framework-spec.md` SS7 |
| R10 | LiteLLM gateway integration for model-agnostic LLM access | `framework-spec.md` SS6 |
| R11 | Tool isolation per agent (Analyzer = read-only; Refactor = read-write) | `framework-spec.md` SS9 |
| R12 | Idempotent operations with deterministic branch naming | `framework-spec.md` SS4.2 |

---

## Options

### Option A: LangGraph

**Architecture:** Single Python process (or Kubernetes-deployed workers) running a LangGraph `StateGraph`. Agents are graph nodes. State flows through typed channels. Checkpoints are persisted to PostgreSQL via `langgraph-checkpoint-postgres`.

```
+----------------------------------------------+
|              Python Process                  |
|                                              |
|  +----------------------------------------+  |
|  |         LangGraph StateGraph           |  |
|  |                                        |  |
|  |  [Analyzer] --> [HiL] --> [Refactor]   |  |
|  |       |                       |        |  |
|  |       v                       v        |  |
|  |   (Send xN)             (Send xN)     |  |
|  |       |                       |        |  |
|  |       v                       v        |  |
|  |  [TestGen] --> [HiL] --> [Reporter]    |  |
|  +----------------+-----------------------+  |
|                   |                          |
|    +--------------v--------------+           |
|    |  langgraph-checkpoint       |           |
|    |     (PostgreSQL)            |           |
|    +-----------------------------+           |
|                                              |
|    +---------+  +----------+  +----------+   |
|    | LiteLLM |  | Langfuse |  |  Tools   |   |
|    +---------+  +----------+  +----------+   |
+----------------------------------------------+
```

**Licensing:** MIT (core library). LangGraph Platform/Cloud is paid but not required.

**Key components:**
- `langgraph` — state graph engine, conditional edges, interrupts, Send API
- `langgraph-checkpoint-postgres` — durable checkpoint persistence
- `langchain-core` — prompt templates, output parsers, tool abstractions
- `langfuse-langchain` — callback handler for LLM tracing
- `litellm` — model-agnostic LLM gateway

---

### Option B: Temporal + PydanticAI

**Architecture:** Temporal server (Go binary) manages workflow durability, scheduling, retries, and fan-out. Python workers execute workflow and activity code. PydanticAI handles agent logic, LLM interactions, structured outputs, and tool calling within Temporal activities.

```
+-----------------------------------+
|        Temporal Server (Go)       |
|   +---------------------------+   |
|   |   Workflow Engine         |   |
|   |   Event History (durable) |   |
|   |   Task Queues             |   |
|   |   Timers & Retries        |   |
|   +-------------+-------------+   |
|                 |                  |
|   +-------------v-------------+   |
|   |   PostgreSQL / Cassandra  |   |
|   +---------------------------+   |
+----------------+------------------+
                 | gRPC
+----------------v------------------+
|       Python Worker Process(es)   |
|                                   |
|  +-----------------------------+  |
|  |    Temporal Workflows       |  |
|  |    (state machine in code)  |  |
|  +--------------+--------------+  |
|                 |                 |
|  +--------------v--------------+  |
|  |    Temporal Activities      |  |
|  |  +-----------------------+  |  |
|  |  |   PydanticAI Agents   |  |  |
|  |  |   (Analyzer, Refactor |  |  |
|  |  |    TestGen, Reporter) |  |  |
|  |  +-----------------------+  |  |
|  +-----------------------------+  |
|                                   |
|  +---------+  +----------+       |
|  | LiteLLM |  | Logfire / |       |
|  |         |  | Langfuse  |       |
|  +---------+  +----------+       |
+-----------------------------------+
```

**Licensing:** Temporal server and Python SDK are MIT. PydanticAI is MIT. Temporal Cloud is paid but not required (self-hosted is fully functional).

**Key components:**
- `temporalio` — Python SDK for defining workflows and activities
- Temporal server — self-hosted Go binary (Docker image available)
- `pydantic-ai` — agent framework with typed outputs, tool calling, dependency injection
- `pydantic-ai[logfire]` — OpenTelemetry-based observability via Pydantic Logfire
- `litellm` — model-agnostic LLM gateway (PydanticAI supports LiteLLM as a model provider)

---

## Detailed Comparison

### R1 — Stateful Workflow Definition

**LangGraph:**
The pipeline is declared as a `StateGraph` with named nodes and edges. The state machine is a first-class, inspectable object. States map to nodes; transitions map to edges (including conditional edges). The graph can be visualized, serialized, and tested structurally.

```python
# Pseudocode — LangGraph
graph = StateGraph(PipelineState)
graph.add_node("analyzer", analyzer_agent)
graph.add_node("impact_review", human_checkpoint)
graph.add_node("refactor", refactor_agent)
graph.add_node("testing", test_agent)
graph.add_node("merge_review", human_checkpoint)
graph.add_node("reporter", reporter_agent)

graph.add_edge("analyzer", "impact_review")
graph.add_conditional_edges("impact_review", route_review)  # approved -> refactor, rejected -> end
graph.add_edge("refactor", "testing")
graph.add_conditional_edges("testing", route_tests)          # pass -> merge_review, fail -> refactor
graph.add_edge("merge_review", "reporter")
```

**Temporal + PydanticAI:**
The workflow is imperative Python code with durable execution guarantees. There is no graph object — the state machine is implicit in the control flow. This is more natural for Python developers but the workflow structure is not inspectable or visualizable as a graph without additional tooling.

```python
# Pseudocode — Temporal workflow
@workflow.defn
class CompliancePipeline:
    @workflow.run
    async def run(self, input: PipelineInput) -> PipelineResult:
        impact_map = await workflow.execute_activity(analyze, input)

        approved = await workflow.wait_condition(lambda: self.review_decision is not None)
        if not self.review_decision.approved:
            return PipelineResult(status="rejected")

        changes = await workflow.execute_activity(refactor, impact_map)
        test_result = await workflow.execute_activity(run_tests, changes)

        if not test_result.passed:
            # retry loop
            ...

        await workflow.wait_condition(lambda: self.merge_decision is not None)
        return await workflow.execute_activity(report, changes)
```

**Verdict:** LangGraph provides a declarative, inspectable graph. Temporal provides imperative, durable code. For auditability, the LangGraph model is stronger — you can export the graph topology and prove which transitions are possible. Temporal's imperative model is more flexible but the workflow structure is only visible by reading the code. **Edge: LangGraph.**

---

### R2 — Durable State Persistence & Crash Recovery

**LangGraph:**
`langgraph-checkpoint-postgres` serializes the full graph state at each superstep. On crash recovery, the graph resumes from the last checkpoint. State includes all channel values (typed Python objects serialized via JSON or custom serializers). The checkpoint model is tied to LangGraph's execution model — it checkpoints between graph supersteps, not at arbitrary points.

Recovery: `rak resume --run-id <id>` loads the checkpoint and re-enters the graph at the interrupted node.

**Note:** LangGraph's default serialization uses JSON. Custom serializers can be configured, but care must be taken to avoid unsafe deserialization formats in production (see `framework-spec.md` SS9 — Security Architecture).

**Temporal + PydanticAI:**
Temporal uses **event sourcing** — every workflow action (activity start, activity completion, signal received, timer fired) is recorded as an event in the workflow history, persisted to PostgreSQL. On crash recovery, the workflow function is **replayed** from the event history, fast-forwarding through completed activities. This is fundamentally more robust than checkpoint-based persistence:

- No serialization format concerns (events are the source of truth, not serialized state)
- Workflow replay is deterministic by construction
- History is append-only and immutable — a natural audit log
- Supports workflows running for days, weeks, or months without state size concerns
- Built-in configurable retention policies for completed workflow histories

Recovery: Temporal automatically recovers running workflows on server restart. No explicit resume command needed — workflows simply continue where they left off.

**Verdict:** Temporal's event-sourced durability is architecturally superior to LangGraph's checkpoint-based model. It provides stronger guarantees, immutable history, and automatic recovery. For a system processing hundreds of repositories over hours or days, this is a significant advantage. **Edge: Temporal.**

---

### R3 — Non-Bypassable Human-in-the-Loop

**LangGraph:**
`interrupt_before` / `interrupt_after` are graph-level primitives. When execution reaches an interrupt node, the graph checkpoints and pauses. Execution only resumes when the application explicitly calls `graph.invoke` with the checkpoint ID and human input. The non-bypassable property comes from the graph topology — the interrupt node is structurally between the preceding and following nodes, so there is no code path that skips it.

Cryptographic signing of approvals is application-level — LangGraph provides the pause/resume mechanism, the application adds signature verification.

**Temporal + PydanticAI:**
Workflows block on `workflow.wait_condition()` or `workflow.execute_activity()` that waits for a Temporal Signal. Signals are sent via the Temporal API (CLI, SDK, or HTTP). The workflow is durably paused — it cannot proceed without the signal. The non-bypassable property comes from the workflow code: the `await` on the signal cannot be skipped because Temporal replays the workflow deterministically.

Temporal also provides **workflow visibility** — you can query which workflows are waiting for approval, for how long, and who approved them. This maps well to the compliance dashboard use case.

Cryptographic signing: same as LangGraph — application-level.

**Verdict:** Both provide robust human gates. Temporal adds built-in workflow visibility (which workflows are waiting, for how long) and the durability guarantee is stronger (event-sourced vs. checkpointed). LangGraph's graph-structural guarantee is more inspectable. **Slight edge: Temporal** for operational visibility.

---

### R4 — Fan-Out/Fan-In Parallelism

**LangGraph:**
The `Send` API allows a node to dynamically create N parallel branches. Each branch executes independently and results are aggregated by a downstream node. This is elegant but runs within a single Python process — true horizontal scaling requires external coordination (e.g., Kubernetes Jobs pulling from a work queue, which is outside LangGraph's scope).

**Temporal + PydanticAI:**
Fan-out is achieved via child workflows or `asyncio.gather()` on activity futures. Temporal activities can run on **different worker processes** on **different machines** — horizontal scaling is native. The Temporal server handles task routing, load balancing, retry on worker failure, and activity-level timeouts.

```python
# Temporal fan-out pseudocode
results = await asyncio.gather(*[
    workflow.execute_activity(
        refactor_repo, repo,
        start_to_close_timeout=timedelta(minutes=30),
        retry_policy=RetryPolicy(maximum_attempts=3)
    )
    for repo in repositories
])
```

Each `refactor_repo` activity can execute on a different worker machine, with per-activity timeouts and retries managed by Temporal.

**Verdict:** Temporal's fan-out is production-grade distributed computing. LangGraph's `Send` is in-process parallelism. For processing 500+ repositories, Temporal's distributed activity execution is a clear advantage. **Edge: Temporal.**

---

### R5 — Conditional Routing

**LangGraph:**
`add_conditional_edges` with a routing function. The routing function inspects the state and returns the next node name. Declarative, inspectable, and testable — you can unit test routing functions independently.

**Temporal + PydanticAI:**
Standard Python `if/elif/else` in workflow code. Equally testable but not independently inspectable as graph topology.

**Verdict:** Functionally equivalent. LangGraph's declarative model is more auditable. **Slight edge: LangGraph.**

---

### R6 — Per-Repository Progress Tracking & Locking

**LangGraph:**
Application-level concern. The graph state can include a repository status map, but advisory locks and progress tracking must be implemented in application code against PostgreSQL.

**Temporal + PydanticAI:**
Temporal provides **workflow-level identity** — each repository can be a child workflow with a deterministic ID (e.g., `compliance/{regulation_id}/{repo_id}`). Temporal enforces **workflow ID uniqueness** — starting a duplicate workflow ID rejects or terminates the prior run, providing natural repository-level locking without advisory locks. Workflow status is queryable via the Temporal API.

**Verdict:** Temporal's workflow ID uniqueness is a built-in solution for repository-level locking. LangGraph requires custom PostgreSQL advisory locks. **Edge: Temporal.**

---

### R7 — Dead Letter Queue & Selective Retry

**LangGraph:**
Application-level concern. Failed repository analyses must be tracked in the graph state or an external store. Selective retry requires custom logic.

**Temporal + PydanticAI:**
Temporal has built-in retry policies per activity (configurable attempts, backoff, non-retryable error types). Failed activities are automatically retried per policy. For dead-letter scenarios, failed child workflows can be listed via the Temporal API (`temporal workflow list --query "ExecutionStatus = 'Failed'"`) and re-signaled or restarted.

**Verdict:** Temporal's retry and failure management is first-class. **Edge: Temporal.**

---

### R8 — Rollback Manifests

**LangGraph:**
Application-level concern. The Reporter agent must construct the rollback manifest.

**Temporal + PydanticAI:**
Application-level concern. Same — the Reporter activity constructs the manifest. However, Temporal's event history provides a natural audit trail of every activity that executed, making manifest reconstruction possible from the history itself.

**Verdict:** Comparable. Temporal's event history is a bonus. **Slight edge: Temporal.**

---

### R9 — Observability (Langfuse + OpenTelemetry)

**LangGraph:**
Native integration with Langfuse via `langfuse-langchain` callback handler. Every LLM call, tool invocation, and chain execution is traced automatically. This is the strongest observability story for LLM-specific tracing. OpenTelemetry for operational metrics requires additional setup.

**Temporal + PydanticAI:**
Temporal has native OpenTelemetry support for workflow and activity tracing — every workflow start, activity execution, signal, and timer is traced. PydanticAI integrates with Pydantic Logfire (OpenTelemetry-based) for LLM call tracing. Langfuse integration requires either the OpenTelemetry exporter path or a custom integration within PydanticAI activities.

The two-layer observability is actually a natural fit: Temporal traces the workflow orchestration (operational), PydanticAI/Logfire traces the LLM interactions (AI-specific). But integrating both into a unified view requires configuration work.

**Verdict:** LangGraph has a simpler, more unified observability story with Langfuse out of the box. Temporal + PydanticAI provides stronger operational observability but requires more integration work for LLM-specific tracing. **Edge: LangGraph** for Langfuse-first environments. **Edge: Temporal** for OpenTelemetry-first environments.

---

### R10 — LiteLLM Gateway Integration

**LangGraph:**
Uses LangChain's `ChatLiteLLM` wrapper or LiteLLM directly. Seamless.

**Temporal + PydanticAI:**
PydanticAI supports LiteLLM as a model backend. Activities call PydanticAI agents that use LiteLLM. Equally seamless.

**Verdict:** **Tie.** Both integrate cleanly with LiteLLM.

---

### R11 — Tool Isolation Per Agent

**LangGraph:**
Each node in the graph binds to a specific set of tools. The Analyzer node gets `[git_clone, ast_parse, search]` (read-only). The Refactor node gets `[git_branch, ast_transform, git_commit]` (read-write). Tool binding is structural — the node definition determines which tools are available.

**Temporal + PydanticAI:**
Each PydanticAI agent is instantiated with its own tool set via dependency injection. Tool isolation is at the agent definition level, which is structurally identical. Activities provide an additional isolation boundary — each activity can run in a separate process with different permissions.

**Verdict:** **Tie.** Both support clean tool isolation.

---

### R12 — Idempotent Operations

**LangGraph:**
Application-level concern. Deterministic branch naming (`rak/{regulation_id}/{rule_id}`) is implemented in agent code.

**Temporal + PydanticAI:**
Temporal workflows are inherently idempotent — starting a workflow with the same ID is a no-op if the workflow is already running. Activity retry uses automatic deduplication. This provides infrastructure-level idempotency on top of application-level patterns.

**Verdict:** **Edge: Temporal** — idempotency is built into the execution model.

---

## Non-Functional Comparison

### Operational Complexity

| Aspect | LangGraph | Temporal + PydanticAI |
|---|---|---|
| **Infrastructure required** | Python process + PostgreSQL | Temporal server (Go) + PostgreSQL + Python workers |
| **Minimum deployment** | 1 process | 3 processes (server, worker, PostgreSQL) |
| **Docker Compose footprint** | App + PostgreSQL | App + Temporal server + Temporal UI + PostgreSQL |
| **Kubernetes deployment** | Standard Python deployment | Temporal Helm chart (temporal-server, temporal-history, temporal-matching, temporal-frontend, temporal-worker) + app workers |
| **Scaling model** | Vertical (single process) or custom horizontal | Horizontal (add worker replicas, Temporal handles routing) |
| **Operational expertise** | Python | Python + Temporal server administration |

**Verdict:** LangGraph is significantly simpler to deploy and operate. Temporal adds 3-5 additional services. **Edge: LangGraph.**

---

### Dependency Weight

| | LangGraph | Temporal + PydanticAI |
|---|---|---|
| **Core Python deps** | `langgraph`, `langchain-core`, `langgraph-checkpoint-postgres` | `temporalio`, `pydantic-ai` |
| **Transitive deps** | LangChain ecosystem (substantial) | Temporal SDK + Pydantic ecosystem (moderate) |
| **External services** | PostgreSQL | Temporal server (Go binary) + PostgreSQL |
| **Total `pip install` size** | ~150-200 MB (LangChain ecosystem) | ~80-120 MB (leaner) |

**Verdict:** Temporal + PydanticAI has fewer Python dependencies but requires an external Go service. **Trade-off** — lighter Python footprint vs. heavier infrastructure.

---

### Team Learning Curve

| | LangGraph | Temporal + PydanticAI |
|---|---|---|
| **Core concept** | Directed graphs, state channels, reducers | Durable functions, event sourcing, replay |
| **Paradigm** | Declarative graph | Imperative workflow code |
| **Debugging** | Graph visualization (LangGraph Studio) | Temporal Web UI (workflow history, pending activities) |
| **AI-specific patterns** | Extensive documentation, tutorials | PydanticAI docs good; combining with Temporal is less documented |
| **Community resources** | Large (LangChain ecosystem) | Large (Temporal) + growing (PydanticAI) but combined usage is niche |

**Verdict:** LangGraph has more AI-specific documentation and tutorials. Temporal + PydanticAI requires understanding two systems and their integration, with fewer combined-usage examples. **Edge: LangGraph.**

---

### Long-Term Maintenance Risk

| Risk | LangGraph | Temporal + PydanticAI |
|---|---|---|
| **API stability** | Moderate — LangGraph is evolving rapidly. Breaking changes between minor versions have occurred. The `WorkflowEngine` abstraction mitigates this. | High — Temporal has strong backward compatibility commitments. Workflow versioning is a first-class concern. PydanticAI follows Pydantic's stability practices. |
| **Vendor risk** | LangChain Inc is a VC-funded startup. If the company pivots or fails, the MIT-licensed library continues but active development may stop. | Temporal Technologies is well-funded ($200M+ raised). The server is MIT-licensed. PydanticAI is backed by Pydantic (Samuel Colvin), also well-funded. |
| **Migration path** | `WorkflowEngine` abstraction allows swapping the graph engine. | Temporal workflows are portable across infrastructure. PydanticAI agents are framework-independent. |
| **Lock-in surface** | LangChain ecosystem (prompt templates, output parsers, tool bindings, callbacks). Replacing LangGraph means also replacing LangChain patterns. | Temporal SDK (workflow/activity decorators). PydanticAI (agent definitions). These are separable — you can replace one without the other. |

**Verdict:** Temporal + PydanticAI has a more stable API trajectory and lower lock-in risk. **Edge: Temporal + PydanticAI.**

---

## Summary Matrix

| Requirement | Weight | LangGraph | Temporal + PydanticAI | Winner |
|---|---|---|---|---|
| R1 — Stateful workflow | Critical | Declarative graph | Imperative durable code | LangGraph |
| R2 — Durable persistence | Critical | Checkpoint-based | Event-sourced | **Temporal** |
| R3 — Human-in-the-loop | Critical | Graph interrupts | Workflow signals | Temporal (slight) |
| R4 — Fan-out/fan-in | Critical | In-process Send | Distributed activities | **Temporal** |
| R5 — Conditional routing | High | Conditional edges | Python if/else | LangGraph (slight) |
| R6 — Repo tracking/locking | High | Custom (advisory locks) | Built-in (workflow ID) | **Temporal** |
| R7 — Dead letter / retry | High | Custom | Built-in retry policies | **Temporal** |
| R8 — Rollback manifests | Medium | Custom | Custom (+ event history) | Temporal (slight) |
| R9 — Observability | High | Langfuse native | OTel native, Langfuse needs work | Context-dependent |
| R10 — LiteLLM integration | High | Native | Native | Tie |
| R11 — Tool isolation | High | Per-node binding | Per-agent DI | Tie |
| R12 — Idempotent ops | Medium | Custom | Built-in (workflow ID) | **Temporal** |
| Operational complexity | High | Low (1 process + PG) | High (server + workers + PG) | LangGraph |
| Learning curve | Medium | AI-specific docs | Two-system integration | LangGraph |
| API stability / lock-in | High | Moderate risk | Lower risk | **Temporal** |

**Score by critical/high requirements:** Temporal + PydanticAI wins or ties on 8 of 12 requirements. LangGraph wins on 2 (stateful workflow declaration, conditional routing) and ties on 2.

---

## Decision

**Use Temporal + PydanticAI** as the orchestration and agent framework for `regulatory-agent-kit`.

### Rationale

Temporal + PydanticAI wins or ties on 8 of 12 functional requirements. The decisive factors are:

1. **Event-sourced durability** (R2) — Temporal's replay-based persistence is architecturally superior to checkpoint serialization for a system that processes hundreds of repositories over hours or days. Automatic recovery on server restart eliminates the need for custom `rak resume` logic.

2. **Distributed fan-out** (R4) — Temporal activities execute on separate worker processes across machines. Scaling from 10 to 500 repositories requires adding worker replicas, not rearchitecting the application. LangGraph's `Send` is in-process only.

3. **Built-in infrastructure primitives** (R6, R7, R12) — Repository-level locking (workflow ID uniqueness), retry policies (per-activity configuration), and idempotency (deduplication) are provided by Temporal out of the box. With LangGraph, all three require custom PostgreSQL-backed implementations.

4. **API stability and lower lock-in risk** — Temporal has strong backward compatibility commitments and workflow versioning as a first-class concern. The Temporal SDK and PydanticAI are separable — either can be replaced independently.

LangGraph's advantages (declarative graph inspection, simpler deployment, native Langfuse integration) are acknowledged but do not outweigh Temporal's strengths for this project's production requirements.

### Accepted trade-offs

- **Higher operational complexity** — The team commits to running and operating a Temporal server (self-hosted via Docker or Kubernetes Helm chart) alongside PostgreSQL and Python workers.
- **Langfuse integration requires work** — LLM tracing via Langfuse will be integrated through OpenTelemetry export or a custom callback within PydanticAI activities, rather than a drop-in callback handler.
- **Two-system learning curve** — Engineers must understand both Temporal (workflows, activities, signals, replay) and PydanticAI (agents, tools, dependency injection).

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph License (MIT)](https://github.com/langchain-ai/langgraph/blob/main/LICENSE)
- [Temporal Documentation](https://docs.temporal.io/)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [Temporal License (MIT)](https://github.com/temporalio/temporal/blob/main/LICENSE)
- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [PydanticAI License (MIT)](https://github.com/pydantic/pydantic-ai/blob/main/LICENSE)
- [PydanticAI — Durability recommendation](https://ai.pydantic.dev/multi-agent-applications/#nested-agent-calls)
- [`docs/framework-spec.md`](../framework-spec.md) — Framework architecture specification
- [ADR-001](001-agent-orchestration-framework.md) — Initial framework selection (LangGraph vs CrewAI vs AutoGen)

---

## Key Terms

| Term | Definition |
|---|---|
| **Activity** | A Temporal unit of work — a function call that can be retried, timed out, and executed on a separate worker machine |
| **Event Sourcing** | A pattern where all state changes are stored as immutable events; on recovery, the workflow is deterministically replayed from the event log |
| **Signal** | A durable message sent to a running Temporal workflow to mutate its state (e.g., delivering an approval decision) |
| **Workflow Replay** | Deterministic re-execution of workflow code using recorded event history as state — enables crash recovery without data loss |
| **Fan-out/Fan-in** | Dynamic parallelism where one task creates N parallel branches (fan-out) that reconverge into a single result (fan-in) |

For a full glossary, see [`glossary.md`](../glossary.md).
