# Unimplemented Features Report — Second Audit

> **Date:** 2026-03-31
> **Scope:** All features in `docs/` cross-referenced against codebase in `src/regulatory_agent_kit/`
> **Previous audit:** `unimplemented-features-report-2026-03-29.md` (20 features — 19 implemented, 1 skipped)
> **Method:** Exhaustive read of all 14 doc files (architecture.md, sad.md, hld.md, lld.md, regulatory-agent-kit.md, cli-reference.md, infrastructure.md, data-model.md, local-development.md, getting-started.md, plugin-template-guide.md, glossary.md, all ADRs, all operations guides)

---

## Legend

| Status | Meaning |
|--------|---------|
| **IMPLEMENTED** | Gap identified and fully implemented |
| **ROADMAP** | Documented as an option but explicitly Phase 2 / not yet planned |

---

## Gaps Found and Resolved

### GAP-1: PDF Report Generation — IMPLEMENTED

**Doc references:** `architecture.md` §2, `hld.md` §5.1, `regulatory-agent-kit.md` §4

**Issue:** `ComplianceReportGenerator` produced only HTML reports. Documentation describes "compliance reports (PDF/HTML)" in the output layer.

**Resolution:** Added `_render_pdf()` to `ComplianceReportGenerator` with weasyprint-first strategy and built-in fallback using raw PDF 1.4 byte construction (no external dependency required). Updated `ReportArtefacts` to include `pdf_report_path`. 15 new tests.

---

### GAP-2: Custom Agent Remediation Strategy — IMPLEMENTED

**Doc references:** `architecture.md` §3.4

**Issue:** Plugin schema accepted `strategy: custom_agent` but no tool existed in `REFACTOR_TOOLS` to invoke user-defined agent classes.

**Resolution:** Added `invoke_custom_agent` async tool function to `agents/tools.py`. Dynamically loads Python classes by fully-qualified path, instantiates them, and calls `remediate()`. Added to `REFACTOR_TOOLS`. 9 new tests.

---

### GAP-3: Data Residency Router Integration — IMPLEMENTED

**Doc references:** `architecture.md` §6

**Issue:** `DataResidencyRouter` class existed but was never used by agent LLM calls. Pipeline activities used a hardcoded model regardless of jurisdiction.

**Resolution:** Updated `_resolve_model()` to accept `jurisdiction` and `content` parameters, instantiating `DataResidencyRouter` for region-based model selection. `_analyze_with_agent()` and `_refactor_with_agent()` now extract jurisdiction from `plugin_data`. PII detection triggers stricter primary-tier routing. 13 new tests.

---

## Documented but Not Implemented — Phase 2 Roadmap Items

These are deployment options listed in `architecture.md` §11 with no implementation. They appear to be roadmap items, not current-version features:

| Item | Description | Status |
|------|-------------|--------|
| Serverless deployment | Lambda + EventBridge | ROADMAP — no Lambda functions or EventBridge config |
| ECS + MSK deployment | Managed containers + managed Kafka on AWS | ROADMAP — no ECS task definitions or MSK config |
| PgBouncer connection pooling | Connection pooler for N > 3 workers | ROADMAP — user responsibility, no deployment guide |

These are **not gaps** — they are explicitly alternative deployment options for future phases.

---

## Remaining Known Gap

| Item | Status | Notes |
|------|--------|-------|
| DORA Regulation Plugin | SKIPPED | Excluded per user instructions in the 2026-03-29 audit |

---

## Verification

- **Full test suite:** 1111 tests passing, 0 failures
- **Lint:** All files pass `ruff check`
- **All 22 features** from both audits are implemented (19 from first audit + 3 from this audit)
