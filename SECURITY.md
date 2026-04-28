# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes    |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/gallindo/regulatory-agent-kit/security/advisories/new). This keeps the details confidential until a fix is ready.

Include in your report:

- Description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Affected versions
- Any suggested mitigations you are aware of

## Response Timeline

| Stage | Target |
|-------|--------|
| Initial acknowledgement | 48 hours |
| Severity assessment | 5 business days |
| Fix or mitigation | Depends on severity (see below) |
| Public disclosure | After fix is released |

**Severity targets:**

- **Critical / High** — patch within 7 days
- **Medium** — patch within 30 days
- **Low / Informational** — addressed in the next regular release

## Scope

Areas of particular concern:

- **Audit trail integrity** — Ed25519 signature verification, append-only guarantees
- **Human checkpoint bypass** — any code path that could skip impact-review or merge-review gates
- **SQL injection** — parameterized query enforcement in all repository classes
- **Template injection** — Jinja2 `SandboxedEnvironment` bypass
- **Credential exposure** — secrets in logs, environment variables, or audit entries
- **LLM prompt injection** — inputs that could manipulate agent behaviour in unsafe ways
- **Plugin YAML execution** — arbitrary code execution via malicious plugin files

Out of scope: vulnerabilities in third-party dependencies (report those upstream), theoretical attacks with no practical exploit path.

## Disclosure Policy

We follow coordinated disclosure. Once a fix is released, we will publish a GitHub Security Advisory crediting the reporter (unless you prefer to remain anonymous).
