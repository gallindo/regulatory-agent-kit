# Regulation Plugins

This directory contains regulation-specific YAML plugins for `regulatory-agent-kit`. Each plugin encodes the rules, conditions, and remediation strategies for a specific regulation or standard.

**The framework core is regulation-agnostic.** This repository does not ship with built-in regulation plugins. Regulation plugins (DORA, PCI-DSS, PSD2, HIPAA, GDPR, Open Finance, etc.) are distributed as **separate packages** and installed via the CLI.

---

## Installing a Plugin

Plugins live in separate GitHub repositories and are installed into your local `regulations/` directory via the CLI:

```bash
# Install from the plugin registry
rak plugin install <plugin-id>

# Example:
rak plugin install dora-ict-risk-2025
```

Once installed, run a compliance pipeline against the plugin:

```bash
rak run --regulation regulations/<plugin-id>/<plugin-id>.yaml --repos <repo-url>
```

---

## Example Plugin

The `examples/` directory contains a minimal, self-contained example plugin used for testing and as a reference for plugin authors. It does **not** represent any real regulation.

See [`examples/example.yaml`](examples/example.yaml) for the full schema.

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
#   README.md                # Plugin documentation
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

## Publishing a Plugin

Plugins are published to the plugin registry so other teams can install them:

```bash
# Publish a plugin to the registry
rak plugin publish regulations/my-regulation/my-regulation.yaml \
    --registry-url https://registry.example.com
```

See [`docs/plugin-template-guide.md`](../docs/plugin-template-guide.md) for the full publication workflow.

---

## Mandatory Fields

Every contributed plugin MUST include:

- `disclaimer` — acknowledging the plugin is an interpretation, not legal advice
- `source_url` — linking to the official regulation text
- At least one rule with a test template
- A `README.md` documenting the regulation context and plugin decisions

## Plugin Certification Tiers

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
# Pillar/section reference (common across regulations)
pillar: "risk_management"
rts_reference: "standard-id"

# Implementation requirement level
implementation_level: "required"

# Cross-regulation linkage
related_standards: ["iso-27001", "nist-csf"]
```

These fields are available in your Jinja2 templates as `{{ rule.pillar }}`, `{{ rule.rts_reference }}`, etc.

---

*For the framework architecture (regulation-agnostic), see [`docs/architecture.md`](../docs/architecture.md).*
