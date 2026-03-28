---
description: Post-test analysis — runs after pytest to check coverage and quality
---

# Post-Test Hook

After test runs, verify:

1. **Coverage threshold:** Coverage must be >= 80% — if below, identify uncovered modules
2. **Slow tests:** Any test exceeding 10 seconds should be flagged for optimization
3. **Flaky tests:** If a test failed intermittently, check for:
   - Race conditions in async code
   - Hardcoded ports or timestamps
   - Missing test isolation (shared state between tests)
4. **Integration test cleanup:** Verify testcontainers were stopped and removed
