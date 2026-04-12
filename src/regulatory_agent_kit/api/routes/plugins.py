"""Plugin registry API routes."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from regulatory_agent_kit.api.dependencies import get_db_pool
from regulatory_agent_kit.models.registry import (
    PluginRegistryEntry,
    PluginSearchResult,
    PluginVersion,
    PublishRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])

# ---------------------------------------------------------------------------
# In-memory fallback (used when DB is unavailable, e.g. in tests)
# ---------------------------------------------------------------------------

_registry: dict[str, dict[str, Any]] = {}
_versions: dict[str, list[dict[str, Any]]] = {}


def seed_plugin(entry: dict[str, Any], versions: list[dict[str, Any]] | None = None) -> None:
    """Seed a plugin into the in-memory store (test helper)."""
    _registry[entry["plugin_id"]] = entry
    if versions:
        _versions[entry["plugin_id"]] = versions


def clear_registry() -> None:
    """Remove all seeded plugins (test helper)."""
    _registry.clear()
    _versions.clear()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PluginSearchResult,
    summary="Search the plugin registry",
)
async def search_plugins(
    q: str = Query(default="", description="Search term"),
    jurisdiction: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> PluginSearchResult:
    """Search published plugins by name, jurisdiction, or keyword."""
    if db_pool is not None:
        return await _search_from_db(q, jurisdiction, page, limit, db_pool)

    entries = list(_registry.values())
    if q:
        q_lower = q.lower()
        entries = [
            e for e in entries
            if q_lower in e.get("plugin_id", "").lower()
            or q_lower in e.get("name", "").lower()
            or q_lower in e.get("description", "").lower()
        ]
    if jurisdiction:
        entries = [e for e in entries if e.get("jurisdiction") == jurisdiction]

    total = len(entries)
    start = (page - 1) * limit
    page_entries = entries[start : start + limit]

    return PluginSearchResult(
        entries=[PluginRegistryEntry(**e) for e in page_entries],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{plugin_id}",
    response_model=PluginRegistryEntry,
    summary="Get plugin details",
)
async def get_plugin(
    plugin_id: str,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> PluginRegistryEntry:
    """Return metadata for a specific plugin."""
    if db_pool is not None:
        return await _get_from_db(plugin_id, db_pool)

    entry = _registry.get(plugin_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin {plugin_id} not found.",
        )
    return PluginRegistryEntry(**entry)


@router.get(
    "/{plugin_id}/versions",
    response_model=list[PluginVersion],
    summary="List plugin versions",
)
async def list_versions(
    plugin_id: str,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> list[PluginVersion]:
    """Return all published versions of a plugin."""
    if db_pool is not None:
        return await _list_versions_from_db(plugin_id, db_pool)

    versions = _versions.get(plugin_id, [])
    return [PluginVersion(**v) for v in versions]


@router.post(
    "",
    response_model=PluginRegistryEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a plugin",
)
async def publish_plugin(
    request: PublishRequest,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> PluginRegistryEntry:
    """Publish or update a regulation plugin in the registry."""
    from regulatory_agent_kit.exceptions import PluginLoadError, PluginValidationError
    from regulatory_agent_kit.plugins.loader import PluginLoader

    loader = PluginLoader()
    try:
        plugin = loader.load_from_string(request.yaml_content)
    except (PluginLoadError, PluginValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid plugin YAML: {exc}",
        ) from exc

    yaml_hash = hashlib.sha256(request.yaml_content.encode()).hexdigest()

    if db_pool is not None:
        return await _publish_to_db(plugin, yaml_hash, request, db_pool)

    # In-memory fallback
    from datetime import UTC, datetime

    entry = {
        "plugin_id": plugin.id,
        "name": plugin.name,
        "latest_version": plugin.version,
        "jurisdiction": plugin.jurisdiction,
        "authority": plugin.authority,
        "description": plugin.rules[0].description if plugin.rules else "",
        "author": request.author,
        "published_at": datetime.now(UTC),
        "downloads": 0,
        "tags": request.tags,
        "certification_tier": plugin.certification.tier,
        "metadata": {},
    }
    _registry[plugin.id] = entry

    version_entry = {
        "version": plugin.version,
        "changelog": plugin.changelog,
        "yaml_hash": yaml_hash,
        "published_at": datetime.now(UTC),
    }
    _versions.setdefault(plugin.id, []).insert(0, version_entry)

    return PluginRegistryEntry(**entry)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def _search_from_db(
    query: str,
    jurisdiction: str | None,
    page: int,
    limit: int,
    db_pool: Any,
) -> PluginSearchResult:
    from regulatory_agent_kit.database.repositories.plugin_registry import (
        PluginRegistryRepository,
    )

    offset = (page - 1) * limit
    async with db_pool.connection() as conn:
        repo = PluginRegistryRepository(conn)
        rows, total = await repo.search(
            query=query,
            jurisdiction=jurisdiction,
            limit=limit,
            offset=offset,
        )

    return PluginSearchResult(
        entries=[_row_to_entry(r) for r in rows],
        total=total,
        page=page,
        limit=limit,
    )


async def _get_from_db(plugin_id: str, db_pool: Any) -> PluginRegistryEntry:
    from regulatory_agent_kit.database.repositories.plugin_registry import (
        PluginRegistryRepository,
    )

    async with db_pool.connection() as conn:
        repo = PluginRegistryRepository(conn)
        row = await repo.get(plugin_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin {plugin_id} not found.",
        )
    return _row_to_entry(row)


async def _list_versions_from_db(plugin_id: str, db_pool: Any) -> list[PluginVersion]:
    from regulatory_agent_kit.database.repositories.plugin_registry import (
        PluginRegistryRepository,
    )

    async with db_pool.connection() as conn:
        repo = PluginRegistryRepository(conn)
        rows = await repo.list_versions(plugin_id)

    return [
        PluginVersion(
            version=r["version"],
            changelog=r.get("changelog", ""),
            yaml_hash=r["yaml_hash"],
            published_at=r["published_at"],
        )
        for r in rows
    ]


async def _publish_to_db(
    plugin: Any,
    yaml_hash: str,
    request: PublishRequest,
    db_pool: Any,
) -> PluginRegistryEntry:
    from regulatory_agent_kit.database.repositories.plugin_registry import (
        PluginRegistryRepository,
    )

    if request.yaml_content.strip().startswith("{"):
        yaml_content = json.loads(request.yaml_content)
    else:
        yaml_content = {"raw": request.yaml_content}

    async with db_pool.connection() as conn:
        repo = PluginRegistryRepository(conn)
        row = await repo.publish(
            plugin_id=plugin.id,
            name=plugin.name,
            version=plugin.version,
            jurisdiction=plugin.jurisdiction,
            authority=plugin.authority,
            description=plugin.rules[0].description if plugin.rules else "",
            author=request.author,
            tags=request.tags,
            certification_tier=plugin.certification.tier,
            yaml_hash=yaml_hash,
            yaml_content=yaml_content,
            changelog=plugin.changelog,
        )
        await conn.commit()

    return _row_to_entry(row)


def _row_to_entry(row: dict[str, Any]) -> PluginRegistryEntry:
    """Convert a DB row to a PluginRegistryEntry model."""
    tags = row.get("tags", [])
    if isinstance(tags, str):
        tags = json.loads(tags)
    metadata = row.get("metadata", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    return PluginRegistryEntry(
        plugin_id=row["plugin_id"],
        name=row["name"],
        latest_version=row["latest_version"],
        jurisdiction=row.get("jurisdiction", ""),
        authority=row.get("authority", ""),
        description=row.get("description", ""),
        author=row.get("author", ""),
        published_at=row["published_at"],
        downloads=row.get("downloads", 0),
        tags=tags,
        certification_tier=row.get("certification_tier", "technically_valid"),
        metadata=metadata,
    )
