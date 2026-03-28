---
description: Create and validate a new Alembic database migration
---

Create a new database migration. Ask the user for:
1. Migration description (e.g., "add notifications table")

Then:
1. Run `alembic revision --autogenerate -m "<description>"` to generate the migration
2. Read the generated migration file
3. Review it for:
   - Correct upgrade() and downgrade() functions
   - Parameterized queries (no f-strings in SQL)
   - UUID primary keys
   - Proper foreign key constraints with ON DELETE CASCADE
   - Index creation for frequently queried columns
4. If the migration touches `audit_entries`, verify it only adds columns or indexes — never modifies existing constraints (append-only table)
5. Report the migration file path and a summary of changes
