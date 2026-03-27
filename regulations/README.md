# Regulation Plugins

This directory contains regulation-specific YAML plugins for `regulatory-agent-kit`. Each plugin encodes the rules, conditions, and remediation strategies for a specific regulation or standard.

**The framework core is regulation-agnostic.** All regulatory knowledge lives here, in plugins.

---

## Plugin Catalog

### Official Plugins (maintained by core team)

| Plugin | Regulation | Jurisdiction | Status | Directory |
|---|---|---|---|---|
| `dora-ict-risk-2025` | DORA — ICT Risk Management | EU | Planned (v1.5) | [`dora/`](dora/) |
| `dora-incident-reporting-2025` | DORA — ICT Incident Reporting | EU | Planned (v1.5) | [`dora/`](dora/) |
| `dora-resilience-testing-2025` | DORA — Resilience Testing | EU | Planned (v1.5) | [`dora/`](dora/) |
| `dora-third-party-risk-2025` | DORA — Third-Party Risk | EU | Planned (v1.5) | [`dora/`](dora/) |
| `pci-dss-v4-2025` | PCI-DSS v4.0 | Global | Planned (v1.5) | `pci-dss/` |
| `psd2-sca-2025` | PSD2 — Strong Customer Authentication | EU | Planned (v1.5) | `psd2/` |
| `eu-ai-act-high-risk-2026` | EU AI Act — High-Risk AI Systems | EU | Planned (v2.0) | `eu-ai-act/` |
| `nis2-essential-2025` | NIS2 — Essential Entities | EU | Planned (v2.0) | `nis2/` |
| `mica-casp-2025` | MiCA — Crypto-Asset Service Providers | EU | Planned (v2.0) | `mica/` |
| `hipaa-technical-2025` | HIPAA — Technical Safeguards | US | Planned (v2.0) | `hipaa/` |
| `gdpr-privacy-engineering-2025` | GDPR — Technical Implementation | EU | Planned (v2.0) | `gdpr/` |

### Community Plugins

Community-contributed plugins will be listed here once the plugin registry launches in v1.5. To contribute a plugin, see [Contributing a Plugin](#contributing-a-plugin) below.

---

## Plugin Roadmap

| Phase | Target Date | Plugins |
|---|---|---|
| **v1.5** | Q2–Q3 2026 | PCI-DSS v4.0, DORA (all 5 pillars), PSD2 |
| **v2.0** | Q3–Q4 2026 | EU AI Act, NIS2, MiCA, HIPAA, GDPR |
| **v2.5+** | Q1 2027+ | Community-contributed via plugin marketplace |

This roadmap covers **official plugins only**. The framework supports any regulation from v1.0 — you can write plugins for any regulation today using the YAML schema.

---

## Creating a Plugin

### Quick Start

```bash
# Scaffold a new plugin
rak plugin init --name my-regulation

# This creates:
# regulations/my-regulation/
#   my-regulation.yaml      # Plugin definition
#   templates/               # Jinja2 remediation templates
#   tests/                   # Test fixtures
#   README.md               # Plugin documentation
```

### Plugin Structure

```
regulations/
  my-regulation/
    my-regulation.yaml       # Plugin definition (YAML)
    templates/
      remediation_a.j2       # Jinja2 template for remediation strategy
      remediation_a_test.j2  # Jinja2 template for generated tests
    tests/
      fixtures/              # Sample repositories for testing
      test_plugin.py         # Plugin validation tests
    README.md                # Regulation-specific documentation
```

### Schema Reference

See [`docs/architecture.md` — Section 12: Plugin Schema Reference](../docs/architecture.md#12-plugin-schema-reference) for the complete YAML schema.

### Validation

```bash
# Validate schema, templates, and test fixtures
rak plugin validate regulations/my-regulation/my-regulation.yaml

# Run plugin against a test repository
rak plugin test regulations/my-regulation/my-regulation.yaml --repo tests/fixtures/sample-repo
```

---

## Contributing a Plugin

### Who Can Contribute

- **Compliance engineers** — domain expertise in specific regulations
- **Legal professionals** — understanding of regulatory interpretation
- **Platform engineers** — technical implementation of remediation templates

### Contribution Process

1. Fork the repository
2. `rak plugin init --name your-regulation`
3. Write the YAML plugin following the schema reference
4. Write Jinja2 templates for each remediation strategy
5. Write test fixtures demonstrating the plugin against sample code
6. Run `rak plugin validate` to verify
7. Submit a pull request

### Review Process

All regulation plugins undergo:

1. **Automated validation** — schema correctness, template rendering, test passing (CI)
2. **Domain review** — at least 2 reviewers with expertise in the regulation
3. **Technical review** — at least 1 reviewer for template quality and edge cases

### Mandatory Fields

Every contributed plugin MUST include:

- `disclaimer` — acknowledging the plugin is an interpretation, not legal advice
- `source_url` — linking to the official regulation text
- At least one rule with a test template
- A `README.md` documenting the regulation context and plugin decisions

### Plugin Certification Tiers

| Tier | Badge | Meaning |
|---|---|---|
| **Technically Valid** | `[valid]` | Passes automated CI validation |
| **Community Reviewed** | `[reviewed]` | 2+ domain expert reviewers approved |
| **Official** | `[official]` | Maintained by core team, versioned with regulation |

There is no "certified" tier. Certification implies legal liability.

---

## Adding Domain-Specific Fields

The plugin schema is **open** — you may include arbitrary additional fields beyond the required schema. The framework ignores unrecognized fields but passes them through to Jinja2 templates and the Reporter Agent.

Examples:

```yaml
# DORA-specific extension fields
dora_pillar: "ict_risk_management"
rts_reference: "JC-2023-86"

# PCI-DSS-specific extension fields
pci_requirement: "6.4.3"
pci_testing_procedure: "6.4.3.a"

# HIPAA-specific extension fields
hipaa_standard: "164.312(a)(1)"
hipaa_implementation: "required"

# BACEN-specific extension fields
bacen_circular: "4.015/2020"
open_finance_phase: "4"
```

These fields are available in your Jinja2 templates as `{{ rule.dora_pillar }}`, `{{ rule.pci_requirement }}`, etc.

---

*For the framework architecture (regulation-agnostic), see [`docs/architecture.md`](../docs/architecture.md). For the full product document, see [`docs/regulatory-agent-kit-v2.md`](../docs/regulatory-agent-kit-v2.md).*
