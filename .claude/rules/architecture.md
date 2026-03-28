---
description: Architectural invariants that must never be violated
globs: ["src/**/*.py"]
---

# Architecture Rules

- NEVER hardcode regulatory logic in Python — all regulation knowledge belongs in YAML plugins under `regulations/`
- Human checkpoint gates are non-bypassable — no code path may skip approval at impact-review or merge-review stages
- Audit trail entries must be cryptographically signed (Ed25519 via `cryptography` library)
- Agents are regulation-agnostic — they receive regulatory context from plugins, never from internal logic
- Event sources implement the `EventSource` interface — never couple to a specific message broker
- LLM calls go through LiteLLM — never call provider APIs (Anthropic, OpenAI) directly
- Configuration uses pydantic-settings — never parse environment variables with `os.getenv()` manually
- All custom exceptions inherit from `RAKError` in `exceptions.py`
