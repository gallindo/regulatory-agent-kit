"""In-memory PluginRegistryStore adapter used when no DB pool is available.

Provides a lightweight fallback for tests and Lite Mode so the FastAPI
routes can depend on a single ``PluginRegistryStore`` abstraction
instead of special-casing ``db_pool is None``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class InMemoryPluginRegistry:
    """Process-local registry implementing :class:`PluginRegistryStore`.

    Data lives in module-level dicts owned by the instance; callers share
    state by sharing the same instance (see ``default_registry``).
    """

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, list[dict[str, Any]]] = {}

    # -- test helpers -------------------------------------------------------

    def seed(
        self,
        entry: dict[str, Any],
        versions: list[dict[str, Any]] | None = None,
    ) -> None:
        """Seed a plugin entry (and optional versions) for tests."""
        self._entries[entry["plugin_id"]] = entry
        if versions:
            self._versions[entry["plugin_id"]] = versions

    def clear(self) -> None:
        """Remove all entries (test helper)."""
        self._entries.clear()
        self._versions.clear()

    # -- PluginRegistryStore protocol ---------------------------------------

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
        """Store a published plugin entry and append a version record."""
        now = datetime.now(UTC)
        entry = {
            "plugin_id": plugin_id,
            "name": name,
            "latest_version": version,
            "jurisdiction": jurisdiction,
            "authority": authority,
            "description": description,
            "author": author,
            "published_at": now,
            "downloads": self._entries.get(plugin_id, {}).get("downloads", 0),
            "tags": tags,
            "certification_tier": certification_tier,
            "metadata": {},
        }
        self._entries[plugin_id] = entry

        version_entry = {
            "plugin_id": plugin_id,
            "version": version,
            "changelog": changelog,
            "yaml_hash": yaml_hash,
            "yaml_content": yaml_content,
            "published_at": now,
        }
        self._versions.setdefault(plugin_id, []).insert(0, version_entry)
        return entry

    async def get(self, plugin_id: str) -> dict[str, Any] | None:
        return self._entries.get(plugin_id)

    async def search(
        self,
        query: str = "",
        jurisdiction: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        entries = list(self._entries.values())
        if query:
            q_lower = query.lower()
            entries = [
                e
                for e in entries
                if q_lower in e.get("plugin_id", "").lower()
                or q_lower in e.get("name", "").lower()
                or q_lower in e.get("description", "").lower()
            ]
        if jurisdiction:
            entries = [e for e in entries if e.get("jurisdiction") == jurisdiction]
        if tags:
            entries = [e for e in entries if all(tag in e.get("tags", []) for tag in tags)]
        total = len(entries)
        return entries[offset : offset + limit], total

    async def list_versions(self, plugin_id: str) -> list[dict[str, Any]]:
        return list(self._versions.get(plugin_id, []))

    async def get_version(self, plugin_id: str, version: str) -> dict[str, Any] | None:
        for entry in self._versions.get(plugin_id, []):
            if entry.get("version") == version:
                return entry
        return None


# Module-level default instance — shared by the FastAPI routes and their
# test helpers so tests can seed/clear without instantiating their own
# store.
default_registry = InMemoryPluginRegistry()
