# DORA — Digital Operational Resilience Act

### Plugin Documentation for Regulation (EU) 2022/2554

> **Regulation:** Digital Operational Resilience Act (DORA)
> **Full Citation:** Regulation (EU) 2022/2554 of the European Parliament and of the Council
> **Jurisdiction:** European Union
> **Authority:** European Banking Authority (EBA), ESMA, EIOPA (Joint Committee)
> **Application Date:** 17 January 2025
> **Official Text:** [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554)
> **Entities in Scope:** ~22,000 EU financial entities and ICT third-party service providers

---

## Overview

DORA establishes a comprehensive framework for the digital operational resilience of EU financial entities. It entered into force on 16 January 2023 and became applicable on **17 January 2025**. DORA applies to credit institutions, investment firms, insurance undertakings, payment institutions, crypto-asset service providers (under MiCA), and their critical ICT third-party service providers.

The `regulatory-agent-kit` DORA plugin suite provides automated detection, analysis, and remediation of DORA compliance issues across codebases. The suite is organized around DORA's five regulatory pillars.

---

## Five Pillars

DORA is structured around five pillars, each with distinct technical requirements:

| Pillar | DORA Articles | Key Requirements | Plugin ID | Automation Potential |
|---|---|---|---|---|
| **1. ICT Risk Management** | Articles 5–16 | ICT risk management framework, governance, asset identification, protection & prevention, detection, response & recovery | `dora-ict-risk-2025` | **HIGH** — Service manifest scanning, security config validation, dependency auditing |
| **2. ICT Incident Reporting** | Articles 17–23 | Incident classification, reporting timelines (initial: 4h, intermediate: 72h, final: 1 month), root cause analysis | `dora-incident-reporting-2025` | **HIGH** — Incident classification code, reporting pipeline validation, timeline enforcement |
| **3. Digital Operational Resilience Testing** | Articles 24–27 | Regular testing of ICT systems, threat-led penetration testing (TLPT) for significant entities | `dora-resilience-testing-2025` | **MEDIUM** — TestGenerator validates resilience test coverage; cannot replace actual penetration testing |
| **4. ICT Third-Party Risk Management** | Articles 28–44 | Due diligence on ICT third-party providers, contractual requirements, concentration risk monitoring, oversight of critical CTPPs | `dora-third-party-risk-2025` | **MEDIUM** — Dependency analysis across repos, third-party library auditing, contract clause validation |
| **5. Information Sharing** | Article 45 | Voluntary sharing of cyber threat intelligence among financial entities | N/A | **LOW** — Architectural support (event topics for threat intel sharing) but limited direct automation |

---

## Regulatory Technical Standards (RTS) and Implementing Technical Standards (ITS)

The ESAs have published detailed Level 2 standards that provide the concrete technical requirements. These are where the actual compliance engineering work lives:

| Standard | Identifier | Subject | Relevance to Plugin |
|---|---|---|---|
| RTS on ICT risk management framework | JC 2023 86 | Detailed policies, procedures, protocols for ICT risk | Primary source for Pillar 1 rules |
| RTS on classification of ICT incidents | JC 2023 83 | Materiality thresholds, classification criteria | Primary source for Pillar 2 rules |
| RTS on incident reporting content/timelines | — | Exact data fields for regulatory reports | Validates reporting code |
| RTS on TLPT | — | Threat-led penetration testing (based on TIBER-EU) | Validates testing infrastructure |
| RTS on ICT third-party policy | — | Subcontracting chains, exit strategies, audit rights | Validates dependency management |
| ITS on registers of information | — | Standardized templates for ICT third-party arrangements | Validates documentation artifacts |

**Plugin design principle:** Each rule in the DORA plugins references a specific RTS/ITS where applicable, not just the Level 1 regulation text. This ensures rules map to concrete, code-checkable requirements.

---

## Cross-Regulation Dependencies

DORA does not exist in isolation. The following cross-references are encoded in the plugin's `cross_references` field:

