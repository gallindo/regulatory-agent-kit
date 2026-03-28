# Documentation Pedagogical & Navigability Audit

**Project:** regulatory-agent-kit
**Scope:** `docs/` directory — 11 primary documents + 6 ADRs
**Date:** 2026-03-28
**Auditor Role:** Senior Technical Writer & Developer Advocate

---

## 1. Executive Summary

**Overall health: 7.5/10** — technically comprehensive but pedagogically uneven.

**Strengths:** Consistent layered architecture (Why -> What -> How), excellent use of Mermaid diagrams and tables, strong cross-referencing between docs, and all documents have clear purpose statements. The documentation covers an impressive breadth of system design at every abstraction level.

**Core weaknesses:**

- **No entry ramp for newcomers.** There is no standalone "Getting Started" guide. A new developer must navigate a 1,000-line product requirements doc before running anything. The quickest path to a working demo (`rak run --lite`) is buried in `infrastructure.md` Section 8.5.
- **Assumed domain knowledge.** ~30 technical terms (Temporal, PydanticAI, tree-sitter, AST, JSON-LD, OTLP, event sourcing) and ~15 regulatory acronyms (DORA, PSD2, RTS/ITS, ICT) are used without definition on first mention.
- **Anchor links are fragile.** 29 cross-document anchor links are broken or fragile — they assume specific heading-to-anchor slugification that varies by renderer.
- **Terminology drift.** "merge request" vs "pull request" (9 vs 3), "checkpoint" vs "approval gate" vs "human gate" (48 vs 7), and others create low-level confusion.

---

## 2. High-Level Structural Changes

### 2.1 Create a `docs/getting-started.md` (new file)

**Problem:** The fastest path to a working demo is scattered across `infrastructure.md` Section 8.5, `cli-reference.md` lines 34-39, and `architecture.md` lines 645-669. A newcomer must read 3 docs to run their first pipeline.

**Solution:** Create a focused ~100-line guide:

1. What is regulatory-agent-kit? (3 sentences)
2. Prerequisites (Python 3.12+, LLM API key)
3. Install & run in 5 minutes (`rak run --lite`)
4. Understand what just happened (pipeline stages explained simply)
5. Next steps by role (links to architecture.md, plugin-template-guide.md, infrastructure.md)

### 2.2 Create a `docs/glossary.md` (new file)

**Problem:** Every review pass flagged undefined jargon as a top issue. Terms like "event sourcing," "AST," "tree-sitter," "OTLP," "JSON-LD," "Jinja2 SandboxedEnvironment," and regulatory acronyms (DORA, PSD2, ICT, RTS/ITS, RTO/RPO) appear without definition.

**Solution:** A single glossary defining ~40 terms, organized alphabetically. Each doc's frontmatter would link to it: `> **Glossary:** Unfamiliar terms? See [glossary.md](glossary.md)`.

### 2.3 Reorder `infrastructure.md` — Lite Mode first

**Problem:** Lite Mode (the quickest evaluation path) is Section 8.5 — the 938th line. New users evaluating the tool won't find it.

**Solution:** Move Lite Mode to Section 1.2 or 2, before cloud topologies. Rename: "Quick Evaluation (Lite Mode)" then "Production Deployment" sections follow.

### 2.4 Add role-based reading paths to `README.md`

**Problem:** The reading order table is audience-labeled but doesn't provide explicit paths. A new platform engineer doesn't know whether to read `hld.md` or `infrastructure.md` first.

**Solution:** Add a "Quick Paths" section after the table:

- **Evaluating the tool?** `getting-started.md` -> `architecture.md`
- **Building a regulation plugin?** `architecture.md` SS3, SS12 -> `plugin-template-guide.md`
- **Deploying to production?** `hld.md` -> `infrastructure.md` -> `operations/runbook.md`
- **Implementing features?** `architecture.md` -> `sad.md` -> `lld.md` -> `data-model.md`

