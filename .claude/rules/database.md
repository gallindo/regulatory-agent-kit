---
description: Database access rules — PostgreSQL via Psycopg 3, no ORM
globs: ["src/regulatory_agent_kit/database/**/*.py"]
---

# Database Rules

- Use Psycopg 3 AsyncConnectionPool — never SQLAlchemy ORM or raw psycopg2
- Parameterized queries only — never f-string or %-format SQL (SQL injection risk)
- Repository pattern: thin classes in `database/repositories/` wrapping queries
- UUIDs for all primary keys (use `uuid.uuid4()`)
- Three PostgreSQL schemas exist: `rak` (Alembic-managed), `temporal` (hands off), `mlflow` (hands off)
- The `audit_entries` table is append-only: INSERT and SELECT only, never UPDATE or DELETE
- All schema changes go through Alembic migrations — never run DDL directly
- Use JSONB columns for semi-structured data (impact maps, rule payloads)
