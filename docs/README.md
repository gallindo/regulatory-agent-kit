# Documentation Guide

## Reading Order

The documentation is organized in layers from "why" to "how to deploy". Start from the top and drill down as needed for your role.

| # | Document | Purpose | Primary Audience |
|---|---|---|---|
| 1 | [`regulatory-agent-kit.md`](regulatory-agent-kit.md) | **Why** — Product requirements, market context, business strategy, roadmap | Engineering managers, product owners |
| 2 | [`architecture.md`](architecture.md) | **What** — System design, contracts, plugin schema, security boundaries | All technical roles |
| 3 | [`adr/`](adr/) | **Decisions** — Technology selections with full rationale and alternatives | Architects, senior engineers |
| 4 | [`sad.md`](sad.md) | **How (architecture)** — Quality attributes, design principles, C4 model, technology stack | Architects, senior engineers |
| 5 | [`hld.md`](hld.md) | **How (operations)** — Deployment topology, scaling model, HA, integration specs | Platform engineers, DevOps |
| 6 | [`lld.md`](lld.md) | **How (code)** — Class diagrams, algorithms, state machines, DDL, retry policies | Implementing engineers |
| 7 | [`data-model.md`](data-model.md) | **Data layer** — Tables, indexes, access control, partitioning, Elasticsearch indexes | Backend engineers, DBAs |
| 8 | [`infrastructure.md`](infrastructure.md) | **Deployment** — Docker, Kubernetes, AWS/GCP/Azure, CI/CD, Lite Mode | Platform engineers, SRE |

## Supplementary Documents

| Document | Purpose |
|---|---|
| [`cli-reference.md`](cli-reference.md) | All `rak` CLI commands, flags, and environment variables |
| [`plugin-template-guide.md`](plugin-template-guide.md) | Jinja2 template authoring for regulation plugins |
| [`operations/runbook.md`](operations/runbook.md) | Operational runbook for failure recovery and maintenance |

## Architecture Decision Records (ADRs)

| ADR | Decision | Status |
|---|---|---|
| [001](adr/001-agent-orchestration-framework.md) | LangGraph as orchestration framework | Superseded by ADR-002 |
| [002](adr/002-langgraph-vs-temporal-pydanticai.md) | Temporal + PydanticAI over LangGraph | Accepted |
| [003](adr/003-database-selection.md) | PostgreSQL 16+ as single database | Accepted |
| [004](adr/004-python-stack.md) | Python 3.12+, uv, Pydantic v2, Psycopg 3, FastAPI | Accepted |
| [005](adr/005-llm-observability-platform.md) | MLflow over Langfuse for LLM observability | Accepted |
| [006](adr/006-elasticsearch-selection.md) | Elasticsearch 8.x for regulatory knowledge base | Accepted |

## Canonical Sources (DRY)

To avoid drift between documents, each topic has one canonical source. Other documents reference it.

| Topic | Canonical Source | Referenced By |
|---|---|---|
| Plugin YAML schema | `architecture.md` Section 12 | `regulatory-agent-kit.md`, `lld.md` |
| Workflow state machine | `architecture.md` Section 4 | `regulatory-agent-kit.md`, `sad.md`, `hld.md` |
| Agent contracts | `architecture.md` Section 4.3 | `regulatory-agent-kit.md`, `sad.md` |
| Security boundaries | `architecture.md` Section 9 | `regulatory-agent-kit.md`, `sad.md` |
| Event schema & sources | `architecture.md` Section 5 | `sad.md` |
| Deployment options (detailed) | `infrastructure.md` | `architecture.md`, `regulatory-agent-kit.md`, `sad.md`, `hld.md` |
| Integration specs (detailed) | `hld.md` Section 6.2 | `architecture.md`, `sad.md`, `regulatory-agent-kit.md` |
| DB status vs Temporal phase | `lld.md` Section 4.1.1 | `data-model.md` |
