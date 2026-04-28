"""FastAPI dependency injection for shared resources."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request  # noqa: TC002


async def get_db_pool(request: Request) -> Any:
    """Return the database connection pool from app state.

    Returns ``None`` when the pool has not been initialised (tests, lite mode).
    """
    return getattr(request.app.state, "db_pool", None)


async def get_temporal_client(request: Request) -> Any:
    """Return the Temporal client from app state.

    Returns ``None`` when Temporal is unavailable (tests, lite mode).
    """
    return getattr(request.app.state, "temporal_client", None)


async def get_audit_signer(request: Request) -> Any:
    """Return the Ed25519 audit signer from app state.

    Returns ``None`` when the signer is not configured.
    """
    return getattr(request.app.state, "audit_signer", None)


async def get_settings(request: Request) -> Any:
    """Return application settings from app state."""
    return getattr(request.app.state, "settings", None)


async def get_plugin_registry(request: Request) -> Any:
    """Return a ``PluginRegistryStore`` implementation.

    Prefers a PostgreSQL-backed ``PluginRegistryRepository`` when a DB
    pool is available, and falls back to the process-local in-memory
    adapter used by tests and Lite Mode.
    """
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is not None:
        return _PooledRegistryProxy(db_pool)

    from regulatory_agent_kit.api.adapters.in_memory_registry import default_registry
    return default_registry


class _PooledRegistryProxy:
    """Thin proxy binding ``PluginRegistryRepository`` to a pool connection.

    Each call acquires a fresh connection so the proxy itself satisfies
    the ``PluginRegistryStore`` Protocol without leaking transaction state.
    """

    def __init__(self, db_pool: Any) -> None:
        self._db_pool = db_pool

    async def publish(
        self,
        plugin_id: str,
        name: str,
        version: str,
        jurisdiction: str,
        authority: str,
        description: str,
        author: str,
        tags: list[str],
        certification_tier: str,
        yaml_hash: str,
        yaml_content: dict[str, Any],
        changelog: str = "",
    ) -> dict[str, Any]:
        from regulatory_agent_kit.database.repositories.plugin_registry import (
            PluginRegistryRepository,
        )

        async with self._db_pool.connection() as conn:
            repo = PluginRegistryRepository(conn)
            row = await repo.publish(
                plugin_id=plugin_id,
                name=name,
                version=version,
                jurisdiction=jurisdiction,
                authority=authority,
                description=description,
                author=author,
                tags=tags,
                certification_tier=certification_tier,
                yaml_hash=yaml_hash,
                yaml_content=yaml_content,
                changelog=changelog,
            )
            await conn.commit()
            return row

    async def get(self, plugin_id: str) -> dict[str, Any] | None:
        from regulatory_agent_kit.database.repositories.plugin_registry import (
            PluginRegistryRepository,
        )

        async with self._db_pool.connection() as conn:
            return await PluginRegistryRepository(conn).get(plugin_id)

    async def search(
        self,
        query: str = "",
        jurisdiction: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        from regulatory_agent_kit.database.repositories.plugin_registry import (
            PluginRegistryRepository,
        )

        async with self._db_pool.connection() as conn:
            return await PluginRegistryRepository(conn).search(
                query=query,
                jurisdiction=jurisdiction,
                tags=tags,
                limit=limit,
                offset=offset,
            )

    async def list_versions(self, plugin_id: str) -> list[dict[str, Any]]:
        from regulatory_agent_kit.database.repositories.plugin_registry import (
            PluginRegistryRepository,
        )

        async with self._db_pool.connection() as conn:
            return await PluginRegistryRepository(conn).list_versions(plugin_id)

    async def get_version(
        self, plugin_id: str, version: str
    ) -> dict[str, Any] | None:
        from regulatory_agent_kit.database.repositories.plugin_registry import (
            PluginRegistryRepository,
        )

        async with self._db_pool.connection() as conn:
            return await PluginRegistryRepository(conn).get_version(
                plugin_id, version
            )
