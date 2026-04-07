# ADR-001: Agent Orchestration Framework Selection

**Status:** Superseded by [ADR-002](002-langgraph-vs-temporal-pydanticai.md)
**Date:** 2026-03-27
**Decision Makers:** Engineering Team
**Context:** Selection of the multi-agent orchestration framework for regulatory-agent-kit

> **Why this was superseded:** ADR-001 selected LangGraph based on its native state machine, checkpointing, and fan-out capabilities. During implementation review, [ADR-002](002-langgraph-vs-temporal-pydanticai.md) conducted a deeper comparison between LangGraph and Temporal + PydanticAI, concluding that Temporal's event-sourced durability, distributed activity execution, and built-in retry policies provide stronger guarantees for production-scale pipeline runs (500+ repositories). This ADR is retained for historical context — the LangGraph evaluation remains valid, but Temporal was ultimately selected for its operational robustness.

---

## Context

`regulatory-agent-kit` is a production-grade, multi-agent AI pipeline that automates the detection, analysis, and remediation of regulatory compliance issues across large software codebases. The framework orchestrates four specialized agents (Analyzer, Refactor, TestGenerator, Reporter) through a stateful workflow with:

- **Non-bypassable human-in-the-loop checkpoints** (post-analysis and pre-merge)
- **Durable state persistence** to PostgreSQL for crash recovery and resume
- **Fan-out/fan-in parallelism** for processing hundreds of repositories concurrently
- **Deterministic, auditable state transitions** — every transition is traced and stored permanently
- **Cross-regulation conflict detection** requiring conditional branching logic
- **Cost estimation gates**, dead letter queues, rollback manifests, and repository-level advisory locks

The orchestration layer is the backbone of the system. It must support regulated-environment requirements: full observability, deterministic behavior, crash recovery, and human checkpoints that cannot be bypassed programmatically.

Three frameworks were evaluated: **LangGraph** (LangChain ecosystem), **CrewAI**, and **AutoGen** (Microsoft).

---

## Decision

**Use LangGraph (LangChain ecosystem) as the orchestration framework.**

---

## Options Considered

### Option 1: LangGraph (LangChain ecosystem)

LangGraph is a library for building stateful, multi-actor applications as directed graphs. It models workflows as a `StateGraph` where nodes are agents or functions and edges are explicit, conditional transitions. State is a typed object passed through the graph. It is part of the LangChain ecosystem but can be used independently.

**Strengths:**

