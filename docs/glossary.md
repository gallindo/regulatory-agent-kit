# Glossary

Technical and regulatory terms used throughout the `regulatory-agent-kit` documentation.

---

## Technical Terms

| Term | Definition |
|---|---|
| **Activity** | A Temporal unit of work — comparable to a function call that can be retried, timed out, and executed on a separate worker machine. Each agent phase (analyze, refactor, test, report) is implemented as a Temporal activity. |
| **Alembic** | A Python database migration tool. Tracks schema changes as versioned Python scripts, enabling forward-only migrations with rollback safety. Used to manage the `rak` PostgreSQL schema. |
| **AST (Abstract Syntax Tree)** | A tree representation of source code structure. The framework uses ASTs to identify code patterns (e.g., classes implementing a specific interface) without relying on text matching. |
| **Checkpoint** | A mandatory human approval point in the pipeline. Two checkpoints exist: Impact Review (after analysis) and Merge Review (before merging). Both are non-bypassable and cryptographically signed. Also called "human-in-the-loop gate." |
| **Child Workflow** | A Temporal workflow started by a parent workflow. The compliance pipeline starts one child workflow per repository, enabling parallel processing with isolated failure domains. |
| **Condition DSL** | A domain-specific language for expressing when a regulation rule applies to a code file. Example: `class implements ICTService AND has_annotation(@AuditLog)`. Supports static evaluation (AST-based) and LLM-assisted evaluation. |
| **Ed25519** | An elliptic-curve digital signature scheme used to cryptographically sign audit trail entries, ensuring tamper detection. |
| **Elasticsearch** | A distributed search and analytics engine. Used as the regulatory knowledge base for full-text search (BM25), semantic vector search (kNN), and structured filtering of regulation documents. Optional — not required for Lite Mode. |
| **Event Sourcing** | A pattern where all state changes are stored as an immutable sequence of events. Temporal uses event sourcing to durably persist workflow state: on recovery, the workflow is deterministically replayed from the event log. |
| **FastAPI** | A modern Python web framework for building APIs. Used for the RAK API server (webhook events, human approvals, pipeline status). |
| **Jinja2** | A Python template engine. Regulation plugins use Jinja2 templates to generate remediation code, test files, and configuration changes. The framework runs templates in a `SandboxedEnvironment` to prevent arbitrary code execution. |
| **JSON-LD (JSON for Linked Data)** | A JSON format that adds semantic context via `@context` and `@type` fields. Used for audit trail payloads, giving each event a self-describing schema for cross-system compatibility. |
| **kNN (k-Nearest Neighbors)** | A vector search algorithm used by Elasticsearch to find semantically similar regulation text. Enables RAG (Retrieval-Augmented Generation) for the Analyzer Agent. |
| **LiteLLM** | A proxy server that provides a unified API across multiple LLM providers (Anthropic Claude, OpenAI GPT, AWS Bedrock, Azure OpenAI, self-hosted models). Deployed as 2+ replicas behind a load balancer. Switching providers is a config change. |
| **Lite Mode** | A zero-infrastructure evaluation mode (`rak run --lite`). Replaces Temporal with sequential execution, PostgreSQL with SQLite, and Elasticsearch with LLM-only context. Requires only Python 3.12+ and an LLM API key. |
| **MLflow** | An open-source platform for ML/LLM lifecycle management. Used as the LLM observability layer: traces every prompt, completion, token count, cost, and latency. Stores metadata in PostgreSQL and artifacts in S3/GCS. |
| **OTLP (OpenTelemetry Protocol)** | The standard wire protocol for transmitting traces, metrics, and logs from applications to observability backends. Used by the Temporal interceptor and FastAPI middleware to export operational metrics to Prometheus. |
| **Pipeline** | The end-to-end compliance automation process: from receiving a regulatory change event through analysis, refactoring, testing, and reporting. Implemented as a Temporal workflow. |
| **Pipeline Run** | A specific execution instance of the pipeline, identified by a UUID (`run_id`). Tracks lifecycle status, cost, repositories, and audit entries. |
| **Psycopg 3** | A modern PostgreSQL adapter for Python with native async support. Used for all application database access (no ORM). |
| **PydanticAI** | A Python agent framework with strong typing via Pydantic models. Each agent (Analyzer, Refactor, TestGenerator, Reporter) is a PydanticAI agent with typed inputs, outputs, and an isolated tool set. |
| **Pydantic v2** | A Python data validation library. All data shapes (events, pipeline config, agent inputs/outputs, API schemas) are Pydantic `BaseModel` subclasses, providing validation, serialization, and schema generation. |
| **RAG (Retrieval-Augmented Generation)** | A technique where relevant documents are retrieved from a knowledge base (Elasticsearch) and injected into the LLM prompt as context, improving accuracy for domain-specific tasks. |
| **Regulation Plugin** | A declarative YAML file that defines a regulatory ruleset — rules, conditions, remediation strategies, templates, cross-references, and metadata. The framework core is regulation-agnostic; all regulatory knowledge lives in plugins. |
| **SBOM (Software Bill of Materials)** | A machine-readable inventory of all software components and dependencies. Generated by Syft/CycloneDX in the CI/CD pipeline for supply chain security. |
| **Signal** | A Temporal primitive for sending durable messages to a running workflow. Used to deliver human checkpoint decisions (approve/reject) to the pipeline without polling. |
| **Temporal** | A distributed workflow engine (Go binary) that provides durable execution, automatic crash recovery, retry policies, and distributed task routing. The pipeline's orchestration layer. Workflows and activities are written in Python using the `temporalio` SDK. |
| **tree-sitter** | An incremental parser generator that produces concrete syntax trees for source files. The framework uses tree-sitter to parse code into ASTs for pattern matching (e.g., finding all classes that implement a given interface) without language-specific parsers. |
| **Typer** | A Python library for building CLI applications. The `rak` CLI (run, status, resume, rollback, plugin commands) is built with Typer. |
| **WAL (Write-Ahead Log)** | A technique where data is written to a log before being applied to the main store. The framework uses a local WAL to buffer audit entries, preventing data loss during PostgreSQL outages. |
| **Workflow** | A Temporal construct: a deterministic, durable function that orchestrates activities. The compliance pipeline is a Temporal workflow; each repository is processed by a child workflow. |

