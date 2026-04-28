# Documentation Guide

`regulatory-agent-kit` is an open-source Python framework for building multi-agent AI pipelines that automate regulatory compliance across software codebases. Unfamiliar terms? See the [`glossary.md`](glossary.md).

## I Am a...

| Your role | Start here | Then read |
|---|---|---|
| **New user evaluating the tool** | [`getting-started.md`](getting-started.md) | [`cli-reference.md`](cli-reference.md) |
| **Plugin author** | [`plugin-template-guide.md`](plugin-template-guide.md) | [`framework-spec.md` Sections 3, 12](framework-spec.md) |
| **Backend engineer** | [`software-architecture.md`](software-architecture.md) → [`implementation-design.md`](implementation-design.md) | [`data-model.md`](data-model.md) |
| **Platform / SRE engineer** | [`infrastructure.md`](infrastructure.md) → [`system-design.md`](system-design.md) | [`operations/runbook.md`](operations/runbook.md) |
| **Architect** | [`prd.md`](prd.md) → [`framework-spec.md`](framework-spec.md) | [`adr/`](adr/) |
| **Contributor** | [`local-development.md`](local-development.md) | [`software-architecture.md` Section 16](software-architecture.md) (Project Structure) |

## Quick Paths

| Your goal | Reading path |
|---|---|
| **Evaluate the tool (5 min)** | [`getting-started.md`](getting-started.md) |
| **Understand the architecture** | [`getting-started.md`](getting-started.md) -> [`framework-spec.md`](framework-spec.md) |
| **Build a regulation plugin** | [`framework-spec.md` SS3, SS12](framework-spec.md) -> [`plugin-template-guide.md`](plugin-template-guide.md) |
| **Deploy to production** | [`system-design.md`](system-design.md) -> [`infrastructure.md`](infrastructure.md) -> [`operations/runbook.md`](operations/runbook.md) |
| **Implement features** | [`framework-spec.md`](framework-spec.md) -> [`software-architecture.md`](software-architecture.md) -> [`implementation-design.md`](implementation-design.md) -> [`data-model.md`](data-model.md) |

## Full Reading Order

The documentation is organized in layers from "why" to "how to deploy". Start from the top and drill down as needed for your role.

| # | Document | Purpose | Status | Primary Audience |
|---|---|---|---|---|
| 1 | [`prd.md`](prd.md) | **Why** — Product requirements, market context, business strategy, roadmap | 🟡 Active Development | Engineering managers, product owners |
| 2 | [`framework-spec.md`](framework-spec.md) | **What** — System design, contracts, plugin schema, security boundaries | 🟡 Active Development | All technical roles |
| 3 | [`adr/`](adr/) | **Decisions** — Technology selections with full rationale and alternatives | 🟢 Accepted | Architects, senior engineers |
| 4 | [`software-architecture.md`](software-architecture.md) | **How (architecture)** — Quality attributes, design principles, C4 model, technology stack | 🟡 Active Development | Architects, senior engineers |
| 5 | [`system-design.md`](system-design.md) | **How (operations)** — Deployment topology, scaling model, HA, integration specs | 🟡 Active Development | Platform engineers, DevOps |
| 6 | [`implementation-design.md`](implementation-design.md) | **How (code)** — Class diagrams, algorithms, state machines, DDL, retry policies | 🟡 Active Development | Implementing engineers |
| 7 | [`data-model.md`](data-model.md) | **Data layer** — Tables, indexes, access control, partitioning, Elasticsearch indexes | 🟡 Active Development | Backend engineers, DBAs |
| 8 | [`infrastructure.md`](infrastructure.md) | **Deployment** — Docker, Kubernetes, AWS/GCP/Azure, CI/CD, Lite Mode | 🟡 Active Development | Platform engineers, SRE |

## Supplementary Documents

| Document | Purpose |
|---|---|
| [`getting-started.md`](getting-started.md) | 5-minute quickstart with Lite Mode — install, run, understand |
| [`local-development.md`](local-development.md) | Full-stack local setup with Docker Compose — 10 minutes, all services |
| [`glossary.md`](glossary.md) | Definitions for technical and regulatory terms used across docs |
| [`cli-reference.md`](cli-reference.md) | All `rak` CLI commands, flags, and environment variables |
| [`plugin-authoring-guide.md`](plugin-authoring-guide.md) | End-to-end: create, validate, test, and share a plugin |
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
| Plugin YAML schema | `framework-spec.md` Section 12 | `prd.md`, `implementation-design.md` |
| Workflow state machine | `framework-spec.md` Section 4 | `prd.md`, `software-architecture.md`, `system-design.md` |
| Agent contracts | `framework-spec.md` Section 4.3 | `prd.md`, `software-architecture.md` |
| Security boundaries & threats | `framework-spec.md` Section 9–10 | `prd.md`, `software-architecture.md` |
| Event schema & sources | `framework-spec.md` Section 5 | `software-architecture.md` |
| DDL / Table schemas | `data-model.md` | `software-architecture.md`, `implementation-design.md`, `adr/003` |
| Deployment options (detailed) | `infrastructure.md` | `framework-spec.md`, `prd.md`, `software-architecture.md`, `system-design.md` |
| Integration specs (detailed) | `system-design.md` Section 6.2 | `framework-spec.md`, `software-architecture.md`, `prd.md` |
| DB status vs Temporal phase | `implementation-design.md` Section 4.1.1 | `data-model.md` |