---

## 3. Specific File Feedback

### 3.1 `docs/README.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | Opens with "The documentation is organized in layers..." — assumes reader already knows what the project is. | Add a one-sentence project definition before the reading order table. |
| 2 | "ADR", "DRY", "C4 model" used without expansion. | Expand on first mention: "ADR (Architecture Decision Record)", "DRY (Don't Repeat Yourself)", "C4 (Context, Container, Component, Code)". |
| 3 | No explicit entry point guidance per role. | Add role-based reading paths (see SS2.4 above). |
| 4 | Supplementary Documents table missing proposed new files. | Add `getting-started.md` and `glossary.md` when created. |

### 3.2 `docs/regulatory-agent-kit.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | 15+ regulatory acronyms (DORA, PSD2, BACEN, SOX, HIPAA, NIS2, MiCA, ICT, RTS/ITS, RTO/RPO, LGPD, GDPR, etc.) appear without expansion in Sections 1-2. | Expand each on first occurrence: "DORA (Digital Operational Resilience Act)", "PSD2 (Payment Services Directive 2)", etc. |
| 2 | Executive Summary (lines 44-56) packs 5 ideas into 2 sentences: problem statement, research citation, multi-agent approach, event architecture, observability. | Break into shorter paragraphs, one idea each. |
| 3 | Key technologies introduced without parenthetical definitions in Section 4: Temporal, PydanticAI, tree-sitter, MLflow, Elasticsearch. | Add brief inline definitions on first mention: "Temporal (a distributed workflow engine)", "PydanticAI (a typed Python agent framework)", etc. |
| 4 | Document ends with References (Section 9) — no forward guidance for the reader. | Add a "Next Steps" footer: "For implementation details, see `architecture.md`. For deployment, see `infrastructure.md`." |
| 5 | Line 1066: `[CONTRIBUTING.md](CONTRIBUTING.md)` links to a file that does not exist. | Remove the link or create the file. |

### 3.3 `docs/architecture.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | System Architecture diagram (Section 2) introduces 7 layers by technical name only. A reader unfamiliar with Temporal or tree-sitter can't parse it. | Add plain-English layer descriptions below the diagram: "The **Input Layer** receives regulatory change events and loads the YAML rules. The **Agent Layer** contains four AI agents that analyze, refactor, test, and report..." |
| 2 | Temporal-specific terms ("Signal", "Activity") used in Section 4 without definition. | Define on first use: "Temporal Signal (a durable message sent to a running workflow to trigger a state change, e.g., an approval decision)", "Activity (a Temporal unit of work that can be retried and timed out independently)". |
| 3 | Security acronyms in Section 9 unexplained: WAL, SBOM, Ed25519, Sigstore/cosign. | Expand: "WAL (Write-Ahead Log)", "SBOM (Software Bill of Materials)", "Ed25519 (an elliptic-curve digital signature scheme)". |
| 4 | No "Next Steps" section at the bottom. | Add role-based guidance: "Implementing agents? `lld.md`. Deploying? `infrastructure.md`. Writing plugins? `plugin-template-guide.md`." |
| 5 | Agent naming inconsistency: "Analyzer Agent" (prose) vs "AnalyzerAgent" (code) vs "analyzer agent" (lowercase). | Standardize: "Analyzer Agent" (capitalized, two words) in prose; "AnalyzerAgent" only in code blocks and class diagrams. |

