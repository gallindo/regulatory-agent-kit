"""Alembic environment configuration.

Supports DATABASE_URL environment variable override for the connection string.
Falls back to sqlalchemy.url in alembic.ini if the env var is not set.
"""

import os

from alembic import context

target_metadata = None


def _get_url() -> str:
    """Return the database URL from env var or alembic.ini."""
    return os.environ.get(
        "DATABASE_URL",
        context.config.get_main_option("sqlalchemy.url", ""),
    )


if context.is_offline_mode():
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    from sqlalchemy import create_engine

    engine = create_engine(_get_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="rak",
        )
        with context.begin_transaction():
            context.run_migrations()
