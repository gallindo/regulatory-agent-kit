# Python Audit Logging Example Plugin

This plugin demonstrates how to write a regulation plugin for **Python codebases**.
It enforces two rules on Python service classes.

## What this plugin enforces

| Rule | Severity | What it checks |
|---|---|---|
| `PYEX-001` | High | All classes inheriting `BaseService` must have `@audit_log` decorator |
| `PYEX-002` | Medium | `db.execute()` calls must be replaced with `Repository.query()` |

## Try it

```bash
# 1. Create a minimal non-compliant Python repo for testing
mkdir -p /tmp/py-test-repo/src
cat > /tmp/py-test-repo/src/payment_service.py << 'EOF'
from myapp.base import BaseService

class PaymentService(BaseService):
    def process_payment(self, amount: float) -> None:
        db.execute("INSERT INTO payments VALUES (?)", [amount])
EOF

# 2. Test the plugin against it
rak plugin test regulations/examples/python-example/python-example.yaml \
    --repo /tmp/py-test-repo

# Expected output:
#   ✓  src/payment_service.py   matches PYEX-001 (confidence: 0.94)
#   ✓  src/payment_service.py   matches PYEX-002 (confidence: 0.88)
```

## Key differences from the Java example

| Aspect | Java example | This Python example |
|---|---|---|
| Annotation/decorator | `has_annotation(@AuditLog)` | `has_decorator(@audit_log)` |
| Inheritance check | `class implements Service` | `class inherits BaseService` |
| Strategy | `add_annotation` | `add_annotation` + `replace_pattern` |
| File pattern | `**/*.java` | `**/*.py` |

## Condition DSL for Python

```yaml
# Check for missing decorator
condition: "class inherits BaseService AND NOT has_decorator(@audit_log)"

# Check for a specific method call pattern
condition: "has_method(db.execute)"

# Multiple inheritance targets
condition: "class inherits BaseService OR class inherits AbstractService"
```

See [`framework-spec.md` §3.3](../../docs/framework-spec.md#33-condition-dsl) for the full predicate reference.
