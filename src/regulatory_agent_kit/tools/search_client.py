"""Async Elasticsearch client for regulation indexing and search."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from regulatory_agent_kit.exceptions import ToolError

try:
    from elasticsearch import ElasticsearchException
except ImportError:
    ElasticsearchException = Exception  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Index names
# ---------------------------------------------------------------------------

REGULATIONS_INDEX = "rak-regulations"
CONTEXT_INDEX = "rak-regulation-context"


# ---------------------------------------------------------------------------
# Index settings / mappings
# ---------------------------------------------------------------------------

_REGULATIONS_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "regulation_id": {"type": "keyword"},
            "name": {"type": "text"},
            "jurisdiction": {"type": "keyword"},
            "authority": {"type": "keyword"},
            "rules": {
                "type": "nested",
                "properties": {
                    "id": {"type": "keyword"},
                    "description": {"type": "text"},
                    "severity": {"type": "keyword"},
                },
            },
        }
    }
}

_CONTEXT_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "regulation_id": {"type": "keyword"},
            "rule_id": {"type": "keyword"},
            "content": {"type": "text"},
            "section": {"type": "keyword"},
        }
    }
}


def _extract_hits(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract source documents from an Elasticsearch search response."""
    return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]


# ---------------------------------------------------------------------------
# Search client
# ---------------------------------------------------------------------------


@dataclass
class SearchClient:
    """Async wrapper around Elasticsearch for regulation search.

    Gracefully degrades when Elasticsearch is unavailable — methods return
    empty results and log a warning rather than raising.
    """

    es_url: str = "http://localhost:9200"
    regulations_index: str = "rak-regulations"
    context_index: str = "rak-regulation-context"
    _client: Any = field(default=None, init=False, repr=False)

    async def _get_client(self) -> Any:
        """Lazily initialise the ``AsyncElasticsearch`` client."""
        if self._client is None:
            try:
                from elasticsearch import AsyncElasticsearch

                self._client = AsyncElasticsearch(hosts=[self.es_url])
            except ImportError as exc:
                msg = "elasticsearch[async] package is not installed"
                raise ToolError(msg) from exc
        return self._client

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    async def ensure_index(self) -> None:
        """Create regulation indexes if they do not exist."""
        try:
            client = await self._get_client()
            for index_name, mapping in (
                (self.regulations_index, _REGULATIONS_MAPPING),
                (self.context_index, _CONTEXT_MAPPING),
            ):
                exists = await client.indices.exists(index=index_name)
                if not exists:
                    await client.indices.create(index=index_name, body=mapping)
                    logger.info("Created index: %s", index_name)
        except ElasticsearchException:
            logger.warning("Elasticsearch unavailable — skipping index creation", exc_info=True)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_regulation(self, plugin: Any) -> None:
        """Index a regulation plugin document."""
        try:
            client = await self._get_client()
            doc = {
                "regulation_id": plugin.id,
                "name": plugin.name,
                "jurisdiction": plugin.jurisdiction,
                "authority": plugin.authority,
                "rules": [
                    {
                        "id": r.id,
                        "description": r.description,
                        "severity": r.severity,
                    }
                    for r in plugin.rules
                ],
            }
            await client.index(
                index=self.regulations_index,
                id=plugin.id,
                document=doc,
            )
            logger.info("Indexed regulation: %s", plugin.id)
        except ElasticsearchException:
            logger.warning(
                "Elasticsearch unavailable — could not index regulation %s",
                getattr(plugin, "id", "?"),
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_rules(
        self,
        query: str,
        regulation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search regulation rules by text query, optionally filtered by regulation."""
        try:
            client = await self._get_client()
            body: dict[str, Any] = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "nested": {
                                    "path": "rules",
                                    "query": {"match": {"rules.description": query}},
                                }
                            }
                        ],
                    }
                }
            }
            if regulation_id:
                body["query"]["bool"]["filter"] = [{"term": {"regulation_id": regulation_id}}]

            resp = await client.search(index=self.regulations_index, body=body)
            return _extract_hits(resp)
        except ElasticsearchException:
            logger.warning("Elasticsearch unavailable — returning empty results", exc_info=True)
            return []

    async def search_context(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search against the regulation context index."""
        try:
            client = await self._get_client()
            body: dict[str, Any] = {
                "query": {"match": {"content": query}},
                "size": limit,
            }
            resp = await client.search(index=self.context_index, body=body)
            return _extract_hits(resp)
        except ElasticsearchException:
            logger.warning("Elasticsearch unavailable — returning empty results", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying Elasticsearch client."""
        if self._client is not None:
            try:
                await self._client.close()
            except ElasticsearchException:
                logger.warning("Error closing Elasticsearch client", exc_info=True)
            finally:
                self._client = None
