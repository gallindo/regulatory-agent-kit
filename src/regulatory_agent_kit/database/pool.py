"""Psycopg 3 async connection pool management."""

from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from regulatory_agent_kit.config import DatabaseSettings  # noqa: TC001


class PoolManager:
    """Manages the lifecycle of a Psycopg 3 async connection pool."""

    def __init__(self) -> None:
        self._pool: AsyncConnectionPool | None = None

    async def create(self, settings: DatabaseSettings) -> AsyncConnectionPool:
        """Create and open an async connection pool from database settings."""
        pool = AsyncConnectionPool(
            conninfo=settings.url,
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
            open=False,
        )
        await pool.open()
        self._pool = pool
        return pool

    async def close(self) -> None:
        """Close the managed connection pool gracefully."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def get(self) -> AsyncConnectionPool:
        """Return the current pool, raising if not initialized."""
        if self._pool is None:
            msg = "Database pool has not been initialized. Call create_pool() first."
            raise RuntimeError(msg)
        return self._pool


# ---------------------------------------------------------------------------
# Default instance & backward-compatible module-level functions
# ---------------------------------------------------------------------------

_default_manager = PoolManager()


# Backward-compatible module-level ``_pool`` attribute used by existing tests
# that directly inspect or reset the internal pool reference.
def __getattr__(name: str) -> object:
    if name == "_pool":
        return _default_manager._pool
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __setattr__(name: str, value: object) -> None:  # noqa: N807
    if name == "_pool":
        _default_manager._pool = value  # type: ignore[assignment]
        return
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


async def create_pool(settings: DatabaseSettings) -> AsyncConnectionPool:
    """Create and open an async connection pool from database settings."""
    return await _default_manager.create(settings)


async def close_pool() -> None:
    """Close the global connection pool gracefully."""
    await _default_manager.close()


def get_pool() -> AsyncConnectionPool:
    """Return the current global pool, raising if not initialized."""
    return _default_manager.get()
