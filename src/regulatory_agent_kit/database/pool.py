"""Psycopg 3 async connection pool management."""

from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from regulatory_agent_kit.config import DatabaseSettings  # noqa: TC001

_pool: AsyncConnectionPool | None = None


async def create_pool(settings: DatabaseSettings) -> AsyncConnectionPool:
    """Create and open an async connection pool from database settings."""
    global _pool
    pool = AsyncConnectionPool(
        conninfo=settings.url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        open=False,
    )
    await pool.open()
    _pool = pool
    return pool


async def close_pool() -> None:
    """Close the global connection pool gracefully."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    """Return the current global pool, raising if not initialized."""
    if _pool is None:
        msg = "Database pool has not been initialized. Call create_pool() first."
        raise RuntimeError(msg)
    return _pool
