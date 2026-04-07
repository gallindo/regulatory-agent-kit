# Plugin Template Authoring Guide

**Audience:** Compliance engineers and platform engineers writing regulation plugins
**Prerequisites:** Familiarity with [Jinja2 templating](https://jinja.palletsprojects.com/) and the [plugin schema](framework-spec.md#12-plugin-schema-reference)

---

> **Glossary:** Unfamiliar with AST, tree-sitter, or Jinja2? See [`glossary.md`](glossary.md).

## Quick Example: Your First Template

Before diving into the full template API, here is a minimal end-to-end example. Given a regulation rule that requires all service classes to have an `@AuditLog` annotation:

**1. Rule (in your plugin YAML):**
```yaml
rules:
  - id: audit-log-required
    description: "All service classes must have @AuditLog annotation"
    severity: high
    condition: "class implements Service AND NOT has_annotation(@AuditLog)"
    remediation:
      strategy: add_annotation
      template: templates/add-audit-log.j2
```

**2. Template (`templates/add-audit-log.j2`):**
```jinja2
{# Adds @AuditLog annotation above the class declaration #}
{% for line in file_content.split('\n') %}
{% if 'class ' in line and 'implements' in line and '@AuditLog' not in file_content %}
@AuditLog
{% endif %}
{{ line }}
{% endfor %}
```

**3. Validate and test:**
```bash
rak plugin validate regulations/my-regulation.yaml
rak plugin test regulations/my-regulation.yaml --repo ./test-repo
```

The sections below explain the template context variables, all available strategies, Jinja2 filters, and security constraints in detail.

## 1. Overview

Each regulation plugin rule can reference two Jinja2 templates:

- **`template`** — The remediation template. Generates the code/configuration changes to make the codebase compliant.
- **`test_template`** — The test template. Generates tests that validate the remediation was applied correctly.

Templates are rendered by the `TemplateEngine` (Jinja2 `SandboxedEnvironment`) and executed by the Refactor Agent and TestGenerator Agent respectively.

---

## 2. Template Context Variables

When a template is rendered, the following variables are available in the Jinja2 context:

### 2.1 Core Variables (Always Available)

| Variable | Type | Description |
|---|---|---|
| `file_path` | `str` | Absolute path to the file being modified |
| `file_content` | `str` | Current content of the file |
| `rule` | `Rule` | The matched rule object from the plugin YAML |
| `rule.id` | `str` | Rule identifier (e.g., `"DORA-ICT-001"`) |
| `rule.description` | `str` | Plain-language rule description |
| `rule.severity` | `str` | `critical`, `high`, `medium`, or `low` |
| `match` | `RuleMatch` | The match result from the Analyzer Agent |
| `match.confidence` | `float` | Confidence score of the match (0.0–1.0) |
| `match.condition_evaluated` | `str` | The condition expression that was evaluated |
| `affected_region` | `ASTRegion` | The AST region where the match occurred |
| `affected_region.start_line` | `int` | Start line number |
| `affected_region.end_line` | `int` | End line number |
| `affected_region.node_type` | `str` | tree-sitter node type (e.g., `class_declaration`) |

### 2.2 Plugin Metadata (Always Available)

| Variable | Type | Description |
|---|---|---|
| `plugin` | `RegulationPlugin` | The full plugin object |
| `plugin.id` | `str` | Plugin identifier |
| `plugin.name` | `str` | Human-readable regulation name |
| `plugin.version` | `str` | Plugin version (semver) |
| `plugin.jurisdiction` | `str` | ISO 3166-1 alpha-2 or `"GLOBAL"` |
| `plugin.disclaimer` | `str` | Legal disclaimer text |

### 2.3 Custom Plugin Fields (Pass-Through)

Any additional fields defined in the plugin YAML (beyond the schema) are passed through to the template context via `plugin.model_extra`. For example, if the plugin YAML contains:

```yaml
rules:
  - id: "DORA-ICT-001"
    dora_pillar: "ict_risk_management"
    rts_reference: "JC-2023-86"
```

These are accessible as:

```jinja2
{{ rule.model_extra.dora_pillar }}
{{ rule.model_extra.rts_reference }}
```

### 2.4 Test Template Additional Variables

Test templates receive all the variables above, plus:

| Variable | Type | Description |
|---|---|---|
| `change_set` | `ChangeSet` | The changes applied by the Refactor Agent |
| `original_content` | `str` | File content before remediation |
| `modified_content` | `str` | File content after remediation |
| `diff` | `str` | Unified diff between original and modified |

---

## 3. Template Examples by Strategy

### 3.1 `add_annotation` — Adding a Class Annotation

**Plugin rule:**

```yaml
rules:
  - id: "EX-001"
    description: "All services must have audit logging"
    severity: "critical"
    affects:
      - pattern: "**/*.java"
        condition: "class implements AuditableService AND NOT has_annotation(@AuditLog)"
    remediation:
      strategy: "add_annotation"
      template: "templates/audit_log.j2"
      test_template: "templates/audit_log_test.j2"
      confidence_threshold: 0.85
```

**Remediation template (`templates/audit_log.j2`):**

```jinja2
{# Insert @AuditLog annotation before the class declaration #}
{% set lines = file_content.split('\n') %}
{% for line in lines %}
{% if loop.index0 == affected_region.start_line - 1 %}
@AuditLog(level = AuditLevel.FULL, retentionDays = 90)
{% endif %}
{{ line }}
{% endfor %}
```

**Test template (`templates/audit_log_test.j2`):**

```jinja2
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class {{ rule.id | replace('-', '') }}Test {

    @Test
    void classHasAuditLogAnnotation() {
        // Verify the @AuditLog annotation is present
        var clazz = Class.forName("{{ affected_region.node_type }}");
        assertTrue(clazz.isAnnotationPresent(AuditLog.class),
            "{{ rule.description }}");
    }
}
```

### 3.2 `add_configuration` — Injecting YAML Keys

**Remediation template:**

```jinja2
{# Add resilience configuration to service manifest #}
{{ file_content }}
{% if 'resilience:' not in file_content %}

resilience:
  rto: "4h"        # Recovery Time Objective ({{ rule.id }})
  rpo: "1h"        # Recovery Point Objective ({{ rule.id }})
  classification: "important"  # ICT service classification
{% endif %}
```

### 3.3 `replace_pattern` — Replacing Deprecated Patterns

**Remediation template:**

```jinja2
{# Replace deprecated API endpoint pattern #}
{{ file_content | replace(
    'HttpClient.newBuilder().build()',
    'HttpClient.newBuilder()\n    .connectTimeout(Duration.ofSeconds(30))\n    .followRedirects(HttpClient.Redirect.NEVER)\n    .build()'
) }}
```

### 3.4 `add_dependency` — Adding Build Dependencies

**Remediation template (for `pom.xml`):**

```jinja2
{# Inject compliance SDK dependency into Maven POM #}
{% set marker = '</dependencies>' %}
{{ file_content | replace(marker,
'    <dependency>\n'
'        <groupId>com.example</groupId>\n'
'        <artifactId>compliance-sdk</artifactId>\n'
'        <version>2.0.0</version>\n'
'    </dependency>\n'
'  ' + marker) }}
```

### 3.5 `generate_file` — Creating New Files

**Remediation template:**

```jinja2
# Auto-generated by {{ plugin.name }} v{{ plugin.version }}
# Rule: {{ rule.id }} — {{ rule.description }}
# Generated for: {{ file_path }}

resilience:
  service_name: "{{ file_path | basename | replace('.yaml', '') }}"
  rto: "4h"
  rpo: "1h"
  backup_strategy: "incremental"
  failover_target: "secondary-region"
```

---

## 4. Available Jinja2 Filters

The `TemplateEngine` uses Jinja2's `SandboxedEnvironment`, which restricts access to system resources. The following filters are available:

### Built-in Jinja2 Filters

All standard Jinja2 filters: `upper`, `lower`, `title`, `capitalize`, `replace`, `trim`, `default`, `join`, `split`, `length`, `first`, `last`, `sort`, `unique`, `reject`, `select`, `map`, `indent`, `wordwrap`, etc.

### Custom Filters

| Filter | Description | Example |
|---|---|---|
| `basename` | Extract filename from path | `{{ "src/main/Foo.java" \| basename }}` → `Foo.java` |
| `dirname` | Extract directory from path | `{{ "src/main/Foo.java" \| dirname }}` → `src/main` |
| `snake_case` | Convert to snake_case | `{{ "FooBar" \| snake_case }}` → `foo_bar` |
| `camel_case` | Convert to camelCase | `{{ "foo_bar" \| camel_case }}` → `fooBar` |
| `pascal_case` | Convert to PascalCase | `{{ "foo_bar" \| pascal_case }}` → `FooBar` |

---

## 5. Security Constraints

Templates execute inside Jinja2's `SandboxedEnvironment`:

- **No file system access:** Templates cannot read or write files
- **No imports:** `import` statements are not available
- **No arbitrary code execution:** Only Jinja2 expressions and filters
- **No access to `os`, `subprocess`, `socket`:** System modules are blocked

Templates are statically analyzed during `rak plugin validate` to catch violations before runtime.

---

## 6. Testing Your Templates

```bash
# Validate template syntax and rendering
rak plugin validate regulations/my-regulation.yaml

# Run templates against a test repository
rak plugin test regulations/my-regulation.yaml --repo ./test-repo
```

The `rak plugin test` command:
1. Loads the plugin and validates the schema
2. Runs the Analyzer Agent against the test repo to find matches
3. Renders remediation templates for each match
4. Renders test templates and executes them in a sandboxed container
5. Reports pass/fail results

---

*See also: [`framework-spec.md` Section 12](framework-spec.md#12-plugin-schema-reference) for the full plugin YAML schema, [`regulations/dora/`](../regulations/dora/) for a real-world plugin example, and [`cli-reference.md`](cli-reference.md) for all `rak plugin` commands.*
