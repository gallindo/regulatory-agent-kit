  What's needed before going live

  Blockers (must fix before announcing)

  ┌─────┬─────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  #  │                 Gap                 │                                                Fix                                                │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 1 ✓ │ DONE — MIT LICENSE file added        │ LICENSE created at repo root (commit 184c287); GitHub now auto-detects MIT                         │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 2 ✓ │ DONE — CONTRIBUTING.md added         │ Full guide: dev setup, code standards, testing, PR workflow, plugin authoring (commit 50e4b06)    │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 3 ✓ │ DONE — [project.urls] added          │ Homepage, Repository, Documentation, Issues, Changelog links added to pyproject.toml              │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 4 ✓ │ DONE — release.yml workflow added    │ Tag push v*.*.* builds sdist+wheel, creates GitHub Release, publishes to PyPI via OIDC            │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 5 ✓ │ DONE — issue and PR templates added  │ bug_report.yml, feature_request.yml, config.yml (security/discussion links), PR template          │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 6 ✓ │ DONE — py.typed marker added         │ src/regulatory_agent_kit/py.typed created; package is now PEP 561 compliant for downstream mypy   │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 7 ✓ │ DONE — CHANGELOG.md added            │ Keep-a-Changelog format; v0.1.0 entry covers all features, ADRs, and out-of-scope note             │
  └─────┴─────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Secondary gaps (polish — can follow in v0.1.x)

  ┌──────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                 Gap                  │                                            Why it matters                                             │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No CODE_OF_CONDUCT.md                │ Standard signal of community values; expected on any public repo                                      │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ ✓ DONE — SECURITY.md added           │ Responsible disclosure via GitHub Security Advisories; severity targets; RAK-specific scope          │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ ✓ DONE — .pre-commit-config.yaml    │ ruff (lint+format), pre-commit-hooks (yaml/toml/json/merge), mypy strict — zero-friction onboarding   │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ ✓ DONE — MkDocs + Pages workflow     │ mkdocs.yml + docs.yml workflow; enable Pages in repo Settings → Pages → Source: GitHub Actions       │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No real plugin repos to point to     │ README mentions DORA/PSD2/HIPAA but zero external plugins exist yet; rak plugin install leads nowhere │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ ✓ DONE — CODEOWNERS added            │ @gallindo owns everything; extra rules for infra, workflows, crypto, DB, migrations                   │
  └──────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  What's already solid

  - README.md — badges, quickstart, architecture diagram, CLI links — excellent
  - CI/CD — lint, typecheck, tests, SBOM, container signing, dependency audit — all automated
  - Docker Compose + Makefile/justfile — functional local dev out of the box
  - .env.example and rak-config.yaml.example — complete and well-commented
  - Documentation — 14 canonical docs, ADRs, glossary, runbook — production-grade
  - Tests — 80%+ coverage enforced, integration tests with testcontainers