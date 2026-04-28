"""Async Elasticsearch client for regulation indexing, search, and RAG context retrieval.

Provides index setup with mappings from data-model.md Section 6,
regulation plugin ingestion, full-text and kNN vector search, and
RAG context assembly for the Analyzer agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from regulatory_agent_kit.exceptions import ToolError

try:
    from elasticsearch import ElasticsearchException  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    ElasticsearchException = Exception

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search strategies (Strategy pattern)
# ---------------------------------------------------------------------------


@runtime_checkable
class SearchStrategy(Protocol):
    """Strategy for building Elasticsearch query bodies."""

    def build_query(self, **kwargs: Any) -> dict[str, Any]: ...


class RulesSearchStrategy:
    """Builds nested rules search queries."""

    def build_query(
        self,
        *,
        query: str,
        regulation_id: str | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Build an ES query body for rule description search."""
        body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"rule_description": query}},
                    ],
                }
            }
        }
        if regulation_id:
            body["query"]["bool"]["filter"] = [
                {"term": {"regulation_id": regulation_id}}
            ]
        return body


class ContextSearchStrategy:
    """Builds full-text context search queries."""

    def build_query(
        self,
        *,
        query: str,
        limit: int = 10,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Build an ES query body for full-text context search."""
        return {"query": {"match": {"content": query}}, "size": limit}


class VectorSearchStrategy:
    """Builds kNN vector search queries for semantic retrieval."""

    def build_query(
        self,
        *,
        embedding: list[float],
        k: int = 5,
        num_candidates: int = 50,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Build an ES kNN query body for dense vector search."""
        return {
            "knn": {
                "field": "embedding",
                "query_vector": embedding,
                "k": k,
                "num_candidates": num_candidates,
            },
        }


# ---------------------------------------------------------------------------
# Index names
# ---------------------------------------------------------------------------

REGULATIONS_INDEX = "rak-regulations"
CONTEXT_INDEX = "rak-regulation-context"


# ---------------------------------------------------------------------------
# Index mappings (data-model.md Section 6)
# ---------------------------------------------------------------------------

_REGULATIONS_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "regulation_id": {"type": "keyword"},
            "regulation_name": {"type": "text", "analyzer": "standard"},
            "rule_id": {"type": "keyword"},
            "rule_description": {
                "type": "text",
                "analyzer": "english",
                "fields": {"exact": {"type": "keyword"}},
            },
            "severity": {"type": "keyword"},
            "jurisdiction": {"type": "keyword"},
            "authority": {"type": "keyword"},
            "effective_date": {"type": "date"},
            "pillar": {"type": "keyword"},
            "rts_reference": {"type": "keyword"},
            "condition": {"type": "text"},
            "remediation_strategy": {"type": "keyword"},
            "source_url": {"type": "keyword"},
            "content_chunk": {
                "type": "text",
                "analyzer": "english",
                "term_vector": "with_positions_offsets",
            },
            "chunk_index": {"type": "integer"},
            "indexed_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "regulation_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"],
                }
            }
        },
    },
}

_CONTEXT_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "regulation_id": {"type": "keyword"},
            "document_title": {"type": "text"},
            "section": {"type": "keyword"},
            "article": {"type": "keyword"},
            "paragraph": {"type": "keyword"},
            "content": {"type": "text", "analyzer": "english"},
            "embedding": {
                "type": "dense_vector",
                "dims": 1536,
                "index": True,
                "similarity": "cosine",
            },
            "source_url": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "total_chunks": {"type": "integer"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
    },
}