| Capability | Detail |
|---|---|
| **Explicit state machine** | Workflow is a `StateGraph` with typed state, named nodes, and conditional edges. Every transition is deterministic and inspectable — critical for audit trails in regulated environments. |
| **Durable checkpointing** | First-class `langgraph-checkpoint-postgres` integration. Pipeline state survives process crashes. Enables `rak resume --run-id <id>` without re-processing completed repositories. |
| **Human-in-the-loop** | Native `interrupt_before` / `interrupt_after` primitives on any node. Checkpoints are graph-level constructs, not application-level hacks. The non-bypassable checkpoint requirement maps directly to LangGraph's interrupt model. |
| **Fan-out/fan-in** | Native `Send` API for dynamic parallelism. The Analyzer produces N repository analyses; N Refactor workers fan out, process independently, and fan back in. This maps directly to the horizontal scaling requirement. |
| **Conditional branching** | `add_conditional_edges` supports the complex routing needed for: cost approved vs. rejected, tests passing vs. failing (retry), human approved vs. rejected, error handling. |
| **Subgraph composition** | Each agent phase can be its own subgraph, enabling independent testing and versioning. The cross-regulation conflict detection engine can be a nested subgraph within the Analyzer. |
| **Tool isolation** | Agents bind to specific tool sets. The Analyzer gets read-only tools (Git clone, AST parse, search); the Refactor Agent gets write tools (Git branch, AST transform). This enforces the security boundary documented in Section 9 of the architecture. |
| **LangSmith/Langfuse integration** | Native callback system for tracing every LLM call, tool invocation, and state transition. Integrates with Langfuse (the project's chosen trace collector) via the `langfuse-langchain` callback handler. |
| **LiteLLM compatibility** | LangGraph agents use LangChain's `ChatLiteLLM` or raw LiteLLM clients. Full compatibility with the LLM Gateway architecture (model-agnostic, region-routed, rate-limited). |
| **Streaming** | Supports token-level and event-level streaming, useful for real-time progress reporting during long pipeline runs. |

**Weaknesses:**

- **API surface churn** — LangGraph is evolving rapidly. Breaking changes between minor versions are possible. Mitigated by version pinning and the `WorkflowEngine` abstraction layer documented in the architecture.
- **Learning curve** — Graph-based state machines require a different mental model than imperative orchestration. Engineers must understand state reducers, channels, and conditional edges.
- **LangChain dependency** — While LangGraph can be used standalone, practical usage pulls in LangChain Core for prompt templates, output parsers, and tool bindings. This adds dependency weight.

---

### Option 2: CrewAI

CrewAI is a high-level framework for orchestrating autonomous AI agents organized as "crews" with roles, goals, and task assignments. It uses a role-based metaphor where agents are defined by their persona and collaborate through delegation.

**Strengths:**

| Capability | Detail |
|---|---|
| **Rapid prototyping** | Defining agents with `role`, `goal`, `backstory` is intuitive. A basic crew can be built in under 50 lines. |
| **Built-in role patterns** | Pre-built patterns for sequential, hierarchical, and consensus-based crew execution. |
| **Tool integration** | Simple `@tool` decorator for custom tools. Built-in tools for web search, file I/O, etc. |
| **Memory** | Built-in short-term and long-term memory for agents using embeddings. |

**Weaknesses:**

| Requirement | Gap |
|---|---|
| **No explicit state machine** | CrewAI uses implicit task sequencing, not a formal state graph. There is no typed state object that flows between nodes. The audit trail cannot capture "transition from state X to state Y on condition Z" because no such construct exists. This is a **critical gap** for regulatory audit requirements. |
| **No durable checkpointing** | No built-in mechanism for persisting workflow state to PostgreSQL. If the process crashes mid-pipeline, there is no resume capability. For a system processing hundreds of repositories, this is unacceptable. |
| **Human-in-the-loop is bolted on** | CrewAI's `human_input=True` flag prompts for terminal input. There is no concept of a non-bypassable, cryptographically signed checkpoint. Implementing the checkpoint architecture would require building it entirely outside CrewAI's execution model. |
| **No fan-out/fan-in** | CrewAI executes tasks sequentially or hierarchically. There is no native `Send`-like primitive for "create N parallel workers from a dynamic list." Processing 500 repositories would require custom parallelism outside the framework. |
| **Limited conditional routing** | Task flow is linear or delegated. The complex state machine (cost gate -> analysis -> human review -> refactor -> test -> retry loop -> human review -> report) cannot be expressed natively. |
| **Opaque execution** | Agent delegation and task routing decisions are made by the framework internally (often via LLM-driven delegation). In a regulated environment, the orchestration layer itself must be deterministic, not LLM-driven. |
| **Observability** | No native integration with Langfuse or OpenTelemetry. Tracing requires custom instrumentation. |

**Assessment:** CrewAI is optimized for rapid prototyping of conversational agent teams. It lacks the infrastructure primitives (state machines, checkpoints, fan-out) required for a production compliance pipeline in a regulated environment.

---

### Option 3: AutoGen (Microsoft)

AutoGen is a framework for building multi-agent conversational systems. Agents communicate through message passing in conversation patterns (two-agent chat, group chat, nested chat). AutoGen 0.4 introduced `AgentChat` with a more structured API.

**Strengths:**

| Capability | Detail |
|---|---|
| **Flexible conversation patterns** | Supports two-agent, group chat, sequential chat, and nested chat patterns. Agents communicate via messages. |
| **Code execution** | Built-in sandboxed code execution (Docker, local). Useful for the TestGenerator's test execution requirement. |
| **Human proxy agent** | `UserProxyAgent` enables human participation in conversations. |
| **Ecosystem** | Microsoft backing, active development, growing community. |
| **Model agnosticism** | Supports multiple LLM providers out of the box. |

**Weaknesses:**

| Requirement | Gap |
|---|---|
| **Conversation-centric, not workflow-centric** | AutoGen models interactions as conversations between agents. The regulatory-agent-kit needs a workflow engine with explicit states, transitions, and conditions — not a chat. The pipeline is not a conversation; it is a state machine. |
| **No durable state persistence** | AutoGen does not persist conversation or workflow state to a database. No crash recovery or resume. The `GroupChat` state exists in memory only. |
| **Human-in-the-loop limitations** | `UserProxyAgent` participates in conversations but does not implement non-bypassable approval gates with cryptographic signatures. The checkpoint model (approve/reject with rationale and signature) does not map to AutoGen's message-passing paradigm. |
| **No native fan-out/fan-in** | Processing N repositories in parallel requires building custom orchestration outside AutoGen. `GroupChat` is designed for turn-taking conversations, not parallel work distribution. |
| **No conditional state transitions** | There are no typed state objects with conditional edges. Flow control is managed through conversation termination conditions and speaker selection, not explicit state machine transitions. |
| **Observability gap** | No native Langfuse integration. OpenTelemetry support is limited. Achieving the audit-first observability requirement would require significant custom instrumentation. |
| **Overhead for structured workflows** | AutoGen's power is in flexible, emergent agent conversations. For the regulatory-agent-kit's rigid, auditable pipeline, this flexibility becomes overhead — the framework would fight against the conversational paradigm rather than leverage it. |

**Assessment:** AutoGen excels at conversational multi-agent systems where agents negotiate, debate, and iterate through dialogue. The regulatory-agent-kit requires a deterministic workflow engine, not a conversation. The gaps in state persistence, checkpoints, and fan-out are structural, not feature gaps that will be filled in future releases.

---

## Comparison Matrix

| Requirement | Weight | LangGraph | CrewAI | AutoGen |
|---|---|---|---|---|
| Explicit state machine with typed state | **Critical** | Native `StateGraph` | Not supported | Not supported (conversation-based) |
| Durable PostgreSQL checkpointing | **Critical** | `langgraph-checkpoint-postgres` | Not supported | Not supported |
| Non-bypassable human-in-the-loop gates | **Critical** | `interrupt_before` / `interrupt_after` | Terminal input only | `UserProxyAgent` (conversational) |
| Fan-out/fan-in for N repositories | **Critical** | Native `Send` API | Not supported | Not supported |
| Conditional edge routing | **High** | `add_conditional_edges` | Limited (linear/hierarchical) | Speaker selection (LLM-driven) |
| Langfuse/OpenTelemetry integration | **High** | Native callback handlers | Custom instrumentation | Custom instrumentation |
| LiteLLM compatibility | **High** | Full (via ChatLiteLLM) | Partial | Partial |
| Tool isolation per agent | **High** | Per-node tool binding | Per-agent tools | Per-agent tools |
| Subgraph composition | **Medium** | Native subgraphs | Not supported | Nested chat (limited) |
| Streaming support | **Medium** | Token + event streaming | Limited | Limited |
| Learning curve | **Low** | Steep (graph concepts) | Gentle (role metaphor) | Moderate (conversation patterns) |
| Rapid prototyping speed | **Low** | Moderate | Fast | Moderate |

---

## Decision Rationale

LangGraph is selected because it is the **only framework among the three that natively provides all four critical requirements**:

1. **Explicit state machine** — The pipeline's states (IDLE, COST_ESTIMATION, ANALYZING, IMPACT_REVIEW, REFACTORING, TESTING, MERGE_REVIEW, REPORTING, COMPLETE, ERROR) map 1:1 to LangGraph `StateGraph` nodes.

2. **Durable checkpointing** — `langgraph-checkpoint-postgres` provides crash recovery and resume without custom implementation. This is non-negotiable for a system that processes hundreds of repositories in a single pipeline run.

3. **Non-bypassable human checkpoints** — `interrupt_before`/`interrupt_after` are graph-level primitives, not application-level hacks. The approval checkpoint cannot be accidentally bypassed by a code change because it is enforced by the graph execution engine itself.

4. **Fan-out/fan-in** — The `Send` API enables dynamic parallelism: Analyzer produces N analyses, N Refactor workers execute concurrently. This maps directly to the horizontal scaling architecture (Kubernetes Jobs or Temporal activities).

CrewAI and AutoGen would require building these four capabilities from scratch outside the framework, effectively reducing them to LLM wrappers while the actual orchestration lives in custom code. At that point, the framework provides negative value — it adds abstraction and dependency without solving the hard problems.

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| LangGraph API instability | HIGH | Version pinning with hash verification. `WorkflowEngine` abstraction wraps LangGraph, limiting blast radius of API changes. Integration test suite validates behavior across upgrades. |
| LangChain ecosystem dependency weight | MEDIUM | Use LangGraph with minimal LangChain Core imports. Avoid LangChain's higher-level chains and retrievers. Use LiteLLM directly for LLM calls where LangChain adds no value. |
| Vendor lock-in to LangChain ecosystem | MEDIUM | The `WorkflowEngine` abstraction documented in `framework-spec.md` (Section 10) provides a migration path. If a superior framework emerges, only the `WorkflowEngine` implementation changes; agents and tools are unaffected. |
| LangGraph learning curve for contributors | LOW | Documented patterns, graph visualization tools (`langgraph-studio`), and a contributor guide with worked examples lower the barrier. |

---

## Consequences

- The orchestration layer will be implemented as a LangGraph `StateGraph` with `langgraph-checkpoint-postgres` for durable state.
- All agent phases (Analyzer, Refactor, TestGenerator, Reporter) will be LangGraph nodes with explicitly typed input/output state contracts.
- Human checkpoints will use LangGraph `interrupt_before` on the IMPACT_REVIEW and MERGE_REVIEW nodes.
- Horizontal scaling will use LangGraph `Send` for fan-out and a coordinator node for fan-in.
- A `WorkflowEngine` abstraction will wrap LangGraph to limit blast radius of future API changes and preserve the option to migrate if needed.
- Langfuse tracing will use the `langfuse-langchain` callback handler, integrated at the graph execution level.
- LiteLLM will be used as the LLM gateway, accessed via LangChain's `ChatLiteLLM` wrapper or directly where appropriate.

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph Checkpoint PostgreSQL](https://langchain-ai.github.io/langgraph/reference/checkpoints/#postgresql)
- [CrewAI Documentation](https://docs.crewai.com/)
- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [`docs/framework-spec.md`](../framework-spec.md) — Framework architecture specification
- [`docs/prd.md`](../prd.md) — Full product requirements document