### 3.4 `docs/sad.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | Temporal, PydanticAI, LiteLLM, and tree-sitter are first used in Sections 8-11 without any prior introduction. | Add a brief "Technology Primer" (3-4 paragraphs) after Section 3 (Architectural Decisions), introducing each dependency in 2-3 sentences. |
| 2 | The 74-line Temporal workflow code example (Section 8.2, lines 792-851) is a single uninterrupted Python block. | Break into 3-4 labeled subsections with explanatory text between each (e.g., "Step 1: Cost Estimation", "Step 2: Fan-out to Repositories", etc.). |
| 3 | Architectural goals table (Section 1.3) lists 15 goals in a flat table — hard to scan. | Group by category: Reliability (AG-1, AG-2, AG-7), Security (AG-3, AG-4), Scalability (AG-5, AG-8, AG-10), Usability (AG-6, AG-9), etc. |
| 4 | Sections end abruptly without forward references. | Add "See Also" cross-references at the end of each major section. Example: after Section 9 (Agent Contracts), add "For agent class hierarchies and tool isolation matrices, see `lld.md` Section 2.4." |
| 5 | Header says audience is "Architects, senior engineers" but content spans from C4 diagrams (conceptual) to DDL (implementation). | Clarify that Sections 1-6 target architects while Sections 7+ target implementing engineers. |

### 3.5 `docs/hld.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | Kubernetes-heavy document uses Pods, Deployments, StatefulSets, Namespaces, Ingress, PVC, HPA, NetworkPolicy without definitions. | Add a 3-paragraph Kubernetes primer early in the document (or link to glossary.md). |
| 2 | Hardware sizing (Section 3) says "4 cores, 8 GB RAM" but doesn't connect sizing to throughput. | Add worked examples: "At this sizing, one worker processes ~X repositories/hour." |
| 3 | No visual showing when to graduate between deployment tiers. | Add a "Deployment Ladder" diagram: Lite Mode -> Docker Compose -> Kubernetes, with criteria for graduating. |
| 4 | "Replica" vs "instance" used interchangeably (line 145 "2 replicas" vs line 316 "1+1 standby instances"). | Standardize terminology. |
| 5 | No "Related Docs" header. | Add links to `infrastructure.md` (detailed configs) and `operations/runbook.md` (failure recovery). |

### 3.6 `docs/lld.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | The 113-line DDL block (Section 5.1) is a single SQL code block — hard to scan for a specific table. | Break into per-table subsections with commentary between each. |
| 2 | Pydantic v2 used throughout (`BaseModel`, `model_validate()`, `Literal` types, validators) without explaining what Pydantic is. | Add a 2-paragraph Pydantic v2 primer at the start of Section 2. |
| 3 | Error Handling (Section 7) is the last section, implying it's an afterthought. | Move earlier — after Class Diagrams (Section 2). Error handling is critical for understanding system behavior. |
| 4 | Condition DSL (Section 6.1) shows grammar and parser pseudocode but no usage examples. | Add: "Given this condition string `class implements ICTService AND has_annotation(@AuditLog)`, here's how it's parsed and evaluated." |
| 5 | Mermaid diagrams lack captions/figure numbers — impossible to reference from other documents. | Add figure captions: "**Figure 1:** Domain model class hierarchy". |

### 3.7 `docs/data-model.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | JSON-LD format appears in every JSONB payload schema (`@context`, `@type`) but is never defined or motivated. | Add on first use (Section 5): "JSON-LD (JSON for Linked Data) gives each audit event a self-describing schema, enabling cross-system compatibility and semantic querying." |
| 2 | PostgreSQL partitioning used extensively without explaining what it is. | Before Section 8 DDL, explain: what partitioning is, why it's needed (audit_entries grows unbounded), and trade-offs (no cross-partition FKs). |
| 3 | Alembic introduced in Section 9 without context. | Add 2-3 sentences: "Alembic is a database migration tool for SQLAlchemy/PostgreSQL. It tracks schema changes as versioned Python scripts, enabling forward-only migrations with rollback safety." |
| 4 | Full ERD (Section 2.1) is thorough but overwhelming for a first look. | Add a simplified "quick reference" ERD at the top showing only table names and relationships (no columns). |
| 5 | Retention policies (Section 8) state durations but don't explain why. | Link to regulatory context: "12-month default aligns with common regulatory retention requirements; permanent audit archives satisfy EU AI Act Article 12 record-keeping mandates." |

