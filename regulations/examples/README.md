# Example Regulation Plugins

This directory contains self-contained example plugins for learning and testing.

| Plugin | Language | Strategies used |
|---|---|---|
| [`example.yaml`](example.yaml) | Java | `add_annotation`, `add_configuration` |
| [`python-example/`](python-example/) | Python | `add_annotation`, `replace_pattern` |

---

## Java Example (`example.yaml`)

### What it enforces

| Rule | Severity | Checks |
|---|---|---|
| `EXAMPLE-001` | High | All Java classes implementing `Service` must have `@AuditLog` annotation |
| `EXAMPLE-002` | Medium | YAML configs must define `resilience.rto` and `resilience.rpo` keys |

### File layout

```
example.yaml                    ← plugin definition (2 rules)
templates/
├── audit_log.j2                ← adds @AuditLog annotation above class declaration
└── audit_log_test.j2           ← generates JUnit 5 test for the annotation
```

### How to test it

**Step 1 — Create a non-compliant Java file:**

```bash
mkdir -p /tmp/java-test/src
cat > /tmp/java-test/src/UserService.java << 'EOF'
public class UserService implements Service {
    public void handleRequest() {}
}
EOF
```

**Step 2 — Run the plugin:**

```bash
rak plugin test regulations/examples/example.yaml --repo /tmp/java-test
```

**Expected output:**

```
Testing plugin: Example Audit Logging Regulation (v1.0.0)

  ✓  src/UserService.java    matches EXAMPLE-001 (confidence: 0.95)

Remediations:
  EXAMPLE-001 → src/UserService.java
  --- original
  +++ remediated
  @@ -1,3 +1,4 @@
  +@AuditLog(level = AuditLevel.FULL, retentionDays = 90)
   public class UserService implements Service {
       public void handleRequest() {}
   }

Summary
  Rules tested:  2
  Matches:       1
  Exit code:     0
```

**Step 3 — Test a compliant file (should NOT match):**

```bash
mkdir -p /tmp/java-compliant/src
cat > /tmp/java-compliant/src/GoodService.java << 'EOF'
@AuditLog(level = AuditLevel.FULL, retentionDays = 90)
public class GoodService implements Service {
    public void handleRequest() {}
}
EOF

rak plugin test regulations/examples/example.yaml --repo /tmp/java-compliant
# Expected: no rules matched
```

### Plugin YAML walkthrough

```yaml
id: example-audit-logging-2025     # Unique ID — used in cross-references and audit trails
name: "Example Audit Logging Regulation"
version: "1.0.0"
effective_date: "2025-01-01"       # When this regulation applies from
jurisdiction: "EXAMPLE"            # "EXAMPLE" for demos; use ISO country code in real plugins
authority: "Example Regulatory Authority"
source_url: "https://example.com/regulations/audit-logging"
disclaimer: >                      # Required — must be non-empty
  This is an example plugin for testing purposes only.

changelog: "1.0.0: Initial example plugin."

rules:
  - id: EXAMPLE-001
    description: >
      All service classes must have an @AuditLog annotation.
    severity: high
    affects:
      - pattern: "**/*.java"       # Glob — matches all .java files recursively
        condition: "class implements Service AND NOT has_annotation(@AuditLog)"
        #                          ↑ AND: BOTH conditions must hold
        #                                NOT: the annotation must be ABSENT for a match
    remediation:
      strategy: add_annotation
      template: templates/audit_log.j2
      test_template: templates/audit_log_test.j2
      confidence_threshold: 0.85   # Below this, human review is required
```

---

## Next steps

- To write your own plugin from scratch, follow the [Plugin Authoring Guide](../../docs/plugin-authoring-guide.md).
- For the full schema reference, see [framework-spec.md §12](../../docs/framework-spec.md#12-plugin-schema-reference).
- For template authoring details, see [plugin-template-guide.md](../../docs/plugin-template-guide.md).
- For the Python example, see [python-example/README.md](python-example/README.md).
