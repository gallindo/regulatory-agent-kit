  What's needed before going live

  Blockers (must fix before announcing)

  ┌─────┬─────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  #  │                 Gap                 │                                                Fix                                                │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 1 ✓ │ DONE — MIT LICENSE file added        │ LICENSE created at repo root (commit 184c287); GitHub now auto-detects MIT                         │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 2   │ No CONTRIBUTING.md                  │ README links to it but it doesn't exist; contributors have no guidance                            │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 3   │ No [project.urls] in pyproject.toml │ PyPI page will be bare — add homepage, repository, docs, issues links                             │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 4   │ No PyPI publish workflow            │ pip install regulatory-agent-kit doesn't work; need a release GitHub Action + semantic versioning │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 5   │ No GitHub issue/PR templates        │ .github/ISSUE_TEMPLATE/ (bug, feature, security) and PULL_REQUEST_TEMPLATE.md are both missing    │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 6   │ No py.typed marker                  │ mypy strict mode is configured but PEP 561 compliance isn't signaled to downstream users          │
  ├─────┼─────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 7   │ No CHANGELOG.md                     │ No human-readable release notes; backfill from git log for v0.1.0                                 │
  └─────┴─────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Secondary gaps (polish — can follow in v0.1.x)

  ┌──────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                 Gap                  │                                            Why it matters                                             │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No CODE_OF_CONDUCT.md                │ Standard signal of community values; expected on any public repo                                      │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No SECURITY.md                       │ No responsible disclosure process for vulnerability reports                                           │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No .pre-commit-config.yaml           │ Contributors must manually wire ruff/mypy; friction at onboarding                                     │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No hosted docs (MkDocs/GitHub Pages) │ 9 000+ lines of .md are only browsable raw on GitHub                                                  │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No real plugin repos to point to     │ README mentions DORA/PSD2/HIPAA but zero external plugins exist yet; rak plugin install leads nowhere │
  ├──────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No CODEOWNERS                        │ No default reviewers assigned to PRs; fine for solo, needed for team                                  │
  └──────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  What's already solid

  - README.md — badges, quickstart, architecture diagram, CLI links — excellent
  - CI/CD — lint, typecheck, tests, SBOM, container signing, dependency audit — all automated
  - Docker Compose + Makefile/justfile — functional local dev out of the box
  - .env.example and rak-config.yaml.example — complete and well-commented
  - Documentation — 14 canonical docs, ADRs, glossary, runbook — production-grade
  - Tests — 80%+ coverage enforced, integration tests with testcontainers