| Referenced Regulation | Relationship | DORA Article | Practical Implication |
|---|---|---|---|
| **GDPR** | `does_not_override` | Art. 2(3) | DORA's audit logging requirements must be balanced against GDPR data minimization. Conflicts are escalated to human review. |
| **NIS2** | `takes_precedence` | Art. 1(2) | DORA prevails for financial entities. NIS2 rules are suppressed for entities in DORA scope to prevent duplicate remediations. |
| **PSD2 / PSD3** | `complementary` | Art. 2(1)(a) | Payment service providers are subject to both. Both regulation plugins run in parallel. |
| **MiCA** | `complementary` | — | Crypto-asset service providers under MiCA are subject to DORA ICT requirements. |
| **CRR3 / Basel III** | `references` | — | Operational risk framework alignment. DORA provides the ICT-specific detail. |
| **EU AI Act** | `references` | — | AI systems used in ICT risk management may be subject to the AI Act. Plugin flags AI components for AI Act review. |

---

## Enforcement Architecture

| Entity Type | Enforced By | Penalty Structure |
|---|---|---|
| **Financial entities** (banks, insurers, investment firms) | National Competent Authorities (NCAs) — e.g., BaFin (DE), AMF/ACPR (FR), DNB (NL) | Administrative penalties determined by each member state's national law |
| **Critical ICT third-party service providers (CTPPs)** | Lead Overseer (EBA, ESMA, or EIOPA) | Periodic penalty payments of up to **1% of average daily worldwide turnover** per day of non-compliance, for up to 6 months (Article 35(8)) |

---

## Plugin Example

```yaml
# regulations/dora/dora-ict-risk-2025.yaml
id: "dora-ict-risk-2025"
name: "DORA ICT Risk Management Requirements"
version: "1.0.0"
effective_date: "2025-01-17"
jurisdiction: "EU"
authority: "European Banking Authority"
source_url: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554"

regulatory_technical_standards:
  - id: "JC-2023-86"
    name: "RTS on ICT risk management framework"
    url: "https://www.eba.europa.eu/activities/digital-finance/digital-operational-resilience-act-dora"

cross_references:
  - regulation_id: "gdpr"
    relationship: "does_not_override"
    articles: ["2(3)"]
    conflict_handling: "escalate_to_human"
  - regulation_id: "nis2"
    relationship: "takes_precedence"
    articles: ["1(2)"]
  - regulation_id: "psd2"
    relationship: "complementary"
    articles: ["2(1)(a)"]

rules:
  - id: "DORA-ICT-001"
    description: "All ICT systems must implement structured logging for audit purposes"
    severity: "critical"
    # DORA-specific extension fields (not part of core schema)
    dora_pillar: "ict_risk_management"
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
      confidence_threshold: 0.85

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

supersedes: null
changelog: "Initial release aligned with DORA application date 2025-01-17"

disclaimer: >
  This plugin represents one interpretation of Regulation (EU) 2022/2554 (DORA).
  It does not constitute legal advice. Organizations must validate compliance
  with their own legal and compliance teams.

event_trigger:
  topic: "regulatory-changes"
  schema:
    regulation_id: "dora-ict-risk-2025"
    change_type: "new_requirement"
```

Note: `dora_pillar` and `rts_reference` are **DORA-specific extension fields**, not part of the generic plugin schema. They are passed through to Jinja2 templates and reports.

---

## References

- Regulation (EU) 2022/2554 (DORA): [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554)
- EBA DORA Implementation Hub: [EBA](https://www.eba.europa.eu/activities/digital-finance/digital-operational-resilience-act-dora)
- European Commission DORA Impact Assessment: [SWD(2020)198](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=SWD:2020:198:FIN)

---

*This document describes the DORA-specific plugin. For the framework architecture (regulation-agnostic), see [`docs/architecture.md`](../../docs/architecture.md). For the plugin schema and contribution guide, see [`regulations/README.md`](../README.md).*