### 3.8 `docs/cli-reference.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | No purpose statement. Opens directly with the `rak` entry point. | Add: "This reference documents all CLI commands for running compliance pipelines, managing regulation plugins, and operating the framework." |
| 2 | No example of `rak status` output. Documents the command but not what the reader will see. | Add a sample output block showing pipeline state, per-repo progress, and cost tracking. |
| 3 | "Checkpoint" and "regulation plugin" used without definition (lines 27, 12). | Define inline on first use or link to glossary. |
| 4 | No "Quick Start" box for the simplest possible invocation. | Add the Lite Mode 3-liner at the top, before Pipeline Commands. |
| 5 | No "See Also" footer. | Add links to `plugin-template-guide.md`, `infrastructure.md` Section 8.5, and `operations/runbook.md`. |

### 3.9 `docs/plugin-template-guide.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | Jumps into template context variables without motivation. No end-to-end walkthrough. | Add Section 1: "Create your first template in 10 minutes." Show the full cycle: rule YAML -> template -> test -> validate. |
| 2 | "ASTRegion" and "tree-sitter node type" used on line 36 without any definition. | Define AST, tree-sitter, and Jinja2 on first mention (or link to glossary). |
| 3 | Remediation strategies (add_annotation, add_configuration, replace_pattern, add_dependency, generate_file) shown as templates but never explained conceptually. | Add a section before the examples: what each strategy does, when to use each, and how they differ. |
| 4 | No troubleshooting section. | Add common template errors: undefined variables, sandbox violations, rendering failures. |
| 5 | No links to working examples. | Add "See Also" links to `regulations/dora/templates/` for real-world examples. |

### 3.10 `docs/operations/runbook.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | All failure scenarios presented equally — no severity/urgency classification. | Add a severity matrix at the top: "**Critical (auto-pages):** PostgreSQL Down, Temporal Server Crash. **Warning (Slack only):** High LLM latency, elevated failure rate." |
| 2 | No expected recovery times. | Add "Expected Recovery Time" to each scenario (e.g., "Worker crash: auto-recovers in <30s via Temporal replay"). |
| 3 | No escalation paths. | Add: "If this runbook step doesn't resolve the issue, escalate to [team/channel]." |
| 4 | No link to monitoring setup. | Link to `infrastructure.md` Section 11 so SREs can set up the alerts that detect these failures. |
| 5 | No "Healthy Baseline" section. | Add normal metric values so SREs can identify degradation (e.g., "Normal: <2s LLM latency, <5% repo failure rate, activities/min 50-200"). |

### 3.11 `docs/infrastructure.md`

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | Lite Mode is Section 8.5 (line 938). Evaluators won't find it. | Move to Section 2, before cloud topologies. Rename: "Quick Evaluation (Lite Mode)". |
| 2 | Section 1.1 lists deployment options but doesn't help readers choose. | Add a "Deployment Decision Matrix" with columns: Setup Time, Monthly Cost, Ops Burden, Learning Curve. |
| 3 | Lite Mode Feature Parity table (Section 8.5.1) uses jargon: "event-sourced", "durable", "concurrent writers". | Add inline definitions for the evaluation audience who may not know these terms. |
| 4 | Subsection 8.5 missing from the Table of Contents. | Add it. |
| 5 | No link to operational procedures. | Add "See Also" linking to `operations/runbook.md` for failure recovery and maintenance. |

### 3.12 ADRs (all 6)