## Regulatory Terms

| Term | Definition |
|---|---|
| **BACEN** | Banco Central do Brasil (Central Bank of Brazil). Regulates Open Finance and financial technology in Brazil. |
| **DORA (Digital Operational Resilience Act)** | EU Regulation 2022/2554. Requires financial entities to implement ICT risk management, incident reporting, resilience testing, and third-party oversight. Effective January 2025. |
| **GDPR (General Data Protection Regulation)** | EU Regulation 2016/679. Governs personal data protection. Relevant to data residency routing (LiteLLM routes calls to region-specific models for GDPR-scoped data). |
| **HIPAA (Health Insurance Portability and Accountability Act)** | US law governing protected health information (PHI) in healthcare. |
| **ICT (Information and Communication Technology)** | A term used extensively in DORA to refer to the technology systems and services that financial entities depend on. |
| **MiCA (Markets in Crypto-Assets Regulation)** | EU Regulation 2023/1114. Establishes a regulatory framework for crypto-asset service providers. |
| **NIS2 (Network and Information Security Directive 2)** | EU Directive 2022/2555. Establishes cybersecurity requirements for essential and important entities across sectors. |
| **PCI-DSS (Payment Card Industry Data Security Standard)** | A security standard for organizations handling credit card data. Maintained by the PCI Security Standards Council. |
| **PSD2 (Payment Services Directive 2)** | EU Directive 2015/2366. Mandates Strong Customer Authentication (SCA) and Open Banking APIs for payment services. |
| **RegTech (Regulatory Technology)** | Technology tools and platforms that assist organizations with regulatory compliance. |
| **RTO / RPO** | **Recovery Time Objective** (maximum acceptable downtime) and **Recovery Point Objective** (maximum acceptable data loss). Used in DORA's ICT resilience testing requirements. |
| **RTS / ITS** | **Regulatory Technical Standards** and **Implementing Technical Standards**. Detailed technical specifications issued by regulatory bodies (e.g., EBA, ESMA) to implement high-level regulation requirements. |
| **SOX (Sarbanes-Oxley Act)** | US law requiring public companies to maintain internal controls over financial reporting. |

---

*This glossary covers terms used across the documentation suite. For the full documentation reading order, see [`README.md`](README.md).*
