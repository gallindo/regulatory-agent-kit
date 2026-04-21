## Summary

<!-- What does this PR do and why? One paragraph. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behaviour change)
- [ ] Documentation update
- [ ] CI / infrastructure change

## Related issues

<!-- Closes #... -->

## Changes

<!-- Bullet list of the key changes. Focus on decisions made, not line-by-line description. -->

-
-

## Testing

<!-- How did you verify this works? -->

- [ ] Unit tests added / updated (`pytest tests/unit/`)
- [ ] Integration tests added / updated (`pytest tests/integration/ -m integration`)
- [ ] Manually tested with `rak run --lite`

## Architecture checklist

- [ ] No regulatory logic hardcoded in Python (all rules live in YAML plugins)
- [ ] No new `os.getenv()` calls — pydantic-settings used for config
- [ ] No direct Anthropic/OpenAI API calls — LiteLLM used for all LLM calls
- [ ] New exceptions inherit from `RAKError`
- [ ] SQL queries are parameterized (no f-string SQL)
- [ ] Jinja2 templates use `SandboxedEnvironment`
- [ ] Public functions have full type annotations (mypy strict passes)

## Reviewer notes

<!-- Anything the reviewer should pay special attention to, or context that isn't obvious from the diff. -->