| # | Finding | Recommendation |
|---|---------|----------------|
| 1 | ADR-002 and ADR-005 use the most unexplained jargon: "event sourcing," "workflow replay," "OTLP," "OTel bridge," "ClickHouse." | Add a "Definitions" footer to each with 5-6 key terms. |
| 2 | ADR-006 alternative analysis is shallower than other ADRs — OpenSearch and pgvector dismissed briefly. | Expand with more quantitative comparison. |
| 3 | ADR-005 line 352 says "update ADR-004's L19 section to replace Langfuse with MLflow" — not yet done. | Resolve the forward dependency: update ADR-004 or remove the requirement from ADR-005. |
| 4 | Several pseudocode blocks in ADR-002 lack `python` language tags. | Add language annotations for syntax highlighting. |
| 5 | Comparison matrix format varies: ADR-001 uses weighted scoring, ADR-002 uses verdict tables, ADR-005 uses feature grids. | Pick one format and use consistently, or note the intentional variation. |

---

## 4. Quick Wins (Fix Immediately)

### 4.1 Broken Links

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `regulatory-agent-kit.md` | 1066 | `[CONTRIBUTING.md](CONTRIBUTING.md)` — file does not exist | Remove link or create the file |
| Multiple files | various | 29 anchor links use `#section-heading` slugs that may not resolve across renderers | Verify anchors in target renderer; consider using "Section X" text references as fallback |

### 4.2 Terminology Standardization (7 instances)

| File | Current Term | Replace With |
|------|-------------|-------------|
| `adr/001` lines 21, 87, 117, 148 | "human gate" / "approval gate" | "checkpoint" |
| `regulatory-agent-kit.md` lines 47, 392 | "approval gate" | "checkpoint" |
| `hld.md` line 1016 | "human gate" | "checkpoint" |

### 4.3 MR/PR Standardization

The docs mix "merge request" (9 occurrences), "pull request" (3), "MR" (4), and "PR" (17) without pattern. Since the framework supports multiple Git providers, adopt a policy:

- **In architecture/framework docs:** use "merge/pull request" (provider-agnostic) on first mention, then "MR/PR" as shorthand
- **In provider-specific contexts:** use the provider's term (GitHub = PR, GitLab = MR)

### 4.4 Missing "See Also" Footers

Add to every document that lacks one (1-3 lines each):

| File | Add Links To |
|------|-------------|
| `cli-reference.md` | `plugin-template-guide.md`, `infrastructure.md`, `operations/runbook.md` |
| `plugin-template-guide.md` | `regulations/dora/`, `cli-reference.md`, `architecture.md` SS12 |
| `hld.md` | `infrastructure.md`, `operations/runbook.md` |
| `data-model.md` | `lld.md`, `operations/runbook.md` (for partition maintenance) |

### 4.5 Code Block Language Tags

| File | Issue |
|------|-------|
| `adr/002` | 4 pseudocode blocks lack `python` language annotation |

---

## 5. Terminology Consistency Audit

| Category | Dominant Term (count) | Variants Found (count) | Status | Action |
|----------|----------------------|----------------------|--------|--------|
| Plugin | "regulation plugin" (17) | "YAML plugin" (12) | Minor | Acceptable. Use "regulation plugin" as primary; "YAML plugin" as format-specific variant. |
| Checkpoint | "checkpoint" (48) | "approval gate" (3), "human gate" (4) | **Fix** | Standardize to "checkpoint" everywhere. Replace 7 instances. |
| Pipeline | "pipeline run" (16) | "pipeline execution" (3) | Acceptable | Intentional distinction: "run" = specific instance, "execution" = generic concept. |
| Agent names | "Analyzer Agent" (20) | "AnalyzerAgent" (3), "analyzer agent" (20) | Minor | Use "Analyzer Agent" in prose; "AnalyzerAgent" in code only. |
| Git operations | "merge request" (9) | "pull request" (3), "MR" (4), "PR" (17) | **Fix** | Adopt provider-agnostic policy (see SS4.3). |
| Orchestration | "Temporal workflow" (28) | "workflow" (122), "pipeline" (93) | Clarify | Define in glossary: "Temporal workflow" = technical construct; "pipeline" = end-to-end compliance process. |

---

