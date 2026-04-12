"""Plugin registry API routes.

The routes depend only on a :class:`PluginRegistryStore` protocol
resolved via :func:`get_plugin_registry`, so the same code path serves
PostgreSQL-backed deployments, in-memory test doubles, and Lite Mode.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from regulatory_agent_kit.api.adapters.in_memory_registry import (
    InMemoryPluginRegistry,
    default_registry,
)
from regulatory_agent_kit.api.dependencies import get_plugin_registry
from regulatory_agent_kit.exceptions import PluginLoadError, PluginValidationError
from regulatory_agent_kit.models.registry import (
    PluginRegistryEntry,
    PluginSearchResult,
    PluginVersion,
    PublishRequest,
)
from regulatory_agent_kit.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])

# ---------------------------------------------------------------------------
# Test helpers (delegate to the shared in-memory adapter)
# ---------------------------------------------------------------------------


def seed_plugin(
    entry: dict[str, Any],
    versions: list[dict[str, Any]] | None = None,
) -> None:
    """Seed a plugin into the default in-memory registry (test helper)."""
    default_registry.seed(entry, versions)


def clear_registry() -> None:
    """Clear the default in-memory registry (test helper)."""
    default_registry.clear()


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
    store: Any = Depends(get_plugin_registry),  # noqa: B008
) -> PluginSearchResult:
    """Search published plugins by name, jurisdiction, or keyword."""
    offset = (page - 1) * limit
    rows, total = await store.search(
        query=q,
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


@router.get(
    "/{plugin_id}",
    response_model=PluginRegistryEntry,
    summary="Get plugin details",
)
async def get_plugin(
    plugin_id: str,
    store: Any = Depends(get_plugin_registry),  # noqa: B008
) -> PluginRegistryEntry:
    """Return metadata for a specific plugin."""
    row = await store.get(plugin_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin {plugin_id} not found.",
        )
    return _row_to_entry(row)


@router.get(
    "/{plugin_id}/versions",
    response_model=list[PluginVersion],
    summary="List plugin versions",
)
async def list_versions(
    plugin_id: str,
    store: Any = Depends(get_plugin_registry),  # noqa: B008
) -> list[PluginVersion]:
    """Return all published versions of a plugin."""
    rows = await store.list_versions(plugin_id)
    return [
        PluginVersion(
            version=r["version"],
            changelog=r.get("changelog", ""),
            yaml_hash=r["yaml_hash"],
            published_at=r["published_at"],
        )
        for r in rows
    ]


@router.post(
    "",
    response_model=PluginRegistryEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a plugin",
)
async def publish_plugin(
    request: PublishRequest,
    store: Any = Depends(get_plugin_registry),  # noqa: B008
) -> PluginRegistryEntry:
    """Publish or update a regulation plugin in the registry."""
    loader = PluginLoader()
    try:
        plugin = loader.load_from_string(request.yaml_content)
    except (PluginLoadError, PluginValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid plugin YAML: {exc}",
        ) from exc

    yaml_hash = hashlib.sha256(request.yaml_content.encode()).hexdigest()
    kwargs = _publish_kwargs(plugin, request, yaml_hash)
    row = await store.publish(**kwargs)
    return _row_to_entry(row)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _publish_kwargs(
    plugin: Any,
    request: PublishRequest,
    yaml_hash: str,
) -> dict[str, Any]:
    """Extract the kwargs passed to ``PluginRegistryStore.publish``."""
    return {
        "plugin_id": plugin.id,
        "name": plugin.name,
        "version": plugin.version,
        "jurisdiction": plugin.jurisdiction,
        "authority": plugin.authority,
        "description": plugin.rules[0].description if plugin.rules else "",
        "author": request.author,
        "tags": request.tags,
        "certification_tier": plugin.certification.tier,
        "yaml_hash": yaml_hash,
        "yaml_content": plugin.model_dump(mode="json"),
        "changelog": plugin.changelog,
    }


def _row_to_entry(row: dict[str, Any]) -> PluginRegistryEntry:
    """Convert a store row to a ``PluginRegistryEntry`` model."""
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


__all__ = [
    "InMemoryPluginRegistry",
    "clear_registry",
    "default_registry",
    "router",
    "seed_plugin",
]
