# regulatory-agent-kit

### Production-Grade Multi-Agent Framework for Automated Regulatory Compliance in Software Systems

> **Version:** 2.0 — Product Requirements, Architecture & Strategic Analysis Document
> **Status:** Active Development
> **Classification:** Open Source (Apache 2.0 License)
> **Last Updated:** 2026-03-26
> **Glossary:** See [`glossary.md`](glossary.md) for technical and regulatory term definitions.

---

### Document Structure

This repository's documentation is split into three layers to maintain regulation-agnosticism in the framework core:

| Document | Purpose | Contains regulation-specific content? |
|---|---|---|
| **[`docs/architecture.md`](architecture.md)** | Pure framework specification — agents, plugins, events, security, deployment | **No** — completely regulation-agnostic |
| **`docs/regulatory-agent-kit.md`** (this file) | Full product document — market context, business strategy, competitive analysis, roadmap | Yes — uses specific regulations as examples for market positioning |
| **[`regulations/README.md`](../regulations/README.md)** | Plugin catalog, contribution guide, plugin roadmap | Yes — lists all planned and community regulation plugins |
| **[`regulations/dora/README.md`](../regulations/dora/README.md)** | DORA-specific plugin documentation (five pillars, RTS/ITS, cross-references) | Yes — entirely DORA-specific |

**The framework codebase is regulation-agnostic.** All regulatory knowledge lives in YAML plugins under `regulations/`. Specific regulations mentioned in this document (DORA, PCI-DSS, PSD2, etc.) are used as illustrative examples for market positioning and business context, not as framework dependencies.

---

## Table of Contents