## 6. Per-Document Quality Matrix

| Criterion | README | reg-agent-kit | architecture | sad | hld | lld | data-model | cli-ref | plugin-guide | runbook | infrastructure |
|-----------|--------|--------------|-------------|-----|-----|-----|-----------|---------|-------------|---------|---------------|
| Clear "Why" | Good | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Partial | Good | Excellent | Good |
| Simple->Complex Flow | Excellent | Strong | Excellent | Strong | Excellent | Very Strong | Excellent | Good | Good | Excellent | Excellent |
| Jargon Defined | Minor gaps | Moderate gaps | Moderate gaps | Minor gaps | Minor gaps | Moderate gaps | Minor gaps | Gaps | Significant gaps | Minor gaps | Significant gaps |
| Code Examples | N/A | Strong | Excellent | Very Good | Very Good | Excellent | Excellent | Good | Good | Excellent | Good |
| See Also / Next Steps | Implicit | Missing | Strong | Missing | Partial | Good | Good | Missing | Partial | Good | Partial |
| ToC Accuracy | N/A | Accurate | Accurate | Accurate | Accurate | Accurate | Accurate | Good | Good | Good | Good (gap: SS8.5) |
| Cross-References | Excellent | Strong | Strong | Strong | Good | Strong | Strong | Partial | Partial | Good | Excellent |
| Paragraph Density | None | Several dense | Minor | Some dense | Excellent | Some dense | Excellent | Good | Good | Good | Good |
| Term Consistency | Excellent | Minor issues | Minor issues | Very Good | Minor issues | Very Good | Very Good | Issues | Minor | Excellent | Minor |
| Newcomer Context | Gap (no intro) | Moderate gaps | Moderate gaps | Moderate gaps | Moderate gaps | Moderate gaps | Moderate gaps | Significant gaps | Major gaps | Moderate gaps | Major gaps |

---

## 7. Priority Action Plan

### Tier 1 — Immediate (Quick Wins)

- [ ] Fix broken `CONTRIBUTING.md` link in `regulatory-agent-kit.md`
- [ ] Standardize 7 "approval gate" / "human gate" instances to "checkpoint"
- [ ] Add `python` language tags to 4 code blocks in `adr/002`
- [ ] Add "See Also" footers to `cli-reference.md`, `plugin-template-guide.md`, `hld.md`, `data-model.md`

### Tier 2 — High Impact (Structural)

- [ ] Create `docs/getting-started.md` with 5-minute Lite Mode walkthrough
- [ ] Create `docs/glossary.md` with ~40 term definitions
- [ ] Move Lite Mode from `infrastructure.md` Section 8.5 to Section 2
- [ ] Add role-based reading paths to `README.md`
- [ ] Add technology primers to `sad.md` and `lld.md`

### Tier 3 — Medium Impact (Per-Document)

- [ ] Expand regulatory acronyms in `regulatory-agent-kit.md` Sections 1-2
- [ ] Add plain-English layer descriptions to `architecture.md` Section 2
- [ ] Break 74-line workflow code block in `sad.md` Section 8.2
- [ ] Break 113-line DDL block in `lld.md` Section 5.1
- [ ] Add severity matrix to `operations/runbook.md`
- [ ] Add deployment decision matrix to `infrastructure.md` Section 1
- [ ] Add end-to-end walkthrough to `plugin-template-guide.md`
- [ ] Add sample output to `rak status` in `cli-reference.md`
- [ ] Resolve ADR-005 -> ADR-004 forward dependency

### Tier 4 — Polish

- [ ] Add figure captions to all Mermaid diagrams in `lld.md`
- [ ] Standardize ADR comparison matrix format
- [ ] Add Kubernetes primer to `hld.md`
- [ ] Add worked sizing examples to `hld.md` Section 3
- [ ] Expand ADR-006 alternative analysis
- [ ] Add MR/PR standardization policy note and apply across all docs
