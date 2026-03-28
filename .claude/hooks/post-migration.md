---
description: Post-migration verification — runs after Alembic migrations
---

# Post-Migration Hook

After running `alembic upgrade head`, verify the migration was applied correctly:

1. **Check current head:** `alembic current` — should show the latest revision
2. **Verify schema:** Connect to PostgreSQL and confirm new tables/columns exist
3. **Check downgrade path:** `alembic downgrade -1` then `alembic upgrade head` — roundtrip must succeed
4. **Audit table integrity:** If migration touched `audit_entries`, verify:
   - No UPDATE or DELETE permissions were granted
   - Partitioning is intact
   - Existing data was not modified

## Guarded Tables

These tables have special constraints:
- `audit_entries` — append-only, monthly partitioned, cryptographic signatures
- `checkpoint_decisions` — signatures must not be nullable
