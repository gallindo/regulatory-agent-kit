"""Add plugin registry tables.

Revision ID: 002_plugin_registry
Revises: 001_initial_schema
Create Date: 2026-04-09
"""

from __future__ import annotations

from alembic import op

revision = "002_plugin_registry"
down_revision = "001_initial_schema"


def upgrade() -> None:
    """Create plugin_registry and plugin_versions tables in the rak schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS rak.plugin_registry (
            plugin_id   TEXT        PRIMARY KEY,
            name        TEXT        NOT NULL,
            latest_version TEXT     NOT NULL,
            jurisdiction TEXT       NOT NULL DEFAULT '',
            authority   TEXT        NOT NULL DEFAULT '',
            description TEXT        NOT NULL DEFAULT '',
            author      TEXT        NOT NULL DEFAULT '',
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            downloads   INTEGER     NOT NULL DEFAULT 0,
            tags        JSONB       NOT NULL DEFAULT '[]'::jsonb,
            certification_tier TEXT NOT NULL DEFAULT 'technically_valid',
            metadata    JSONB       NOT NULL DEFAULT '{}'::jsonb,

            CONSTRAINT chk_certification_tier CHECK (
                certification_tier IN ('technically_valid', 'community_reviewed', 'official')
            )
        );

        CREATE TABLE IF NOT EXISTS rak.plugin_versions (
            plugin_id    TEXT        NOT NULL REFERENCES rak.plugin_registry(plugin_id)
                                     ON DELETE CASCADE,
            version      TEXT        NOT NULL,
            changelog    TEXT        NOT NULL DEFAULT '',
            yaml_hash    CHAR(64)    NOT NULL,
            yaml_content JSONB       NOT NULL DEFAULT '{}'::jsonb,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            PRIMARY KEY (plugin_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_registry_jurisdiction
            ON rak.plugin_registry (jurisdiction);

        CREATE INDEX IF NOT EXISTS idx_registry_tags
            ON rak.plugin_registry USING gin (tags);

        CREATE INDEX IF NOT EXISTS idx_registry_name_trgm
            ON rak.plugin_registry USING gin (name gin_trgm_ops);

        -- Grant permissions to app role (if exists).
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rak_app') THEN
                GRANT SELECT, INSERT, UPDATE ON rak.plugin_registry TO rak_app;
                GRANT SELECT, INSERT ON rak.plugin_versions TO rak_app;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Drop plugin registry tables."""
    op.execute("""
        DROP TABLE IF EXISTS rak.plugin_versions;
        DROP TABLE IF EXISTS rak.plugin_registry;
    """)