1. [Executive Summary & Objective](#1-executive-summary--objective)
2. [Target Market](#2-target-market)
3. [Pain Points Solved](#3-pain-points-solved)
4. [Core Features](#4-core-features)
5. [Integrations & Ecosystem](#5-integrations--ecosystem)
6. [Risk Analysis](#6-risk-analysis)
7. [Open Source Strategy](#7-open-source-strategy)
8. [Future Roadmap](#8-future-roadmap)
9. [References & Citations](#9-references--citations)

---

## 1. Executive Summary & Objective

**`regulatory-agent-kit`** is an open-source Python framework for building production-grade, multi-agent AI pipelines that automate the detection, analysis, and remediation of regulatory compliance issues across large software codebases.

The framework operates on a foundational architectural principle: **regulatory change is a software engineering problem.** When a financial regulator publishes a new directive, when an API contract shifts, or when a compliance standard is revised, software teams must identify every affected system, understand the impact, apply coordinated changes, generate validation tests, and produce an auditable trail — all under time pressure, across dozens or hundreds of repositories. Without automation, this process is error-prone, expensive, and dangerously slow.

Research demonstrates that 50–70% of compliance activities could be automated, with typical cost reductions of 30–50% [9]. Multi-agent AI systems have shown the ability to decompose complex software engineering tasks into specialized roles — analysis, refactoring, testing, reporting — coordinating through explicit state machines and human-in-the-loop checkpoints [1][2][4].

`regulatory-agent-kit` solves this by providing:

- A **pluggable, regulation-as-configuration model** where any regulatory ruleset — DORA (Digital Operational Resilience Act), PSD2 (Payment Services Directive 2), PCI-DSS (Payment Card Industry Data Security Standard), BACEN (Central Bank of Brazil), SOX (Sarbanes-Oxley Act), HIPAA (Health Insurance Portability and Accountability Act), NIS2 (Network and Information Security Directive 2), MiCA (Markets in Crypto-Assets Regulation), EU AI Act — is expressed as a declarative YAML plugin, not hardcoded logic. This approach aligns with the OECD's "Regulation as Code" initiative, which advocates for machine-readable regulatory expressions [7].
- A **composable multi-agent orchestration engine**, built on **Temporal + PydanticAI** (see [ADR-002](adr/002-langgraph-vs-temporal-pydanticai.md)), where specialized AI agents (Analyzer, Refactor, TestGenerator, Reporter) collaborate in defined workflows with explicit state management, retry logic, and human-in-the-loop checkpoints [21][22].
- A **generic event-driven architecture** where regulatory change events from any upstream source trigger the pipeline and deliver results downstream — decoupled from any specific regulator's publication channel.
- **Full observability** of every agent decision, every LLM call, every tool invocation, and every generated artifact — enabling the audit trails that regulated environments legally require, as mandated by the EU AI Act (Regulation (EU) 2024/1689) [24] and the NIST AI Risk Management Framework [25].

The result is a reusable infrastructure layer that any engineering team can adopt to build their own compliance automation tools, whether targeting Brazilian Open Finance requirements, European DORA mandates, or US payment card security standards.

### Strategic Positioning

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   "regulatory-agent-kit is to compliance automation        │
│    what Spring Boot is to Java microservices:               │
│    the opinionated, production-ready foundation             │
│    that eliminates boilerplate and lets teams               │
│    focus on their domain-specific logic."                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Market Positioning & Competitive Differentiation

No established RegTech vendor currently operates at the source-code level. Existing platforms (Ascent/Wolters Kluwer, Corlytics, CUBE, Suade Labs) occupy the "detect and report" layers — identifying which regulations apply and generating compliance reports. AI code analysis tools (Snyk, SonarQube, Semgrep, CodeQL) focus on security vulnerabilities, not regulatory compliance. LLM-based code transformation tools (Aider, GitHub Copilot Workspace, Amazon Q Developer) are general-purpose, without regulatory domain knowledge.

`regulatory-agent-kit` uniquely occupies the **"remediate in code"** layer — the last mile between regulatory awareness and engineering implementation.

| Layer | Existing Tools | regulatory-agent-kit |
|---|---|---|
| **Regulatory Intelligence** | Ascent, CUBE, Corlytics | Consumes their output as Kafka events |
| **Security Scanning** | Snyk, SonarQube, Semgrep, CodeQL | Complements with regulation-specific rules |
| **Code Transformation** | Aider, Copilot, Amazon Q | Adds domain-specific orchestration, audit trails, multi-repo pipelines |
| **Compliance Reporting** | Suade Labs, Vanta, Drata | Generates as part of the pipeline output |
| **Code-Level Compliance Automation** | **No established player** | **Primary focus** |

---

## 2. Target Market

### 2.1 Ideal Customer Profile (ICP)

The framework targets two distinct buyer personas that often coexist within the same organization:

| Dimension | **Primary Persona** | **Secondary Persona** |
|---|---|---|
| **Title** | Staff / Principal Software Engineer | Platform Engineering Manager / VP of Engineering |
| **Industry** | Financial Services, FinTech, InsurTech, HealthTech | Any industry under mandatory software compliance |
| **Company Size** | 200–10,000 employees | Series B+ startup or Enterprise |
| **Tech Stack** | Python, Java, Kotlin; Kafka; AWS/GCP/Azure | Polyglot; Kubernetes-native |
| **Primary Goal** | Automate compliance remediation at scale | Reduce engineering hours spent on regulatory cycles |
| **Key Frustration** | Manual cross-repo changes take weeks and introduce regressions | Cannot predict or budget compliance effort across quarters |
| **Evaluation Trigger** | New regulatory deadline announced; audit finding issued | Engineering team burned out after a compliance sprint |

### 2.2 Market Segments & Sizing

The global RegTech market was valued at approximately USD 12.8–15.8 billion in 2024 and is projected to reach USD 45–60 billion by 2030, with a CAGR of 20–23% [8][10]. The "compliance automation" subset — tools that act rather than just report — is estimated at USD 2.5–3.5 billion in 2024, growing at 25–30% CAGR, driven by DORA enforcement (January 2025) and PCI-DSS v4.0 mandate (March 2025).

```mermaid
pie title Addressable Market by Regulatory Domain
    "Financial Services (DORA, PSD2, PCI-DSS)" : 38
    "Open Banking / Central Bank Mandates" : 20
    "Healthcare (HIPAA, LGPD, GDPR)" : 15
    "AI Regulation (EU AI Act)" : 10
    "Enterprise SaaS (SOX, ISO 27001)" : 10
    "Sustainability (CSRD, SEC Climate)" : 5
    "Other Regulated Industries" : 2
```

**Note on AI Regulation market segment:** The EU AI Act (Regulation (EU) 2024/1689) [24] creates a new, large addressable market. The kit could be used to ensure AI systems themselves are compliant — scanning codebases for AI/ML components, verifying required documentation exists (model cards [27], data sheets, risk assessments), and validating that human oversight mechanisms are implemented. This represents a powerful narrative: **"an AI framework that ensures other AI systems are compliant."**

### 2.3 Geographic Focus

| Region | Primary Regulation Drivers | Market Readiness |
|---|---|---|
| **EU** | DORA (Jan 2025), PSD2/PSD3, MiCA (Dec 2024), NIS2 (Oct 2024), EU AI Act (Aug 2024), CSRD | **High** — Multiple concurrent enforcement deadlines creating urgent demand |
| **Brazil** | Open Finance Brasil (800+ institutions), PIX, BACEN Circulars, LGPD | **High** — One of the most comprehensive Open Banking/Open Finance ecosystems globally, with scope extending beyond payments to insurance, investments, and pensions [source: BACEN Open Finance portal] |
| **United States** | OCC guidance, PCI-DSS v4.0 (March 2025 final deadline), SOX, CCPA/CPRA | **Medium-High** — Fragmented regulators, high per-incident costs |
| **United Kingdom** | FCA regulations, Open Banking (OBIE), post-Brexit regulatory divergence | **High** — Regulatory independence driving new mandates |
| **Australia** | CDR (Consumer Data Right), APRA CPS 230 (July 2025) | **Medium** — CPS 230 (replacing CPS 231/232/234) directly analogous to DORA |

---

## 3. Pain Points Solved

### 3.1 The Compliance Engineering Crisis

Modern financial institutions operate on **portfolios of 50 to 500+ microservices**. When a regulator issues a new requirement — a revised API specification, a new data field, a changed security protocol — the consequences ripple across every service that participates in the affected ecosystem. Research on scaling agile methods to regulated environments documents the significant overhead of manual compliance activities, with friction between development practices and regulatory requirements creating substantial engineering cost [18].

```mermaid
flowchart TD
    A["Regulator publishes\nnew directive"] --> B{Manual Process\nToday}
    A --> C{With\nregulatory-agent-kit}

    B --> D["Engineering team reads\n200-page directive"]
    D --> E["Manual audit of\nevery repository"]
    E --> F["Spreadsheet of\naffected services"]
    F --> G["Manual code changes\nacross teams"]
    G --> H["Regression bugs\nintroduced silently"]
    H --> I["Missed deadline\nor failed audit"]
    I --> J["Regulatory fine\nor remediation cost"]

    C --> K["Event source\ndetects change event"]
    K --> L["Analyzer Agent\nmaps impact across repos"]
    L --> M["Refactor Agent\napplies changes safely"]
    M --> N["TestGenerator Agent\nvalidates backward compat"]
    N --> O["Reporter Agent\nproduces audit trail"]
    O --> P["Merge requests ready\nfor tech lead review"]
    P --> Q["On-time delivery\nwith full audit log"]

    style B fill:#ff6b6b,color:#fff
    style C fill:#51cf66,color:#fff
    style J fill:#ff6b6b,color:#fff
    style Q fill:#51cf66,color:#fff
```

### 3.2 Pain Points Matrix

| # | Pain Point | Current Impact | How the Kit Solves It |
|---|---|---|---|
| **P1** | **Discovering which repositories are affected** by a regulatory change requires manual audit | 40–80 engineering hours per compliance cycle | Analyzer Agent traverses all repositories automatically, using AST parsing (via tree-sitter [14]) and semantic search to identify affected code paths |
| **P2** | **Applying changes across dozens of repos** is error-prone and inconsistent when done manually | 3–12 weeks of coordinated engineering effort | Refactor Agent applies standardized, regulation-aware changes across all affected repositories in parallel, using AST-aware editing (not text substitution) [12][15] |
| **P3** | **Ensuring backward compatibility** after changes requires extensive manual testing | Regressions discovered in production post-deployment | TestGenerator Agent creates targeted tests for both new requirements and backward compatibility before any merge request is created |
| **P4** | **Audit documentation** required by regulators must be manually assembled from disparate sources | 20–40 hours of technical writing per audit cycle | Reporter Agent generates structured, machine-readable audit trails (JSON-LD) automatically, capturing every decision and transformation [26] |
| **P5** | **Regulatory rules change frequently**, requiring continuous re-work of tooling | Compliance tools become obsolete with each regulatory revision | Regulation-as-YAML plugin model: updating compliance rules requires no code changes, only YAML updates [7] |
| **P6** | **LLM hallucinations in production code** are catastrophic in regulated environments | Silent introduction of bugs that pass unit tests but fail in production [5] | Human-in-the-loop checkpoints after each agent phase [21][23]; all changes surface as reviewable merge requests, never auto-deployed |
| **P7** | **Observability of AI-generated changes** is absent from most agentic systems | No audit trail of what the AI decided, why, and what it produced | Full MLflow tracing of every LLM call, every tool invocation, every agent state transition — permanently stored and queryable [25][27] |
| **P8** | **Cross-regulation conflicts** are invisible until audit time | Multiple regulations requiring contradictory changes to the same code (e.g., DORA audit logging vs. GDPR data minimization) | Cross-regulation dependency graph detects conflicts and escalates to human review before any code changes are applied |

### 3.3 The Cost of Inaction

> Based on industry reports from Thomson Reuters "Cost of Compliance" surveys and BCG Global Risk Reports [10]:

- **Compliance costs at major banks grew 60% over the preceding decade**, with technology investment as the primary mitigation strategy
- Average time from regulatory publication to implementation deadline: **6–18 months**
- DORA empowers national competent authorities to impose administrative penalties on financial entities (amounts vary by member state), and enables Lead Overseers to levy periodic penalty payments on critical ICT third-party providers of **up to 1% of average daily global turnover per day of non-compliance** (Article 35(8), Regulation (EU) 2022/2554) [11]
- GDPR fines reached **EUR 2.1 billion in 2023 alone**
- PCI-DSS v4.0 final deadline for all "future-dated" requirements: **March 31, 2025** — PCI-DSS v3.2.1 is now fully retired

---

## 4. Core Features

### 4.1 System Architecture Overview

```mermaid
graph TB
    subgraph INPUT["INPUT LAYER"]
        ES_SRC["Event Sources\n(Kafka · Webhook · SQS · File)"]
        ES["Elasticsearch Index\n(Regulatory Knowledge Base)"]
        RS["Repository Sources\nGitHub · GitLab · Bitbucket"]
        YAML["Regulation Plugins\n*.yaml"]
    end

    subgraph ORCHESTRATION["ORCHESTRATION LAYER (Temporal + PydanticAI)"]
        WF["Workflow Engine\n(Temporal)"]
        SM["State Manager\n(Temporal + PostgreSQL)"]
        HiL["Human-in-the-Loop\nCheckpoints (non-bypassable)"]
    end

    subgraph AGENTS["AGENT LAYER"]
        AA["Analyzer Agent\nImpact Detection"]
        RA["Refactor Agent\nCode Transformation"]
        TG["TestGenerator Agent\nBackward Compat Validation"]
        RP["Reporter Agent\nAudit Trail Generation"]
    end

    subgraph TOOLS["TOOL LAYER"]
        GIT["Git Tools\nclone · diff · branch · PR"]
        AST["AST Tools (tree-sitter)\nparse · search · transform"]
        TEST["Test Tools (sandboxed)\nrun · evaluate · report"]
        LLM["LiteLLM Gateway\nClaude · GPT · Gemini"]
    end

    subgraph OBSERVABILITY["OBSERVABILITY LAYER"]
        LF["MLflow\nTracing & Evaluation"]
        OTEL["OpenTelemetry\nMetrics & Spans"]
        PROM["Prometheus + Grafana\nOperational Dashboards"]
    end

    subgraph OUTPUT["OUTPUT LAYER"]
        MR["Merge Requests\n(per repository)"]
        AL["Audit Log\n(JSON-LD, immutable, signed)"]
        REP["Compliance Report\n(PDF/HTML)"]
        NOTIF["Notifications\nSlack · Email · Webhook"]
    end

    ES_SRC -->|"Change event\ntriggered"| WF
    YAML -->|"Rules loaded\nat startup"| WF
    ES -->|"Regulatory\nknowledge"| AA
    RS -->|"Repository\naccess"| AA

    WF --> SM
    SM --> AA
    AA -->|"Impact map\nproduced"| HiL
    HiL -->|"Approved\nby tech lead"| RA
    RA -->|"Changes\napplied"| TG
    TG -->|"Tests\npassing"| HiL
    HiL -->|"Approved\nfor merge"| RP

    AA --> LLM
    RA --> LLM
    TG --> LLM
    RP --> LLM

    AA --> GIT
    AA --> AST
    RA --> GIT
    RA --> AST
    TG --> TEST
    TG --> GIT
    RP --> GIT

    LLM --> LF
    LF --> OTEL
    OTEL --> PROM

    RP --> MR
    RP --> AL
    RP --> REP
    RP --> NOTIF

    style INPUT fill:#e3f2fd,stroke:#1565c0
    style ORCHESTRATION fill:#f3e5f5,stroke:#6a1b9a
    style AGENTS fill:#e8f5e9,stroke:#2e7d32
    style TOOLS fill:#fff3e0,stroke:#e65100
    style OBSERVABILITY fill:#fce4ec,stroke:#880e4f
    style OUTPUT fill:#e0f2f1,stroke:#00695c
```

**Key architectural changes from v1.0:**
- **Event Sources** are now pluggable: Kafka, Webhook (HTTP POST), SQS, or file-based (for lite mode evaluation)
- **State Manager** uses Temporal's event-sourced persistence to PostgreSQL for durable checkpointing, not in-memory state
- **AST Tools** use tree-sitter as the universal parsing backend, supporting partial ASTs for syntactically invalid files [14]
- **Test execution is sandboxed** in network-isolated, resource-limited containers
- **Audit logs are cryptographically signed** for tamper evidence

### 4.2 Feature 1 — Regulation-as-YAML Plugin System

The kit's most strategically important capability is its **total decoupling of regulatory knowledge from code**. Rules are expressed as structured YAML plugins that non-engineers (compliance officers, legal teams) can read and validate, while engineers can version-control and test like any other configuration. This aligns with the OECD's "Regulation as Code" initiative [7] and the broader movement toward formalizing compliance objectives as verifiable predicates [16].

**Plugin Structure:**

```yaml
# regulations/dora_ict.yaml
id: "dora-ict-risk-2025"
name: "DORA ICT Risk Management Requirements"
version: "1.0.0"
effective_date: "2025-01-17"
jurisdiction: "EU"
authority: "European Banking Authority"
source_url: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554"

# Regulatory hierarchy: Level 1 (regulation) → Level 2 (RTS/ITS) → Rules
regulatory_technical_standards:
  - id: "JC-2023-86"
    name: "RTS on ICT risk management framework"
    url: "https://www.eba.europa.eu/activities/digital-finance/digital-operational-resilience-act-dora"

# Cross-regulation dependencies
cross_references:
  - regulation_id: "gdpr"
    relationship: "does_not_override"     # Generic term (EU: "without prejudice to")
    articles: ["2(3)"]
    conflict_handling: "escalate_to_human"
  - regulation_id: "nis2"
    relationship: "takes_precedence"      # Generic term (EU: "lex specialis")
    articles: ["1(2)"]
  - regulation_id: "psd2"
    relationship: "complementary"
    articles: ["2(1)(a)"]

rules:
  - id: "DORA-ICT-001"
    description: "All ICT systems must implement structured logging for audit purposes"
    severity: "critical"
    dora_pillar: "ict_risk_management"  # One of 5 DORA pillars
    rts_reference: "JC-2023-86"
    affects:
      - pattern: "**/*.java"
        condition: "class implements ICTService AND NOT has_annotation(@AuditLog)"
      - pattern: "**/*.kt"
        condition: "class : ICTService AND NOT has_annotation(@AuditLog)"
    remediation:
      strategy: "add_annotation"
      template: "templates/audit_log_annotation.j2"
      test_template: "templates/audit_log_test.j2"
      confidence_threshold: 0.85  # Below this, require additional human review

  - id: "DORA-ICT-002"
    description: "RTO/RPO objectives must be documented in service manifests"
    severity: "high"
    dora_pillar: "digital_operational_resilience_testing"
    affects:
      - pattern: "**/service-manifest.yaml"
        condition: "NOT has_key(resilience.rto) OR NOT has_key(resilience.rpo)"
    remediation:
      strategy: "add_configuration"
      template: "templates/resilience_manifest.j2"

# Plugin versioning and supersession
supersedes: null  # or "dora-ict-risk-2024-draft"
changelog: "Initial release aligned with DORA application date 2025-01-17"

# Legal disclaimer (required field)
disclaimer: >
  This plugin represents one interpretation of Regulation (EU) 2022/2554 (DORA).
  It does not constitute legal advice. Organizations must validate compliance
  with their own legal and compliance teams.

kafka_event:
  topic: "regulatory-changes"
  schema:
    regulation_id: "dora-ict-risk-2025"
    change_type: "new_requirement"
```

**DORA Coverage — Five Pillars:**

> For detailed DORA plugin documentation including all five pillars, RTS/ITS references, enforcement architecture, and cross-regulation dependencies, see [`regulations/dora/README.md`](../regulations/dora/README.md).

| Pillar | Automation Potential |
|---|---|
| **1. ICT Risk Management** (Arts. 5–16) | **HIGH** |
| **2. ICT Incident Reporting** (Arts. 17–23) | **HIGH** |
| **3. Digital Operational Resilience Testing** (Arts. 24–27) | **MEDIUM** |
| **4. Third-Party Risk Management** (Arts. 28–44) | **MEDIUM** |
| **5. Information Sharing** (Art. 45) | **LOW** |

**Supported remediation strategies:**

| Strategy | Description | Example Use Case |
|---|---|---|
| `add_annotation` | Adds class/method annotations | Adding `@AuditLog` to all ICT service classes |
| `add_configuration` | Injects configuration keys into manifests | Adding RTO/RPO fields to service descriptors |
| `replace_pattern` | Replaces deprecated patterns with compliant ones | Updating deprecated API endpoint signatures |
| `add_dependency` | Adds required library dependencies to build files | Injecting a compliance SDK into all services |
| `generate_file` | Creates new required files per repository | Generating DPIA documentation templates |
| `custom_agent` | Delegates to a user-defined agent class | Complex multi-step remediations |

### 4.3 Feature 2 — Temporal + PydanticAI Multi-Agent Orchestration

The workflow engine is built on **Temporal** (self-hosted, Go binary) with **PydanticAI** as the agent framework (see [ADR-002](adr/002-langgraph-vs-temporal-pydanticai.md)). Each agent phase is a Temporal Activity, and transitions are governed by explicit workflow logic, including human approval gates via Temporal Signals. Pipeline state is durably persisted to PostgreSQL via Temporal's event-sourced history, ensuring crash recovery at any point in the pipeline. The canonical state machine definition is maintained in [`architecture.md` Section 4](architecture.md#4-agent-orchestration).

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> COST_ESTIMATION : Event received\n(regulatory change detected)

    COST_ESTIMATION --> ANALYZING : Cost approved\n(within budget threshold)
    COST_ESTIMATION --> IDLE : Cost rejected\n(too expensive)

    ANALYZING --> IMPACT_REVIEW : Analyzer Agent complete\n(impact map produced)
    ANALYZING --> ERROR : Agent failure

    IMPACT_REVIEW --> REFACTORING : Tech lead approves\nimpact assessment
    IMPACT_REVIEW --> IDLE : Tech lead rejects\n(false positive)

    REFACTORING --> TESTING : Refactor Agent complete\n(changes applied to branches)
    REFACTORING --> ERROR : Agent failure\nor tool error

    TESTING --> MERGE_REVIEW : TestGenerator Agent complete\n(all tests passing)
    TESTING --> REFACTORING : Tests failing\n(agent retries with\ncorrected approach)

    MERGE_REVIEW --> REPORTING : Tech lead approves\nchanges for merge
    MERGE_REVIEW --> REFACTORING : Tech lead requests\nmodifications

    REPORTING --> COMPLETE : Reporter Agent complete\n(MRs + audit log + report)

    COMPLETE --> [*]
    ERROR --> [*]

    note right of COST_ESTIMATION
        Pre-run LLM cost
        estimation displayed
    end note

    note right of IMPACT_REVIEW
        Human-in-the-Loop
        Checkpoint #1
        (non-bypassable, signed)
    end note

    note right of MERGE_REVIEW
        Human-in-the-Loop
        Checkpoint #2
        (non-bypassable, signed)
    end note
```

> The state names above are conceptual. The canonical state machine is defined in [`architecture.md` Section 4](architecture.md#4-agent-orchestration). For the implementation-level state mapping (DB status vs Temporal phase), see [`lld.md` Section 4.1](lld.md#41-pipeline-run-lifecycle).

**Key additions to the orchestration model:**

- **Cost estimation gate** before analysis begins — operators see estimated LLM cost before approving
- **Non-bypassable human checkpoints** via Temporal Signals with cryptographic signing of approvals
- **Per-repository progress tracking** in PostgreSQL: `{repo_url, status: pending|in_progress|complete|failed, branch_name, commit_sha}`
- **Idempotent operations** with deterministic branch naming (`rak/{regulation_id}/{rule_id}`) and deterministic Temporal workflow IDs
- **Repository-level locking** via Temporal workflow ID uniqueness to prevent conflicts from concurrent pipeline runs
- **Dead letter queue** for failed repositories, with retry support via `rak retry-failures --run-id <id>`

**Agent responsibilities** (canonical contracts: [`architecture.md` Section 4.3](architecture.md#43-agent-contracts)):

| Agent | Input | Core Capability | Output |
|---|---|---|---|
| **Analyzer Agent** | Repository list + regulation YAML | Clones repositories; uses tree-sitter AST parsing and semantic search to identify all code paths affected by the regulation; evaluates all applicable regulations (not just one); ranks impact by severity | Structured impact map (JSON): repository → affected files → affected rules → suggested approach → cross-regulation conflicts |
| **Refactor Agent** | Impact map + regulation templates | Applies rule-specific transformations to source code using AST-aware editing [12][15]; creates feature branches with deterministic naming; generates change summaries with confidence scores | Modified code on branches; per-file change diffs; branch references; confidence scores per change |
| **TestGenerator Agent** | Refactored code + original code | Generates two categories of tests in sandboxed execution: (1) tests that validate the new regulatory requirements are met; (2) regression tests that confirm existing behavior is preserved [3][5] | Test files committed to branches; test execution report; pass/fail status per repository |
| **Reporter Agent** | All previous outputs + metadata | Assembles the complete audit trail in JSON-LD format [26]; generates human-readable compliance report; creates merge requests with structured descriptions; sends notifications | Merge requests; signed JSON-LD audit log; PDF/HTML compliance report; webhook notifications; rollback manifest |

### 4.4 Feature 3 — Multi-Source Event Architecture

The framework treats regulatory changes as **domain events** from pluggable sources. This architectural decision decouples the kit from any single messaging infrastructure.

**Supported event sources:**

| Source | Use Case | Dependencies |
|---|---|---|
| **Kafka** (`KafkaEventSource`) | Enterprise environments with existing Kafka infrastructure | Kafka cluster |
| **Webhook** (`WebhookEventSource`) | Lightweight deployments; CI/CD integration; manual triggers | None (built-in HTTP endpoint) |
| **SQS** (`SQSEventSource`) | AWS-native organizations | AWS SQS |
| **File** (`FileEventSource`) | Development, testing, and evaluation ("lite mode") | None |

**Shift-Left Integration (CI/CD Mode):**

Beyond reacting to regulatory changes, the framework also supports **code change events** — detecting when a developer is about to introduce a compliance violation:

- **CI/CD pipeline gate:** A GitHub Action / GitLab CI step that blocks merges if code introduces compliance violations
- **PR review bot:** An agent that comments on pull requests with compliance impact analysis
- **Pre-commit hook:** A lightweight Analyzer that flags violations before code is pushed

```mermaid
sequenceDiagram
    participant P as Event Source
    participant C as EventConsumer
    participant ES as Elasticsearch<br/>(Regulatory KB)
    participant WF as Temporal Workflow
    participant AA as Analyzer Agent
    participant RA as Refactor Agent
    participant TG as TestGenerator Agent
    participant RP as Reporter Agent
    participant TL as Tech Lead<br/>(Human Checkpoint)
    participant GH as Git Provider<br/>(GitHub/GitLab)

    P->>C: Event {regulation_id, change_type, diff}
    C->>ES: Index regulation change + update knowledge base
    C->>WF: Trigger workflow with event payload

    WF->>WF: Estimate LLM cost; display to operator
    WF->>AA: Start analysis phase
    AA->>ES: Query affected rules + regulatory context
    AA->>GH: Clone repositories (parallel, cached)
    AA->>AA: Run tree-sitter AST analysis + semantic search
    AA->>AA: Check cross-regulation dependencies
    AA-->>WF: Return impact_map {repos, files, rules, severity, conflicts}

    WF->>TL: Present impact report + cost estimate (Checkpoint #1)
    TL-->>WF: Approve (cryptographically signed)

    WF->>RA: Start refactoring phase (fan-out across repos)
    RA->>GH: Create feature branches (deterministic naming)
    RA->>RA: Apply transformations per rule template
    RA-->>WF: Return changed_branches {diffs, summaries, confidence}

    WF->>TG: Start test generation phase
    TG->>GH: Read changed code
    TG->>TG: Generate compliance + regression tests
    TG->>TG: Execute tests in sandboxed containers
    TG-->>WF: Return test_results {pass_rate, failures}

    WF->>TL: Present changes for review (Checkpoint #2)
    TL-->>WF: Approve (cryptographically signed)

    WF->>RP: Start reporting phase
    RP->>GH: Create merge requests (per repository)
    RP->>RP: Generate signed JSON-LD audit log
    RP->>RP: Compile compliance report
    RP->>RP: Generate rollback manifest
    RP-->>WF: Return output_artifacts {mr_urls, audit_log, report, rollback_manifest}

    WF-->>C: Pipeline complete
```

### 4.5 Feature 4 — LiteLLM Multi-Model Gateway

All LLM calls within the framework are routed through **LiteLLM**, providing model-agnostic agent logic with built-in fallback routing, cost tracking, and rate limit management.

**Benefits for regulated environments:**

- **Data residency compliance:** Route specific agent calls to on-premise or region-specific models (Azure OpenAI in EU, AWS Bedrock in US) based on data classification. **This is mandatory, not optional**, for any deployment handling data subject to GDPR or equivalent.
- **Cost optimization:** Use larger models (Claude Opus, GPT-4o) for complex analysis tasks; smaller models (Haiku, GPT-4o-mini) for templated, deterministic tasks like test generation.
- **Model version pinning:** Pin specific model versions in production to ensure deterministic behavior. A code transformation that worked correctly with one model version may behave differently with an update.
- **Audit of model selection:** Every model used for every decision is logged in MLflow (see [ADR-005](adr/005-llm-observability-platform.md)), ensuring the audit trail includes the reasoning engine, not just the output.
- **Vendor independence:** Switching LLM providers requires zero code changes — only a configuration update.
- **Rate limit management:** Token bucket rate limiter prevents hitting API limits when processing 500+ repositories. Estimated cost is displayed before pipeline execution begins.

### 4.6 Feature 5 — Compliance-Grade Observability

Every agent decision in a regulated environment is a potential audit artifact. The framework integrates **MLflow** (self-hosted, PostgreSQL + S3 backend; see [ADR-005](adr/005-llm-observability-platform.md)) as its primary LLM observability layer, with a mandatory local write-ahead log (WAL) for audit-critical traces to prevent data loss during MLflow outages.

| Observable Event | Captured Data | Retention |
|---|---|---|
| LLM call initiated | Model + version, prompt (sanitized), temperature, max_tokens | Configurable (default: 90 days) |
| LLM response received | Full output, token count, latency, cost, confidence score | Configurable |
| Tool invocation | Tool name, input parameters, output | Configurable |
| Agent state transition | From state, to state, trigger condition, timestamp | Permanent |
| Human checkpoint decision | Actor, decision (approve/reject), rationale, timestamp, **cryptographic signature** | Permanent |
| Test execution result | Pass/fail per test, stack traces on failure, sandbox metadata | 30 days |
| Merge request created | Repository, branch, PR URL, rule IDs addressed | Permanent |
| Audit log generated | SHA-256 hash of log, storage location, **digital signature** | Permanent |
| Cross-regulation conflict detected | Conflicting rule IDs, affected code regions, resolution | Permanent |
| Cost tracking | Per-call cost, cumulative pipeline cost, budget threshold | Permanent |

This data structure enables regulators and internal audit teams to answer: *"For this code change, which AI model (including version) made which decisions, who approved them (with cryptographic proof), and what tests validated the result?"* — meeting the requirements of both the EU AI Act [24] and the NIST AI Risk Management Framework [25].

### 4.7 Feature 6 — Cross-Regulation Dependency Graph

A single code change may trigger multiple regulations simultaneously. The kit's cross-regulation dependency engine uses generic relationship types to encode these dependencies:

| Relationship | Meaning | Example (illustrative) |
|---|---|---|
| `does_not_override` | Both regulations apply; neither supersedes | DORA does not override GDPR (Art. 2(3)) |
| `takes_precedence` | This regulation prevails for entities in scope | DORA prevails over NIS2 for financial entities (Art. 1(2)) |
| `complementary` | Both apply and reinforce each other | PSD2 + PCI-DSS for payment card processing |
| `supersedes` | Replaces the referenced regulation entirely | New version replaces old version |
| `references` | Cites the other without a precedence relationship | EU AI Act references GDPR for data governance |

> For the complete DORA cross-regulation dependency map, see [`regulations/dora/README.md`](../regulations/dora/README.md).

**Practical implications (regulation-agnostic behavior):**
- The Analyzer Agent evaluates **all loaded regulation plugins** for each code change, not just one
- **Conflicting requirements are detected and flagged** (e.g., audit logging vs. data minimization) — by default, conflicts are escalated to human review (`escalate_to_human`). Plugin authors may opt into `apply_both` or `defer_to_referenced` for well-understood relationships, but the default behavior is human escalation, as conflict resolution is ultimately a legal decision
- **Precedence relationships** are encoded so the kit does not generate duplicate or contradictory remediations

---

## 5. Integrations & Ecosystem

### 5.1 Integration Architecture

```mermaid
graph LR
    subgraph REGULATORY_SOURCES["Regulatory Sources\n(Upstream — NOT part of kit)"]
        SRC_A["Regulatory Portal A\n(any jurisdiction)"]
        SRC_B["Regulatory Portal B\n(any jurisdiction)"]
        SRC_C["Regulatory Portal C\n(any jurisdiction)"]
        MANUAL["Manual Upload\n(Compliance Officer)"]
    end

    subgraph KIT["regulatory-agent-kit"]
        CONSUMER["EventConsumer\n(Kafka · Webhook · SQS · File)"]
        ES_INT["Elasticsearch\nIntegration"]
        PIPELINE["Agent Pipeline\n(Temporal + PydanticAI)"]
        LITELLM["LiteLLM Gateway"]
        MLFLOW["MLflow\nObservability"]
    end

    subgraph GIT_PROVIDERS["Git Providers"]
        GITHUB["GitHub\nEnterprise / Cloud"]
        GITLAB["GitLab\nSelf-hosted / Cloud"]
        BITBUCKET["Bitbucket\nData Center / Cloud"]
    end

    subgraph LLM_PROVIDERS["LLM Providers"]
        CLAUDE["Anthropic Claude\n(Primary)"]
        OPENAI["OpenAI GPT-4o\n(Fallback)"]
        BEDROCK["AWS Bedrock\n(Data Residency)"]
        AZURE_OAI["Azure OpenAI\n(Enterprise)"]
    end

    subgraph MESSAGING["Messaging & Storage"]
        KAFKA["Apache Kafka"]
        ELASTICSEARCH["Elasticsearch\n(Regulatory KB)"]
        S3["Object Storage\nS3 / GCS / Azure Blob"]
        PG["PostgreSQL\n(State + Checkpoints)"]
    end

    subgraph NOTIFICATIONS["Notifications"]
        SLACK["Slack"]
        EMAIL["Email\nSMTP / SendGrid"]
        WEBHOOK["Generic Webhook"]
    end

    subgraph CICD["CI/CD Integration"]
        GHA["GitHub Actions"]
        GLCI["GitLab CI"]
        JENKINS["Jenkins"]
    end

    SRC_A -->|"Regulation published"| KAFKA
    SRC_B -->|"Standard updated"| KAFKA
    SRC_C -->|"Guidance issued"| KAFKA
    MANUAL -->|"Document uploaded"| KAFKA

    KAFKA --> CONSUMER
    CONSUMER --> ES_INT
    ES_INT --> ELASTICSEARCH
    CONSUMER --> PIPELINE
    PIPELINE --> LITELLM

    LITELLM --> CLAUDE
    LITELLM --> OPENAI
    LITELLM --> BEDROCK
    LITELLM --> AZURE_OAI

    LITELLM --> MLFLOW
    PIPELINE --> MLFLOW
    MLFLOW --> S3
    PIPELINE --> PG

    PIPELINE --> GITHUB
    PIPELINE --> GITLAB
    PIPELINE --> BITBUCKET

    PIPELINE --> SLACK
    PIPELINE --> EMAIL
    PIPELINE --> WEBHOOK

    GHA --> CONSUMER
    GLCI --> CONSUMER
    JENKINS --> CONSUMER

    style KIT fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style REGULATORY_SOURCES fill:#e3f2fd,stroke:#1565c0
    style LLM_PROVIDERS fill:#f3e5f5,stroke:#6a1b9a
    style GIT_PROVIDERS fill:#fff3e0,stroke:#e65100
    style CICD fill:#fff9c4,stroke:#f57f17
```

### 5.2 Integration Reference Table

For detailed integration specifications including rate limits, retry strategies, and timeouts, see [`hld.md` Section 6.2](hld.md#62-integration-specification-table).

| Category | Integration | Protocol | Authentication | Notes |
|---|---|---|---|---|
| **Event Streaming** | Apache Kafka (Confluent, AWS MSK, self-hosted) | Kafka Protocol 2.x+ | SASL/SCRAM, mTLS | Schema Registry support for Avro/Protobuf events |
| **Event — Lightweight** | Webhook (HTTP POST) | REST (HTTPS) | Bearer Token, HMAC | Zero-dependency event ingestion for evaluation and small deployments |
| **Event — AWS** | Amazon SQS | AWS SDK | IAM Roles | For AWS-native organizations |
| **Search & Knowledge** | Elasticsearch 8.x | REST (HTTPS) | API Key, OAuth2 | Used for regulatory knowledge base and semantic search |
| **State & Checkpoints** | PostgreSQL 16+ | libpq | Username/Password, SSL | Durable pipeline state (Temporal + rak + mlflow schemas), repository progress |
| **LLM — Primary** | Anthropic Claude (claude-opus-4-5, claude-sonnet-4-6) | REST (HTTPS) | API Key | Default model for complex reasoning tasks |
| **LLM — Fallback** | OpenAI GPT-4o / GPT-4o-mini | REST (HTTPS) | API Key | Configurable fallback via LiteLLM routing |
| **LLM — Enterprise** | AWS Bedrock (Claude, Llama), Azure OpenAI | AWS SigV4, Azure AD | IAM Roles, Service Principal | For data residency requirements (mandatory for GDPR-scoped data) |
| **LLM Gateway** | LiteLLM Proxy | REST (HTTPS) | Bearer Token | Deployed behind load balancer with 2+ replicas |
| **Observability** | MLflow (self-hosted, PostgreSQL + S3) | REST (HTTPS) | Bearer Token | LLM traces, evaluations, cost tracking; local WAL for durability |
| **Metrics** | OpenTelemetry → Prometheus → Grafana | OTLP (gRPC/HTTP) | N/A | Operational metrics for pipeline health |
| **Git — GitHub** | GitHub Enterprise / Cloud | REST (HTTPS), GraphQL | GitHub App (short-lived tokens) | Clone, branch, PR creation, code search |
| **Git — GitLab** | GitLab Self-hosted / Cloud | REST (HTTPS) | Access Token (with expiry) | Clone, branch, MR creation |
| **Git — Bitbucket** | Bitbucket Data Center / Cloud | REST (HTTPS) | OAuth2 with refresh | Clone, branch, PR creation |
| **Notifications** | Slack | Webhooks / Bolt API | Bot Token | Checkpoint approvals, pipeline status |
| **Notifications** | Email | SMTP / SendGrid / SES | SMTP credentials / API Key | Compliance reports, approvals |
| **Notifications** | Generic Webhook | HTTP POST | Bearer Token | Jira ticket creation, PagerDuty alerts |
| **Storage** | AWS S3 / GCS / Azure Blob | SDK | IAM / Service Account | Immutable audit log storage |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins | Webhook / REST | Token | Shift-left compliance gates on PRs |
| **Secrets** | HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager | SDK | IAM / AppRole | Mandatory for production credential management |

### 5.3 Deployment Options

The framework supports multiple deployment models ranging from zero-infrastructure evaluation to production Kubernetes with full HA. For the canonical list of deployment options (including Lite Mode, Docker Compose, Kubernetes, and cloud-native configurations for AWS, GCP, and Azure), hardware sizing, and cloud-specific guides, see [`infrastructure.md`](infrastructure.md). For the architecture-level summary, see [`architecture.md` Section 11 — Deployment Options](architecture.md#11-deployment-options).

### 5.4 Analysis Scope — Beyond Application Code

The framework analyzes not just application source code but the full spectrum of artifacts in regulated environments:

| Asset Type | Examples | Regulatory Relevance | Phase |
|---|---|---|---|
| **Application code** | Java, Kotlin, Python | Primary compliance target | v1.0 |
| **API specifications** | OpenAPI 3.x, AsyncAPI | PSD2/Open Finance API contract compliance | v1.5 |
| **Infrastructure-as-Code** | Terraform (.tf), Pulumi | DORA ICT infrastructure documentation, encryption, backup policies | v1.5 |
| **Kubernetes manifests** | Deployments, NetworkPolicies | Security/resilience requirements (resource limits, network isolation) | v1.5 |
| **Build files** | pom.xml, build.gradle, package.json | Dependency management, compliance SDK injection | v1.0 |
| **CI/CD pipelines** | GitHub Actions, GitLab CI | Security scanning gates, audit logging requirements | v2.0 |
| **Go, TypeScript** | .go, .ts/.tsx | Polyglot fintech stacks | v2.0 |

---

## 6. Risk Analysis

### 6.1 Technical Risks

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| **Mid-pipeline crash losing state** | CRITICAL | HIGH | Temporal event-sourced state with automatic replay; per-repository progress tracking; idempotent operations with deterministic branch naming; `rak resume --run-id <id>` command |
| **Test execution as remote code execution vector** | CRITICAL | MEDIUM | Sandboxed execution in network-isolated containers (`--network=none --read-only`); static AST analysis of generated tests before execution; resource limits (CPU, memory, time) |
| **No rollback mechanism** | CRITICAL | HIGH | Every pipeline run generates a rollback manifest; `rak rollback --run-id <id>` closes PRs, deletes branches, creates revert PRs for merged changes |
| **LLM prompt injection via regulatory documents** | HIGH | MEDIUM | Input sanitization; structured output enforcement via Pydantic schemas; tool-level isolation (Analyzer gets read-only tools); human checkpoints as primary defense [see OWASP LLM Top 10] |
| **Concurrent regulation conflicts on same repos** | HIGH | MEDIUM | Temporal workflow ID uniqueness; deterministic child workflow IDs; conflict detection at PR creation |
| **Credential exposure via environment variables** | HIGH | HIGH | Mandatory secrets manager integration (Vault, AWS SM, GCP SM); short-lived Git tokens (GitHub App installation tokens expire in 1h); credential rotation without restart |
| **Temporal SDK version instability** | HIGH | MEDIUM | Exact version pinning; integration tests; internal `WorkflowEngine` abstraction for potential migration |
| **LLM response non-determinism across model versions** | HIGH | MEDIUM | Model version pinning; version logged in every audit trace; validation test suite per model+plugin combination |
| **No incremental analysis** | MEDIUM | HIGH | File-level caching via content hashing (`SHA256(content + plugin_version + agent_version)`); `git diff` based change detection; analysis results cached in PostgreSQL |

### 6.2 Security Architecture

The framework enforces eight security boundaries covering tool isolation, output validation, sandboxed execution, non-bypassable human review, credential management, data residency routing, cryptographic audit signing, and supply chain verification. For the full security architecture including threat mitigations and credential management, see [`architecture.md` Section 9 — Security Architecture](architecture.md#9-security-architecture).

### 6.3 Market & Strategic Risks

| Risk | Level | Mitigation |
|---|---|---|
| **GitHub Copilot / Amazon Q adding compliance features** | HIGH (18-24 month horizon) | Accelerate regulation plugin ecosystem — community-contributed coverage is the primary defensible moat. Neither GitHub nor Amazon is likely to build deep, regulation-specific plugins. |
| **Regulation-specific SaaS tools being "good enough"** | MEDIUM | Multi-regulation environments (the primary target) need a unified framework, not 5 separate tools. The plugin model's value increases with breadth. |
| **Open-source sustainability / maintainer burnout** | MEDIUM-HIGH | Transition to open-core model with enterprise features by v2.0; consulting revenue to bootstrap; consider LF AI & Data Foundation membership for governance continuity. |
| **LLM reliability and liability in regulated contexts** | HIGH | Non-bypassable human checkpoints; cryptographic signing of approvals; confidence scoring with configurable thresholds; explicit positioning as a tool, not decision-maker. |
| **Plugin ecosystem chicken-and-egg** | HIGH | Vertical wedge strategy: ship 3-5 official plugins (PCI-DSS, DORA, PSD2) before soliciting community contributions; partner with 2-3 design partners for early validation. |

### 6.4 Liability Positioning

> **regulatory-agent-kit is a developer tool that assists qualified professionals in identifying and implementing regulatory compliance changes. All outputs are suggestions that require human review and approval before taking effect. The framework does not provide legal, regulatory, or compliance advice. Users are responsible for validating all outputs against their organization's compliance requirements and applicable regulations.**

This positioning is reinforced architecturally:
- Checkpoints are **non-bypassable** in production mode
- Approvals are **cryptographically signed** and logged
- Changes are **diff-only** — the framework creates branches and MRs; the actual merge is a human action in the Git provider
- Confidence scoring flags uncertain changes for additional review
- Every regulation plugin carries a **mandatory disclaimer field**

---

## 7. Open Source Strategy

### 7.1 Licensing

**Apache 2.0** (not MIT). Apache 2.0 provides explicit patent protection from contributors — critical in financial services where patent trolls and large incumbents hold compliance automation patents. The Apache Individual CLA is implemented via CLA Assistant (GitHub App) before accepting external contributions, preserving the option to offer commercial licenses.

### 7.2 Governance Evolution

| Phase | Model | Decision Process |
|---|---|---|
| **Now — v1.5** | BDFL (founding team) | All decisions documented in ADRs |
| **v1.5 — v2.0** (5-15 contributors) | Technical Steering Committee (3-5 people) | Lightweight RFC process for significant changes |
| **Post v2.5** (if adoption warrants) | Foundation membership (LF AI & Data) | Neutral governance, trademark protection, enterprise credibility |

### 7.3 Community Strategy

**Persona-specific contribution paths:**

| Persona | First Contribution | Value They Bring |
|---|---|---|
| **Compliance Engineers** | Write a regulation YAML plugin; review existing plugins for regulatory accuracy; write Jinja2 templates | Domain expertise (they know the regulations) |
| **Platform Engineers** | Add Git provider integration; improve Helm chart; add notification channel; performance optimization | Infrastructure expertise |
| **Engineering Managers** | Write case studies; provide feedback on cost estimation; validate ROI claims | Market validation and advocacy |

**Plugin ecosystem strategy** (modeled on Terraform Registry, ESLint RuleTester):

1. `rak plugin init` — scaffold a new plugin with boilerplate YAML, test fixture, README
2. `rak plugin validate` — check YAML schema, verify templates exist, run against synthetic test repo
3. `rak plugin search` — discover community plugins from the registry
4. Plugin registry at v1.5 (GitHub repo with YAML index, like Homebrew formulas) — discoverability cannot wait until v2.5

**Plugin certification tiers:**

| Tier | Meaning | How Achieved |
|---|---|---|
| **Technically Valid** | Schema correct, templates render, tests pass | Automated CI validation |
| **Community Reviewed** | Reviewed by 2+ domain experts | Pull request review process |
| **Official** | Maintained by core team, versioned with regulation | Core team ownership, visually distinguished in registry |

Note: No "certified" tier. Certification implies legal liability that cannot be assumed.

### 7.4 Documentation Structure

Three persona-based tracks:

**Track 1: Compliance Engineers** — Plugin development guide, condition DSL reference, remediation strategy reference

**Track 2: Platform Engineers** — Architecture overview, deployment guides, configuration reference, custom agent development, observability setup

**Track 3: Engineering Managers** — Non-technical explainer, TCO analysis, security posture, risk assessment

**Tutorial progression:**
1. **"Hello World" (15 min):** Run example plugin in lite mode — no Kafka, no ES, just `pip install` and `rak run --lite`
2. **"Your First Plugin" (45 min):** Write a 3-rule YAML plugin, validate, run
3. **"Full Pipeline" (2 hours):** Docker Compose with full infrastructure, DORA plugin across multi-repo org
4. **"Production Deployment" (half day):** Kubernetes + Helm, RBAC, monitoring, audit retention
5. **"Custom Agent" (half day):** Write a custom agent class for complex remediation

### 7.5 Business Model

| Phase | Primary Revenue | Secondary | Timeline |
|---|---|---|---|
| **v1.0–v1.5** | Professional services (EUR 50–150k/engagement) | Community building | Now — Q3 2026 |
| **v2.0** | Open-core enterprise license (RBAC, SSO, advanced audit) | Consulting | Q3–Q4 2026 |
| **v2.5+** | Managed SaaS ("Compliance Pipeline as a Service") | Enterprise license + marketplace | Q1 2027+ |

**Open vs. Commercial:**

| Open (Apache 2.0) | Commercial (Proprietary) |
|---|---|
| Full agent pipeline | Multi-tenant SaaS |
| Plugin system + all official plugins | RBAC + fine-grained access controls |
| Temporal + PydanticAI orchestration | SSO/SAML integration |
| Single-tenant deployment | Advanced audit (cryptographic chaining, digital signatures, legal hold) |
| CLI + developer tooling | Cost forecasting + analytics dashboard |
| MLflow integration | GRC platform integrations (ServiceNow, Archer, OneTrust) |
| | Enterprise support SLAs |

---

## 8. Future Roadmap

### 8.1 Release Phases

```mermaid
gantt
    title regulatory-agent-kit — Product Roadmap
    dateFormat  YYYY-MM
    axisFormat  %b %Y

    section Phase 1 — Foundation (v1.0)
    Core agent framework (Analyzer, Refactor, TestGen, Reporter) :done, p1a, 2026-01, 2026-03
    Temporal + PydanticAI orchestration + PostgreSQL             :done, p1b, 2026-01, 2026-03
    Pluggable event sources (Kafka, Webhook, File)              :done, p1c, 2026-02, 2026-03
    LiteLLM gateway + MLflow observability                      :done, p1d, 2026-02, 2026-03
    GitHub + GitLab + Bitbucket integrations                    :done, p1e, 2026-02, 2026-03
    Regulation plugin system (YAML) + validation CLI            :done, p1f, 2026-01, 2026-03
    Lite mode (zero-infra evaluation)                           :done, p1g, 2026-03, 2026-03
    Docker Compose local stack                                  :done, p1h, 2026-03, 2026-03
    Sandboxed test execution                                    :done, p1i, 2026-03, 2026-03
    Cost estimation gate                                        :done, p1j, 2026-03, 2026-03

    section Phase 2 — Ecosystem (v1.5)
    Official plugins: PCI-DSS v4.0, DORA (all 5 pillars), PSD2:active, p2a, 2026-04, 2026-06
    Plugin registry + rak plugin search                         :p2b, 2026-04, 2026-05
    Helm chart for Kubernetes deployment                        :p2c, 2026-04, 2026-06
    GitHub Actions + GitLab CI shift-left integration           :p2d, 2026-05, 2026-06
    Cross-regulation dependency graph                           :p2e, 2026-05, 2026-07
    Plugin SDK + contributor documentation                      :p2f, 2026-05, 2026-07
    OpenAPI + Terraform + K8s manifest analysis                 :p2g, 2026-06, 2026-07
    Web-based approval UI                                       :p2h, 2026-06, 2026-08
    EU AI Act self-compliance assessment                        :p2i, 2026-06, 2026-08

    section Phase 3 — Intelligence (v2.0)
    Agent self-evaluation (MLflow evals integration)            :p3a, 2026-08, 2026-10
    Continuous monitoring mode (always-on compliance watch)     :p3b, 2026-08, 2026-11
    Enterprise features: RBAC, SSO, advanced audit              :p3c, 2026-08, 2026-10
    Cost forecasting per compliance cycle (pre-run forecast)    :p3d, 2026-09, 2026-11
    Multi-language AST support: Go, TypeScript, C#              :p3e, 2026-09, 2026-12
    Official plugins: EU AI Act, NIS2, MiCA, HIPAA, GDPR       :p3f, 2026-09, 2026-12

    section Phase 4 — Enterprise (v2.5)
    Multi-tenant SaaS deployment model                         :p4a, 2026-11, 2027-02
    Regulation plugin marketplace (community-contributed)       :p4b, 2027-01, 2027-03
    GRC platform integrations (ServiceNow, Archer, OneTrust)   :p4c, 2027-01, 2027-03
    Commercial support and SLA tiers                            :p4d, 2027-01, 2027-03
    Temporal Cloud managed backend (enterprise option)           :p4e, 2027-02, 2027-04
```

### 8.2 Roadmap Feature Detail

#### Phase 2 — Ecosystem (v1.5, Q2–Q3 2026)

| Feature | Rationale | Success Metric |
|---|---|---|
| **Official PCI-DSS v4.0 plugin** | Global applicability, unambiguous requirements, largest addressable market. The March 2025 enforcement deadline has passed — organizations are now in ongoing compliance maintenance and audit remediation, making the plugin more urgent, not less. | Adopted by 10+ organizations within 90 days |
| **Official DORA plugin (all 5 pillars)** | DORA applicable since January 2025; 22,000+ EU financial entities in scope [11] | Adopted by 10+ EU financial institutions within 90 days |
| **Plugin registry** | Discoverability is critical for ecosystem growth — cannot wait until v2.5 | 10+ community plugins within 6 months of launch |
| **Shift-left CI/CD integration** | Increases daily active usage and stickiness; captures "code change events" not just "regulatory change events" | Available as GitHub Action and GitLab CI component |
| **Cross-regulation dependency graph** | Practical necessity given DORA/NIS2/GDPR/AI Act overlap — elevated from research to roadmap | Conflicts detected and escalated in 100% of multi-regulation runs |
| **OpenAPI + Terraform analysis** | PSD2/Open Finance requires API contract compliance; DORA requires IaC documentation | Coverage of the two most common non-code regulatory surfaces |

#### Phase 3 — Intelligence (v2.0, Q3–Q4 2026)

| Feature | Rationale | Success Metric |
|---|---|---|
| **Agent self-evaluation** | LLM outputs must be measurably improving; current performance is a black box | Automated eval scores tracked per release in MLflow |
| **Enterprise features (RBAC, SSO)** | Required for enterprise adoption and open-core revenue model | First enterprise license sold within 60 days |
| **EU AI Act + NIS2 + MiCA plugins** | EU AI Act high-risk obligations fully applicable August 2026 [24]; NIS2 already in force; MiCA fully applicable since December 2024 | Complete coverage of major EU regulatory stack |
| **Go + TypeScript AST support** | Modern fintechs run polyglot stacks; Python + Java/Kotlin alone excludes 40%+ of potential users | Full analysis and refactoring capability |

#### Phase 4 — Enterprise (v2.5, Q4 2026–Q1 2027)

| Feature | Rationale | Success Metric |
|---|---|---|
| **Multi-tenant SaaS** | Consulting firms and RegTech vendors need to run on behalf of multiple clients | Pilot with 3+ compliance consulting firms |
| **Temporal Cloud managed backend** | Enterprise environments may prefer Temporal Cloud (managed SaaS) over self-hosted Temporal for reduced operational overhead | Available as managed backend option for enterprise deployments |
| **Commercial support** | Enterprise buyers require SLAs; open source cannot provide contractual guarantees | First paying support contract by Q1 2027 |

### 8.3 Research Directions

Beyond the planned roadmap, the following areas are under active investigation:

- **Formal verification of regulatory rules:** Expressing regulation plugins in a subset of Alloy or TLA+ to enable mathematical verification that a proposed code change fully satisfies a rule, not just heuristically [16].
- **Adversarial testing of generated changes:** Applying mutation testing to code modified by the Refactor Agent, specifically targeting compliance-critical paths, to detect cases where changes are syntactically correct but semantically incomplete [5].
- **Natural language interface for compliance officers:** Allowing non-engineers to query the system (*"Which of our services are not yet DORA-compliant with respect to ICT incident reporting?"*) and receive structured answers backed by the Elasticsearch knowledge base.
- **Supply chain compliance (EU CSRD, SEC climate disclosures):** Software systems that calculate, store, and report emissions/ESG metrics need code-level compliance with reporting formats (ESRS, XBRL). A CSRD plugin could validate data models, reporting endpoints, and audit logging.
- **Sanctions screening code compliance:** Verifying that all payment processing code pathways include OFAC/EU sanctions screening calls.
- **Accessibility compliance (WCAG/ADA):** Scanning frontend codebases for WCAG violations — a legal requirement in many jurisdictions.

---

## 9. References & Citations

### Academic Papers

| # | Reference | Relevance |
|---|---|---|
| [1] | Qian, C. et al. (2024). "ChatDev: Communicative Agents for Software Development." *ACL 2024*. DOI: 10.18653/v1/2024.acl-long.507 | Validates multi-agent collaboration for software development |
| [2] | Hong, S. et al. (2024). "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." *ICLR 2024*. arXiv:2308.00352 | SOPs as coordination mechanism; validates state machine approach |
| [3] | Jimenez, C. E. et al. (2024). "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" *ICLR 2024*. arXiv:2310.06770 | Benchmark for LLM-based code modification reliability |
| [4] | Wu, Q. et al. (2023). "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." arXiv:2308.08155 | Multi-agent conversation with human-in-the-loop |
| [5] | Liu, J. et al. (2024). "Is Your Code Generated by ChatGPT Really Correct?" *NeurIPS 2023*. arXiv:2305.01210 | LLM-generated code can pass tests while containing subtle bugs |
| [6] | Arner, D. W., Barberis, J., & Buckley, R. P. (2017). "FinTech, RegTech, and the Reconceptualization of Financial Regulation." *Northwestern J. of Int'l Law & Business*, 37(3), 371-413 | Foundational academic definition of RegTech |
| [7] | Alam, K. et al. (2022). "Regulation as Code: Opportunities and Challenges." *OECD Working Papers on Public Governance*, No. 54. DOI: 10.1787/9e587940-en | Validates regulation-as-configuration approach |
| [12] | Bader, J. et al. (2019). "Getafix: Learning to Fix Bugs Automatically." *OOPSLA*. DOI: 10.1145/3360585 | Production AST-based code fixes at scale (Meta) |
| [13] | Alon, U. et al. (2019). "code2vec: Learning Distributed Representations of Code." *POPL*. DOI: 10.1145/3290353 | Semantic representations from AST paths |
| [14] | Chakraborty, S. et al. (2022). "Deep Learning Based Vulnerability Detection." *IEEE TSE*, 48(9). DOI: 10.1109/TSE.2021.3087402 | AST-based methods more reliable for pattern detection |
| [15] | Meng, N. et al. (2013). "LASE: Locating and Applying Systematic Edits." *ICSE 2013*. DOI: 10.1109/ICSE.2013.6606596 | Learning systematic code edits from examples |
| [16] | Sadiq, S. et al. (2007). "Modeling Control Objectives for Business Process Compliance." *BPM 2007*. DOI: 10.1007/978-3-540-75183-0_11 | Formalizing compliance as verifiable predicates |
| [18] | Fitzgerald, B. et al. (2013). "Scaling Agile Methods to Regulated Environments." *ICSE 2013*. DOI: 10.1109/ICSE.2013.6606635 | Friction between agile and regulatory compliance |
| [19] | Rahman, A. et al. (2019). "The Seven Sins: Security Smells in IaC Scripts." *ICSE 2019*. DOI: 10.1109/ICSE.2019.00033 | Compliance-as-code paradigm for infrastructure |
| [21] | Amershi, S. et al. (2019). "Guidelines for Human-AI Interaction." *CHI '19*. DOI: 10.1145/3290605.3300233 | Design guidelines for human-AI oversight |
| [22] | Weisz, J. D. et al. (2023). "Toward General Design Principles for Generative AI Applications." *CHI '24*. DOI: 10.1145/3613904.3642466 | Verification mechanisms for AI-generated content |
| [23] | Vaithilingam, P. et al. (2022). "Expectation vs. Experience: Evaluating Code Generation Tools." *CHI EA '22*. DOI: 10.1145/3491101.3519665 | Developer trust in AI-generated code |
| [26] | Brundage, M. et al. (2020). "Toward Trustworthy AI Development." arXiv:2004.07213 | Mechanisms for verifiable AI claims and audit trails |
| [27] | Mitchell, M. et al. (2019). "Model Cards for Model Reporting." *FAT* '19*. DOI: 10.1145/3287560.3287596 | Standard for AI model documentation |
| [28] | Lins, S. et al. (2021). "Artificial Intelligence as a Service." *BISE*, 63(4). DOI: 10.1007/s12599-021-00708-w | Transparency requirements for AI services |

### Industry Reports

| # | Reference | Relevance |
|---|---|---|
| [8] | Deloitte (2023). "RegTech Universe 2023." *Deloitte Center for Regulatory Strategy* | 500+ RegTech companies mapped by category |
| [9] | McKinsey & Company (2020). "The Compliance Function of the Future." *McKinsey Risk & Resilience* | 50-70% of compliance activities automatable |
| [10] | BCG (2022). "Global Risk 2022." *BCG Global Risk Report* | Compliance costs grew 60% over preceding decade |

### Regulatory Sources

| # | Reference | URL |
|---|---|---|
| [11] | Regulation (EU) 2022/2554 — Digital Operational Resilience Act (DORA) | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554 |
| [17] | NIST SP 800-53 Rev. 5 — Security and Privacy Controls | DOI: 10.6028/NIST.SP.800-53r5 |
| [20] | ISO/IEC 27001:2022 — Information Security | https://www.iso.org/standard/27001 |
| [24] | Regulation (EU) 2024/1689 — EU Artificial Intelligence Act | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689 |
| [25] | NIST AI 100-1 — AI Risk Management Framework | DOI: 10.6028/NIST.AI.100-1 |
| — | NIS2 Directive (EU) 2022/2555 | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2555 |
| — | MiCA Regulation (EU) 2023/1114 | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114 |
| — | EBA DORA RTS/ITS | https://www.eba.europa.eu/activities/digital-finance/digital-operational-resilience-act-dora |
| — | BACEN Open Finance Brasil | https://openfinancebrasil.org.br/ |
| — | PCI Security Standards Council | https://www.pcisecuritystandards.org/document_library/ |

---

## Appendix A — Quick Start

```bash
# Install the framework
pip install regulatory-agent-kit

# Set up environment (minimum for lite mode)
export ANTHROPIC_API_KEY=your_key

# Run in lite mode — no Kafka, no Elasticsearch, no MLflow required
rak run --lite \
  --regulation regulations/examples/pci_dss_v4.yaml \
  --repos ./my-local-repo \
  --checkpoint-mode terminal

# --- Full deployment (production) ---

# Set up environment
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export ELASTICSEARCH_URL=http://localhost:9200
export DATABASE_URL=postgresql://rak:password@localhost:5432/rak

# Start local infrastructure
docker compose up -d  # Temporal, Elasticsearch, MLflow, PostgreSQL

# Run with full infrastructure
rak run \
  --regulation regulations/dora_ict.yaml \
  --repos https://github.com/your-org/service-a \
           https://github.com/your-org/service-b \
  --checkpoint-mode slack \
  --slack-channel "#compliance-approvals"

# Plugin development
rak plugin init --name my-regulation
rak plugin validate regulations/my-regulation.yaml
rak plugin search hipaa

# Pipeline management
rak status --run-id <id>
rak retry-failures --run-id <id>
rak rollback --run-id <id>
```

---

## Appendix B — Regulation Plugin Schema Reference

For the complete plugin YAML schema with all required and optional fields, see [`architecture.md` Section 12 — Plugin Schema Reference](architecture.md#12-plugin-schema-reference). A worked example using DORA is provided in [Section 4.2](#42-feature-1--regulation-as-yaml-plugin-system) of this document.

---

## Appendix C — Regulatory Timeline (2024–2027, Illustrative)

> **Note:** This timeline is provided for market context only. It highlights regulations relevant to early adopters and is not exhaustive. The framework supports any regulation from any jurisdiction via its plugin system. For regulation-specific details, see [`regulations/`](../regulations/README.md).

| Date | Event | Impact |
|---|---|---|
| 2024-06-30 | MiCA partially applicable | Stablecoin issuers subject to ICT requirements |
| 2024-08-01 | EU AI Act entered into force | Kit may be high-risk AI system; phased enforcement begins |
| 2024-10-17 | NIS2 transposition deadline | Financial entities in scope; DORA lex specialis relationship |
| 2024-12-30 | MiCA fully applicable | All crypto-asset service providers under full obligations |
| 2025-01-01 | Basel 3.1 / CRR3 application begins (EU) | Operational risk + ICT provisions for banking |
| 2025-01-17 | **DORA application date** | 22,000+ EU financial entities must comply |
| 2025-02-02 | EU AI Act: Prohibited AI practices (Article 5) | Certain AI uses in financial services banned |
| 2025-03-31 | **PCI-DSS v4.0 final deadline** | All future-dated requirements enforced; v3.2.1 retired |
| 2025-07-01 | APRA CPS 230 (Australia) | Operational risk management — analogous to DORA |
| 2025-08-02 | EU AI Act: GPAI model obligations | LLM providers face transparency requirements |
| 2026-08-02 | **EU AI Act: High-risk AI obligations** | Full conformity assessment if kit is classified high-risk |

---

---

## 10. Next Steps

| Your goal | Start here |
|---|---|
| Understand the architecture | [`architecture.md`](architecture.md) — framework contracts, plugin system, orchestration |
| Deploy and evaluate | [`getting-started.md`](getting-started.md) — 5-minute Lite Mode walkthrough |
| Write a regulation plugin | [`plugin-template-guide.md`](plugin-template-guide.md) — Jinja2 template authoring |
| Deploy to production | [`infrastructure.md`](infrastructure.md) — Docker, Kubernetes, AWS/GCP/Azure |

*Document maintained by the `regulatory-agent-kit` core team. For the application layer built on this framework, see [openfinance-agent](https://github.com/your-org/openfinance-agent).*

*This document incorporates findings from multi-agent research analysis covering regulatory landscape, competitive positioning, technical architecture, open-source strategy, and academic citations. All claims are sourced; see Section 9 for full references.*
