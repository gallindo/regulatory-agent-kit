# Plugin Authoring Guide

**Audience:** Engineers and compliance officers who want to create a new regulation plugin for regulatory-agent-kit.

**Prerequisites:**
- `rak` installed (`uv sync` from the repo root)
- LLM API key set (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`)
- Basic familiarity with YAML and Jinja2

**Time:** ~30 minutes for a single-rule plugin from scratch.

---

## 1. What is a plugin?

A plugin is a YAML file (plus Jinja2 templates) that teaches the framework about a specific regulation. It answers three questions:

1. **Which files are affected?** — A glob pattern (e.g., `**/*.java`).
2. **What makes a file non-compliant?** — A condition DSL expression (e.g., `class implements Service AND NOT has_annotation(@AuditLog)`).
3. **How do we fix it?** — A remediation strategy and a Jinja2 template.

The framework is agnostic to regulations. All regulatory knowledge lives in your plugin YAML — the core code never changes.

---

## 2. Scaffold a new plugin

```bash
rak plugin init --name my-regulation
```

This creates:

```
regulations/my-regulation/
├── my-regulation.yaml          ← plugin definition
├── templates/
│   └── example.j2              ← placeholder remediation template
└── README.md                   ← documentation template
```

Open `regulations/my-regulation/my-regulation.yaml`. You will see all required fields pre-populated with placeholder values.

---

## 3. Fill in the plugin metadata

Edit `my-regulation.yaml`. Replace every placeholder with real values. The required fields are:

```yaml
id: my-regulation-2025             # unique, kebab-case
name: "My Regulation Requirements"
version: "1.0.0"
effective_date: "2025-01-01"
jurisdiction: "EU"                 # ISO 3166-1 alpha-2, or "GLOBAL"
authority: "My Regulatory Authority"
source_url: "https://example.com/my-regulation"
disclaimer: >
  This plugin represents one interpretation of the referenced regulation.
  It does not constitute legal advice. Validate with your legal team.
```

See the [full field reference](framework-spec.md#12-plugin-schema-reference) for all optional fields.

---

## 4. Define your first rule

Add a `rules` block below the metadata. Each rule needs an `id`, `description`, `severity`, at least one `affects` clause, and a `remediation`.

**Java example — requiring an annotation:**

```yaml
rules:
  - id: MYREG-001
    description: >
      All service classes must have @AuditLog annotation for traceability.
    severity: high
    affects:
      - pattern: "**/*.java"
        condition: "class implements Service AND NOT has_annotation(@AuditLog)"
    remediation:
      strategy: add_annotation
      template: templates/add_audit_log.j2
      test_template: templates/add_audit_log_test.j2
      confidence_threshold: 0.85
```

**Python example — requiring a decorator:**

```yaml
rules:
  - id: MYREG-001
    description: >
      All service classes must have @audit_log decorator.
    severity: high
    affects:
      - pattern: "**/*.py"
        condition: "class inherits BaseService AND NOT has_decorator(@audit_log)"
    remediation:
      strategy: add_annotation
      template: templates/add_audit_log.j2
      confidence_threshold: 0.85
```

**Condition DSL quick reference:**

| Expression | Matches when... |
|---|---|
| `class implements Foo` | Java class implements `Foo` interface |
| `class inherits Bar` | Python class inherits from `Bar` |
| `has_annotation(@Foo)` | Java class/method has `@Foo` annotation |
| `has_decorator(@foo)` | Python class/function has `@foo` decorator |
| `has_method(bar)` | Class has method named `bar` |
| `has_key(a.b)` | YAML/JSON file has nested key `a.b` |
| `class_name matches ".*Controller"` | Class name matches regex |
| `A AND B` | Both A and B must be true |
| `A OR B` | Either A or B must be true |
| `NOT A` | A must not be true |

---

## 5. Write the remediation template

Rename `templates/example.j2` to match your rule's `template` path (e.g., `templates/add_audit_log.j2`).

Templates are Jinja2 rendered by a `SandboxedEnvironment` — no file I/O, no imports. They receive these key variables:

| Variable | What it contains |
|---|---|
| `file_content` | The full current content of the file |
| `file_path` | Absolute path to the file |
| `affected_region.start_line` | Line where the match begins (1-indexed) |
| `rule.id` | The rule ID (e.g., `MYREG-001`) |
| `plugin.id` | The plugin ID |

**Java annotation example (`templates/add_audit_log.j2`):**

```jinja2
{# Insert @AuditLog before the class declaration line #}
{% set lines = file_content.split('\n') %}
{% for i in range(lines | length) %}
{% if i == affected_region.start_line - 1 %}
@AuditLog(level = AuditLevel.FULL, retentionDays = 90)
{% endif %}
{{ lines[i] }}
{% endfor %}
```

**Python decorator example (`templates/add_audit_log.j2`):**

```jinja2
{# Insert @audit_log before the class definition line #}
{% set lines = file_content.split('\n') %}
{% for i in range(lines | length) %}
{% if i == affected_region.start_line - 1 %}
@audit_log(regulation="{{ plugin.id }}", rule="{{ rule.id }}")
{% endif %}
{{ lines[i] }}
{% endfor %}
```

See [plugin-template-guide.md](plugin-template-guide.md) for the full variable reference, all built-in strategies, custom Jinja2 filters, and security constraints.

---

## 6. Validate the plugin

```bash
rak plugin validate regulations/my-regulation/my-regulation.yaml
```

This checks schema validity, template syntax, and that all referenced template files exist. Fix any errors it reports before continuing.

Common errors and fixes:

| Error | Fix |
|---|---|
| `disclaimer must contain non-whitespace text` | Add a non-empty `disclaimer` field |
| `template file not found: templates/foo.j2` | Create the file or fix the path in `template:` |
| `Condition DSL parse error` | Check for typos in predicate names; see §3.3 of framework-spec.md |
| `field required: source_url` | Add `source_url` pointing to the official regulation text |

---

## 7. Test the plugin against a repository

Create a minimal test repository with one non-compliant file:

```bash
mkdir -p /tmp/test-repo/src
# Java example:
cat > /tmp/test-repo/src/UserService.java << 'EOF'
public class UserService implements Service {
    public void handleRequest() {}
}
EOF

# Run the test
rak plugin test regulations/my-regulation/my-regulation.yaml --repo /tmp/test-repo
```

Expected output:

```
  ✓  src/UserService.java    matches MYREG-001 (confidence: 0.95)

Summary
  Matches: 1
  Exit code: 0
```

If you see `no rules matched`, check:
1. The `affects[].pattern` glob — use `**/*.java`, not `*.java`.
2. The `condition` predicates — verify class names are spelled exactly as in the source file.
3. Run `rak plugin validate` to catch template errors separately.

---

## 8. Run the full pipeline (Lite Mode)

Once `rak plugin test` passes, run the pipeline against a real repository in Lite Mode (no Docker required):

```bash
rak run --lite \
  --regulation regulations/my-regulation/my-regulation.yaml \
  --repos /path/to/target-repo
```

The pipeline will:
1. Scan the repository and produce an impact map.
2. Pause and ask for your approval (Impact Review checkpoint).
3. Apply remediations and generate tests.
4. Pause and ask for your approval (Merge Review checkpoint).
5. Create a merge request and write the signed audit trail.

---

## 9. Share your plugin

Until the plugin registry launches (Phase 2), share your plugin as a GitHub repository:

**Naming convention:** `rak-plugin-<jurisdiction>-<regulation-short-name>`
For example: `rak-plugin-eu-dora`, `rak-plugin-us-hipaa`

**Recommended repository structure:**

```
rak-plugin-eu-dora/
├── eu-dora-2025.yaml           ← plugin YAML
├── templates/                  ← all Jinja2 templates
│   ├── ict_risk_policy.j2
│   └── ict_risk_policy_test.j2
├── test-fixtures/
│   ├── compliant/              ← files that should NOT match
│   └── non-compliant/         ← files that SHOULD match
└── README.md                   ← how to use, what the regulation covers
```

**Others can install and use it:**

```bash
git clone https://github.com/your-org/rak-plugin-eu-dora.git
rak plugin validate rak-plugin-eu-dora/eu-dora-2025.yaml
rak run --lite --regulation rak-plugin-eu-dora/eu-dora-2025.yaml --repos ./my-service
```

---

## Next steps

| Goal | Resource |
|---|---|
| Write multi-rule plugins with cross-references | [framework-spec.md §3.5](framework-spec.md#35-plugin-lifecycle) |
| All Jinja2 template variables and filters | [plugin-template-guide.md](plugin-template-guide.md) |
| Write a custom Python remediator | [framework-spec.md §3.4.1](framework-spec.md#341-writing-a-custom-agent) |
| Full CLI reference | [cli-reference.md](cli-reference.md) |
| Full field reference | [framework-spec.md §12](framework-spec.md#12-plugin-schema-reference) |
