"""Repository for plugin registry operations."""

from __future__ import annotations

import json
from typing import Any

from regulatory_agent_kit.database.repositories.base import BaseRepository


class PluginRegistryRepository(BaseRepository):
    """Data access for the plugin_registry and plugin_versions tables."""

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
        """Publish or update a plugin in the registry.

        Upserts the registry entry and inserts a new version record.
        """
        tags_json = json.dumps(tags)

        await self._execute(
            """
            INSERT INTO rak.plugin_registry
                (plugin_id, name, latest_version, jurisdiction, authority,
                 description, author, tags, certification_tier)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (plugin_id) DO UPDATE SET
                name = EXCLUDED.name,
                latest_version = EXCLUDED.latest_version,
                jurisdiction = EXCLUDED.jurisdiction,
                authority = EXCLUDED.authority,
                description = EXCLUDED.description,
                author = COALESCE(NULLIF(EXCLUDED.author, ''), rak.plugin_registry.author),
                tags = EXCLUDED.tags,
                certification_tier = EXCLUDED.certification_tier,
                published_at = now()
            """,
            (
                plugin_id, name, version, jurisdiction, authority,
                description, author, tags_json, certification_tier,
            ),
        )

        yaml_json = json.dumps(yaml_content)
        await self._execute(
            """
            INSERT INTO rak.plugin_versions
                (plugin_id, version, changelog, yaml_hash, yaml_content)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (plugin_id, version) DO NOTHING
            """,
            (plugin_id, version, changelog, yaml_hash, yaml_json),
        )

        return await self.get(plugin_id)  # type: ignore[return-value]

    async def get(self, plugin_id: str) -> dict[str, Any] | None:
        """Retrieve a plugin entry by ID."""
        return await self._fetch_one(
            "SELECT * FROM rak.plugin_registry WHERE plugin_id = %s",
            (plugin_id,),
        )

    async def search(
        self,
        query: str = "",
        jurisdiction: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search plugins with optional filters. Returns (entries, total)."""
        conditions: list[str] = []
        params: list[Any] = []

        if query:
            conditions.append(
                "(plugin_id ILIKE %s OR name ILIKE %s OR description ILIKE %s)"
            )
            like = f"%{query}%"
            params.extend([like, like, like])

        if jurisdiction:
            conditions.append("jurisdiction = %s")
            params.append(jurisdiction)

        if tags:
            conditions.append("tags @> %s::jsonb")
            params.append(json.dumps(tags))

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_sql = "SELECT count(*) AS total FROM rak.plugin_registry" + where_clause  # noqa: S608
        count_row = await self._fetch_one(count_sql, tuple(params))
        total = count_row["total"] if count_row else 0

        params.extend([limit, offset])
        list_sql = (
            "SELECT * FROM rak.plugin_registry"  # noqa: S608
            + where_clause
            + " ORDER BY published_at DESC LIMIT %s OFFSET %s"
        )
        rows = await self._fetch_all(list_sql, tuple(params))

        return rows, total

    async def list_versions(self, plugin_id: str) -> list[dict[str, Any]]:
        """List all published versions of a plugin."""
        return await self._fetch_all(
            """
            SELECT version, changelog, yaml_hash, published_at
            FROM rak.plugin_versions
            WHERE plugin_id = %s
            ORDER BY published_at DESC
            """,
            (plugin_id,),
        )

    async def get_version(
        self, plugin_id: str, version: str
    ) -> dict[str, Any] | None:
        """Retrieve a specific version including YAML content."""
        return await self._fetch_one(
            """
            SELECT * FROM rak.plugin_versions
            WHERE plugin_id = %s AND version = %s
            """,
            (plugin_id, version),
        )

    async def increment_downloads(self, plugin_id: str) -> None:
        """Increment the download counter for a plugin."""
        await self._execute(
            """
            UPDATE rak.plugin_registry
            SET downloads = downloads + 1
            WHERE plugin_id = %s
            """,
            (plugin_id,),
        )
