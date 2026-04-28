"""File analysis cache — avoids redundant LLM calls on re-runs.

Wraps the ``FileAnalysisCacheRepository`` (PostgreSQL) or
``LiteFileAnalysisCacheRepository`` (SQLite) with cache-key computation
using ``SHA256(file_content + plugin_version + agent_version)`` as
defined in data-model.md Section 3.6 and architecture.md Section 10.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, cast, runtime_checkable

from regulatory_agent_kit.util.hashing import compute_cache_key

logger = logging.getLogger(__name__)

# Agent version included in the cache key — changes invalidate all entries.
_AGENT_VERSION = "0.1.0"


@runtime_checkable
class CacheStore(Protocol):
    """Minimal interface for the file analysis cache backend."""

    async def get(self, cache_key: str) -> dict[str, Any] | None: ...

    async def put(
        self,
        cache_key: str,
        repo_url: str,
        file_path: str,
        result: dict[str, Any],
        ttl_days: int = 7,
    ) -> None: ...

    async def delete_expired(self) -> int: ...


class FileAnalysisCache:
    """High-level cache for file-level analysis results.

    Computes a deterministic cache key from ``SHA256(content +
    plugin_version + agent_version)`` and delegates storage to the
    injected ``CacheStore`` backend.

    Usage::

        cache = FileAnalysisCache(store, plugin_version="1.0.0")

        # Check cache before expensive analysis
        result = await cache.lookup(file_content, repo_url, file_path)
        if result is not None:
            return result  # cache hit

        # Run analysis, then store
        result = await run_analysis(file_content)
        await cache.store(file_content, repo_url, file_path, result)
    """

    def __init__(
        self,
        store: CacheStore,
        plugin_version: str,
        *,
        ttl_days: int = 7,
        agent_version: str = _AGENT_VERSION,
    ) -> None:
        self._store = store
        self._plugin_version = plugin_version
        self._ttl_days = ttl_days
        self._agent_version = agent_version
        self._hits = 0
        self._misses = 0

    def _key(self, content: str) -> str:
        """Compute the cache key for the given file content."""
        return compute_cache_key(content, self._plugin_version, self._agent_version)

    async def lookup(
        self,
        content: str,
        repo_url: str,
        file_path: str,
    ) -> dict[str, Any] | None:
        """Look up a cached analysis result.

        Args:
            content: The file's text content.
            repo_url: Repository URL (for debugging, not part of the key).
            file_path: Relative file path (for debugging, not part of the key).

        Returns:
            The cached ``FileImpact``-equivalent dict, or ``None`` on miss.
        """
        key = self._key(content)
        row = await self._store.get(key)
        if row is None:
            self._misses += 1
            logger.debug("Cache MISS for %s:%s (key=%s…)", repo_url, file_path, key[:12])
            return None

        self._hits += 1
        logger.debug("Cache HIT for %s:%s (key=%s…)", repo_url, file_path, key[:12])
        raw_result = row.get("result", "{}")
        if isinstance(raw_result, str):
            result: dict[str, Any] = json.loads(raw_result)
            return result
        return cast("dict[str, Any]", raw_result)

    async def store(
        self,
        content: str,
        repo_url: str,
        file_path: str,
        result: dict[str, Any],
    ) -> None:
        """Store an analysis result in the cache.

        Args:
            content: The file's text content (used for key computation).
            repo_url: Repository URL.
            file_path: Relative file path.
            result: The analysis result dict to cache.
        """
        key = self._key(content)
        await self._store.put(
            cache_key=key,
            repo_url=repo_url,
            file_path=file_path,
            result=result,
            ttl_days=self._ttl_days,
        )
        logger.debug(
            "Cache STORE for %s:%s (key=%s, ttl=%dd)",
            repo_url, file_path, key[:12], self._ttl_days,
        )

    async def clean_expired(self) -> int:
        """Delete expired cache entries and return the count removed."""
        count = await self._store.delete_expired()
        logger.info("Cache cleanup: %d expired entries removed", count)
        return count

    @property
    def hits(self) -> int:
        """Total cache hits since creation."""
        return self._hits

    @property
    def misses(self) -> int:
        """Total cache misses since creation."""
        return self._misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a fraction (0.0 to 1.0)."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total
