"""Initial RAK schema — all 6 tables, roles, constraints, indexes, triggers, partitioning.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-28
"""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the full rak schema with all 6 tables."""
    conn = op.get_bind()

    # --- Schema ---
    conn.execute(op.inline_literal("CREATE SCHEMA IF NOT EXISTS rak"))

    # --- Roles (idempotent) ---
    conn.execute(
        op.inline_literal(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rak_admin') THEN
                    CREATE ROLE rak_admin LOGIN PASSWORD 'rak_admin';
                END IF;
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rak_app') THEN
                    CREATE ROLE rak_app LOGIN PASSWORD 'rak_app';
                END IF;
            END $$;
            """
        )
    )

    # --- 1. pipeline_runs ---
    conn.execute(
        op.inline_literal(
            """
            CREATE TABLE rak.pipeline_runs (
                run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                regulation_id   TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN (
                        'pending','running','cost_rejected',
                        'completed','failed','rejected','cancelled'
                    )),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at    TIMESTAMPTZ,
                total_repos     INTEGER NOT NULL CHECK (total_repos > 0),
                estimated_cost  NUMERIC(10,4),
                actual_cost     NUMERIC(10,4) DEFAULT 0,
                config_snapshot JSONB NOT NULL,
                temporal_workflow_id TEXT UNIQUE,
                CONSTRAINT valid_completion CHECK (
                    (status IN (
                        'completed','failed','rejected',
                        'cost_rejected','cancelled'
                    ) AND completed_at IS NOT NULL)
                    OR (status IN ('pending','running')
                        AND completed_at IS NULL)
                )
            )
            """
        )
    )

    # --- 2. repository_progress ---
    conn.execute(
        op.inline_literal(
            """
            CREATE TABLE rak.repository_progress (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                run_id      UUID NOT NULL REFERENCES rak.pipeline_runs(run_id) ON DELETE CASCADE,
                repo_url    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','completed','failed','skipped')),
                branch_name TEXT,
                commit_sha  CHAR(40),
                pr_url      TEXT,
                error       TEXT,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE (run_id, repo_url)
            )
            """
        )
    )

    # updated_at trigger
    conn.execute(
        op.inline_literal(
            """
            CREATE OR REPLACE FUNCTION rak.update_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    conn.execute(
        op.inline_literal(
            """
            CREATE TRIGGER trg_progress_updated
            BEFORE UPDATE ON rak.repository_progress
            FOR EACH ROW EXECUTE FUNCTION rak.update_timestamp()
            """
        )
    )

    # --- 3. audit_entries (partitioned by month) ---
    conn.execute(
        op.inline_literal(
            """
            CREATE TABLE rak.audit_entries (
                entry_id    UUID NOT NULL DEFAULT gen_random_uuid(),
                run_id      UUID NOT NULL,
                event_type  TEXT NOT NULL
                    CHECK (event_type IN ('llm_call','tool_invocation','state_transition',
                        'human_decision','conflict_detected','cost_estimation',
                        'test_execution','merge_request','error')),
                timestamp   TIMESTAMPTZ NOT NULL,
                payload     JSONB NOT NULL DEFAULT '{}',
                signature   TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (timestamp, entry_id)
            ) PARTITION BY RANGE (timestamp)
            """
        )
    )

    # Create partitions for current month and next 2 months
    now = datetime.now(UTC)
    for month_offset in range(3):
        month = now.month + month_offset
        year = now.year
        if month > 12:
            month -= 12
            year += 1
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1

        partition_name = f"audit_entries_y{year}m{month:02d}"
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{next_year}-{next_month:02d}-01"

        conn.execute(
            op.inline_literal(
                f"""
                CREATE TABLE rak.{partition_name} PARTITION OF rak.audit_entries
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
                """
            )
        )

    # --- 4. checkpoint_decisions ---
    conn.execute(
        op.inline_literal(
            """
            CREATE TABLE rak.checkpoint_decisions (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                run_id          UUID NOT NULL
                    REFERENCES rak.pipeline_runs(run_id)
                    ON DELETE CASCADE,
                checkpoint_type TEXT NOT NULL
                    CHECK (checkpoint_type IN ('impact_review','merge_review')),
                actor           TEXT NOT NULL,
                decision        TEXT NOT NULL
                    CHECK (decision IN ('approved','rejected','modifications_requested')),
                rationale       TEXT,
                signature       TEXT NOT NULL DEFAULT '',
                decided_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE (run_id, checkpoint_type, decided_at)
            )
            """
        )
    )

    # --- 5. conflict_log ---
    conn.execute(
        op.inline_literal(
            """
            CREATE TABLE rak.conflict_log (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                run_id              UUID NOT NULL
                    REFERENCES rak.pipeline_runs(run_id)
                    ON DELETE CASCADE,
                conflicting_rules   JSONB NOT NULL,
                affected_regions    JSONB NOT NULL,
                resolution          TEXT,
                human_decision_id   UUID REFERENCES rak.checkpoint_decisions(id),
                detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT resolution_requires_decision CHECK (
                    (resolution IS NOT NULL AND human_decision_id IS NOT NULL)
                    OR resolution IS NULL
                )
            )
            """
        )
    )

    # --- 6. file_analysis_cache ---
    conn.execute(
        op.inline_literal(
            """
            CREATE TABLE rak.file_analysis_cache (
                cache_key   CHAR(64) PRIMARY KEY,
                repo_url    TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                result      JSONB NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at  TIMESTAMPTZ NOT NULL
            )
            """
        )
    )

    # --- Indexes (see data-model.md Section 4.1) ---

    # pipeline_runs indexes
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_runs_status ON rak.pipeline_runs (status)"
        )
    )
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_runs_regulation ON rak.pipeline_runs (regulation_id)"
        )
    )
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_runs_created ON rak.pipeline_runs (created_at DESC)"
        )
    )

    # repository_progress indexes
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_progress_run ON rak.repository_progress (run_id)"
        )
    )
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_progress_status ON rak.repository_progress (status)"
        )
    )

    # audit_entries indexes (applied to partitioned parent — propagates to partitions)
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_audit_run ON rak.audit_entries (run_id)"
        )
    )
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_audit_type ON rak.audit_entries (event_type)"
        )
    )
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_audit_payload ON rak.audit_entries USING gin (payload)"
        )
    )
    conn.execute(
        op.inline_literal(
            """
            CREATE INDEX idx_audit_model ON rak.audit_entries
                ((payload->>'model'))
            WHERE event_type = 'llm_call'
            """
        )
    )

    # checkpoint_decisions indexes
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_checkpoint_run ON rak.checkpoint_decisions (run_id)"
        )
    )

    # conflict_log indexes
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_conflict_run ON rak.conflict_log (run_id)"
        )
    )

    # file_analysis_cache indexes
    conn.execute(
        op.inline_literal(
            "CREATE INDEX idx_cache_expires ON rak.file_analysis_cache (expires_at)"
        )
    )

    # --- Grants ---
    conn.execute(op.inline_literal("GRANT USAGE ON SCHEMA rak TO rak_app, rak_admin"))
    conn.execute(
        op.inline_literal(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rak TO rak_admin"
        )
    )
    conn.execute(
        op.inline_literal(
            """
            GRANT SELECT, INSERT, UPDATE, DELETE ON rak.pipeline_runs TO rak_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON rak.repository_progress TO rak_app;
            GRANT SELECT, INSERT ON rak.audit_entries TO rak_app;
            GRANT SELECT, INSERT, UPDATE ON rak.checkpoint_decisions TO rak_app;
            GRANT SELECT, INSERT, UPDATE ON rak.conflict_log TO rak_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON rak.file_analysis_cache TO rak_app;
            """
        )
    )


def downgrade() -> None:
    """Drop all rak schema tables."""
    conn = op.get_bind()
    conn.execute(op.inline_literal("DROP SCHEMA IF EXISTS rak CASCADE"))