def _extract_hits(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract source documents from an Elasticsearch search response."""
    hits_wrapper = resp.get("hits", {})
    hit_list: list[dict[str, Any]] = (
        hits_wrapper.get("hits", []) if isinstance(hits_wrapper, dict) else []
    )
    return [hit["_source"] for hit in hit_list]


# ---------------------------------------------------------------------------
# Search client
# ---------------------------------------------------------------------------


@dataclass
class SearchClient:
    """Async wrapper around Elasticsearch for regulation search and RAG.

    Gracefully degrades when Elasticsearch is unavailable — methods return
    empty results and log a warning rather than raising.
    """

    es_url: str = "http://localhost:9200"
    regulations_index: str = REGULATIONS_INDEX
    context_index: str = CONTEXT_INDEX
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
        """Create regulation indexes with full mappings if they do not exist."""
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
            logger.warning(
                "Elasticsearch unavailable — skipping index creation",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Regulation ingestion
    # ------------------------------------------------------------------

    async def index_regulation(self, plugin: Any) -> None:
        """Index a regulation plugin as a single summary document."""
        try:
            client = await self._get_client()
            doc = {
                "regulation_id": plugin.id,
                "regulation_name": plugin.name,
                "jurisdiction": plugin.jurisdiction,
                "authority": plugin.authority,
                "source_url": str(getattr(plugin, "source_url", "")),
                "effective_date": str(getattr(plugin, "effective_date", "")),
                "indexed_at": datetime.now(UTC).isoformat(),
            }
            await client.index(
                index=self.regulations_index,
                id=plugin.id,
                document=doc,
            )
            logger.info("Indexed regulation summary: %s", plugin.id)
        except ElasticsearchException:
            logger.warning(
                "Elasticsearch unavailable — could not index regulation %s",
                getattr(plugin, "id", "?"),
                exc_info=True,
            )

    async def ingest_plugin(self, plugin: Any) -> int:
        """Ingest a regulation plugin: index each rule as a separate document.

        Indexes one document per rule into ``rak-regulations`` with
        all fields from data-model.md Section 6.1, enabling per-rule
        search by description, severity, condition, or strategy.

        Returns:
            The number of rule documents indexed.
        """
        count = 0
        try:
            client = await self._get_client()
            for rule in getattr(plugin, "rules", []):
                doc: dict[str, Any] = {
                    "regulation_id": plugin.id,
                    "regulation_name": plugin.name,
                    "rule_id": rule.id,
                    "rule_description": rule.description.strip(),
                    "severity": rule.severity,
                    "jurisdiction": plugin.jurisdiction,
                    "authority": plugin.authority,
                    "effective_date": str(getattr(plugin, "effective_date", "")),
                    "source_url": str(getattr(plugin, "source_url", "")),
                    "condition": " | ".join(
                        a.condition for a in rule.affects
                    ),
                    "remediation_strategy": rule.remediation.strategy,
                    "indexed_at": datetime.now(UTC).isoformat(),
                }
                # Include optional plugin-specific fields
                for extra_field in ("pillar", "rts_reference"):
                    val = getattr(rule, extra_field, None) or rule.model_extra.get(extra_field)
                    if val:
                        doc[extra_field] = val

                doc_id = f"{plugin.id}:{rule.id}"
                await client.index(
                    index=self.regulations_index,
                    id=doc_id,
                    document=doc,
                )
                count += 1

            logger.info(
                "Ingested %d rules from plugin %s", count, plugin.id
            )
        except ElasticsearchException:
            logger.warning(
                "Elasticsearch unavailable — ingestion incomplete for %s",
                getattr(plugin, "id", "?"),
                exc_info=True,
            )
        return count

    async def index_context_chunk(
        self,
        *,
        regulation_id: str,
        content: str,
        section: str = "",
        article: str = "",
        paragraph: str = "",
        document_title: str = "",
        source_url: str = "",
        chunk_index: int = 0,
        total_chunks: int = 1,
        embedding: list[float] | None = None,
    ) -> None:
        """Index a single regulation context chunk for RAG retrieval.

        Args:
            regulation_id: Plugin ID this chunk belongs to.
            content: The text content of the chunk.
            section/article/paragraph: Structural location metadata.
            document_title: Title of the source document.
            source_url: URL of the source regulation.
            chunk_index: Position of this chunk in the document.
            total_chunks: Total number of chunks in the document.
            embedding: Optional dense vector (1536 dims) for kNN search.
        """
        try:
            client = await self._get_client()
            doc: dict[str, Any] = {
                "regulation_id": regulation_id,
                "document_title": document_title,
                "section": section,
                "article": article,
                "paragraph": paragraph,
                "content": content,
                "source_url": source_url,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
            }
            if embedding is not None:
                doc["embedding"] = embedding

            doc_id = f"{regulation_id}:{section}:{chunk_index}"
            await client.index(
                index=self.context_index,
                id=doc_id,
                document=doc,
            )
        except ElasticsearchException:
            logger.warning(
                "Failed to index context chunk %s:%s:%d",
                regulation_id,
                section,
                chunk_index,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def _search_with_strategy(
        self,
        index: str,
        strategy: SearchStrategy,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Execute a search using the given strategy to build the query."""
        try:
            client = await self._get_client()
            body = strategy.build_query(**kwargs)
            resp = await client.search(index=index, body=body)
            return _extract_hits(resp)
        except ElasticsearchException:
            logger.warning("ES unavailable", exc_info=True)
            return []

    async def search_rules(
        self,
        query: str,
        regulation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search regulation rules by text query."""
        return await self._search_with_strategy(
            self.regulations_index,
            RulesSearchStrategy(),  # type: ignore[arg-type]
            query=query,
            regulation_id=regulation_id,
        )

    async def search_context(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search against the regulation context index."""
        return await self._search_with_strategy(
            self.context_index,
            ContextSearchStrategy(),  # type: ignore[arg-type]
            query=query,
            limit=limit,
        )

    async def search_by_vector(
        self,
        embedding: list[float],
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic kNN vector search against the regulation context index.

        Args:
            embedding: Query embedding vector (1536 dims for cosine similarity).
            k: Number of nearest neighbours to return.

        Returns:
            List of matching context documents sorted by similarity.
        """
        return await self._search_with_strategy(
            self.context_index,
            VectorSearchStrategy(),  # type: ignore[arg-type]
            embedding=embedding,
            k=k,
        )

    # ------------------------------------------------------------------
    # RAG context assembly
    # ------------------------------------------------------------------

    async def build_rag_context(
        self,
        query: str,
        regulation_id: str | None = None,
        max_chunks: int = 5,
    ) -> str:
        """Assemble RAG context for an LLM prompt.

        Retrieves relevant regulation rules and context chunks, then
        formats them as a single context string suitable for injection
        into an agent's system prompt.

        Args:
            query: The analysis query or condition being evaluated.
            regulation_id: Optional filter to a specific regulation.
            max_chunks: Maximum number of context chunks to include.

        Returns:
            Formatted context string for LLM prompt injection.
        """
        sections: list[str] = []

        # 1. Fetch matching rules
        rules = await self.search_rules(query, regulation_id=regulation_id)
        if rules:
            sections.append("## Matching Regulation Rules\n")
            for rule in rules[:max_chunks]:
                rid = rule.get("rule_id", "?")
                desc = rule.get("rule_description", rule.get("description", ""))
                sev = rule.get("severity", "")
                cond = rule.get("condition", "")
                sections.append(
                    f"- **{rid}** ({sev}): {desc}"
                )
                if cond:
                    sections.append(f"  Condition: `{cond}`")

        # 2. Fetch context chunks
        context_hits = await self.search_context(query, limit=max_chunks)
        if context_hits:
            sections.append("\n## Regulation Context\n")
            for chunk in context_hits:
                sec = chunk.get("section", "")
                art = chunk.get("article", "")
                content = chunk.get("content", "")
                header = " ".join(filter(None, [sec, art])).strip()
                if header:
                    sections.append(f"### {header}\n")
                sections.append(content)

        if not sections:
            return ""

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying Elasticsearch client."""
        if self._client is not None:
            try:
                await self._client.close()
            except ElasticsearchException:
                logger.warning(
                    "Error closing Elasticsearch client", exc_info=True
                )
            finally:
                self._client = None
