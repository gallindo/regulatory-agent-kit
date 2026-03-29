"""Tests for SearchClient — index management, ingestion, search, and RAG."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from regulatory_agent_kit.tools.search_client import (
    _CONTEXT_MAPPING,
    _REGULATIONS_MAPPING,
    ContextSearchStrategy,
    RulesSearchStrategy,
    SearchClient,
    VectorSearchStrategy,
)

# ======================================================================
# Graceful degradation when ES is unavailable
# ======================================================================


class TestSearchClientDegradation:
    async def test_search_rules_returns_empty_on_connection_error(self) -> None:
        client = SearchClient(es_url="http://localhost:9999")
        mock_es = AsyncMock()
        mock_es.search.side_effect = ConnectionError("Connection refused")

        with patch.object(client, "_client", mock_es):
            results = await client.search_rules("encryption")

        assert results == []

    async def test_search_context_returns_empty_on_connection_error(self) -> None:
        client = SearchClient(es_url="http://localhost:9999")
        mock_es = AsyncMock()
        mock_es.search.side_effect = ConnectionError("Connection refused")

        with patch.object(client, "_client", mock_es):
            results = await client.search_context("risk management")

        assert results == []

    async def test_ensure_index_does_not_raise_on_connection_error(self) -> None:
        client = SearchClient(es_url="http://localhost:9999")
        mock_es = AsyncMock()
        mock_es.indices.exists.side_effect = ConnectionError("Connection refused")

        with patch.object(client, "_client", mock_es):
            await client.ensure_index()

    async def test_index_regulation_does_not_raise_on_error(self) -> None:
        client = SearchClient(es_url="http://localhost:9999")
        mock_es = AsyncMock()
        mock_es.index.side_effect = ConnectionError("Connection refused")

        mock_plugin = MagicMock()
        mock_plugin.id = "dora-2025"
        mock_plugin.name = "DORA ICT Risk"
        mock_plugin.jurisdiction = "EU"
        mock_plugin.authority = "EBA"
        mock_plugin.rules = []
        mock_plugin.source_url = "https://example.com"
        mock_plugin.effective_date = "2025-01-17"

        with patch.object(client, "_client", mock_es):
            await client.index_regulation(mock_plugin)

    async def test_close_handles_errors(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.close.side_effect = RuntimeError("close failed")
        client._client = mock_es

        await client.close()
        assert client._client is None


# ======================================================================
# Index creation
# ======================================================================


class TestIndexCreation:
    async def test_ensure_index_creates_both_indexes(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.indices.exists.return_value = False
        mock_es.indices.create = AsyncMock()

        with patch.object(client, "_client", mock_es):
            await client.ensure_index()

        assert mock_es.indices.create.call_count == 2
        calls = mock_es.indices.create.call_args_list
        indexes_created = {c.kwargs["index"] for c in calls}
        assert "rak-regulations" in indexes_created
        assert "rak-regulation-context" in indexes_created

    async def test_ensure_index_skips_existing(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.indices.exists.return_value = True

        with patch.object(client, "_client", mock_es):
            await client.ensure_index()

        mock_es.indices.create.assert_not_called()

    def test_regulations_mapping_has_required_fields(self) -> None:
        props = _REGULATIONS_MAPPING["mappings"]["properties"]
        assert "regulation_id" in props
        assert "rule_id" in props
        assert "rule_description" in props
        assert props["rule_description"]["analyzer"] == "english"
        assert "content_chunk" in props
        assert "indexed_at" in props

    def test_context_mapping_has_embedding_field(self) -> None:
        props = _CONTEXT_MAPPING["mappings"]["properties"]
        assert "embedding" in props
        assert props["embedding"]["type"] == "dense_vector"
        assert props["embedding"]["dims"] == 1536
        assert props["embedding"]["similarity"] == "cosine"


# ======================================================================
# Plugin ingestion
# ======================================================================


class TestPluginIngestion:
    async def test_ingest_plugin_indexes_each_rule(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.index = AsyncMock()

        mock_rule_1 = MagicMock()
        mock_rule_1.id = "R-001"
        mock_rule_1.description = "Must have logging"
        mock_rule_1.severity = "high"
        mock_rule_1.affects = [MagicMock(condition="has_annotation(@Log)")]
        mock_rule_1.remediation = MagicMock(strategy="add_annotation")
        mock_rule_1.model_extra = {}

        mock_rule_2 = MagicMock()
        mock_rule_2.id = "R-002"
        mock_rule_2.description = "Must have RTO"
        mock_rule_2.severity = "medium"
        mock_rule_2.affects = [MagicMock(condition="has_key(rto)")]
        mock_rule_2.remediation = MagicMock(strategy="add_configuration")
        mock_rule_2.model_extra = {}

        mock_plugin = MagicMock()
        mock_plugin.id = "dora-2025"
        mock_plugin.name = "DORA"
        mock_plugin.jurisdiction = "EU"
        mock_plugin.authority = "EBA"
        mock_plugin.source_url = "https://example.com"
        mock_plugin.effective_date = "2025-01-17"
        mock_plugin.rules = [mock_rule_1, mock_rule_2]

        with patch.object(client, "_client", mock_es):
            count = await client.ingest_plugin(mock_plugin)

        assert count == 2
        assert mock_es.index.call_count == 2

        # Verify document IDs follow the convention
        call_ids = {c.kwargs["id"] for c in mock_es.index.call_args_list}
        assert "dora-2025:R-001" in call_ids
        assert "dora-2025:R-002" in call_ids

    async def test_ingest_empty_plugin_returns_zero(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_plugin = MagicMock()
        mock_plugin.id = "empty"
        mock_plugin.rules = []

        with patch.object(client, "_client", mock_es):
            count = await client.ingest_plugin(mock_plugin)

        assert count == 0


# ======================================================================
# Context chunk indexing
# ======================================================================


class TestContextChunkIndexing:
    async def test_index_context_chunk(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.index = AsyncMock()

        with patch.object(client, "_client", mock_es):
            await client.index_context_chunk(
                regulation_id="dora-2025",
                content="Article 5 requires ICT risk management.",
                section="Chapter II",
                article="Article 5",
                source_url="https://example.com",
                chunk_index=0,
                total_chunks=10,
            )

        mock_es.index.assert_called_once()
        doc = mock_es.index.call_args.kwargs["document"]
        assert doc["regulation_id"] == "dora-2025"
        assert doc["content"] == "Article 5 requires ICT risk management."
        assert doc["section"] == "Chapter II"

    async def test_index_context_chunk_with_embedding(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.index = AsyncMock()

        embedding = [0.1] * 1536
        with patch.object(client, "_client", mock_es):
            await client.index_context_chunk(
                regulation_id="dora-2025",
                content="Test content",
                embedding=embedding,
            )

        doc = mock_es.index.call_args.kwargs["document"]
        assert "embedding" in doc
        assert len(doc["embedding"]) == 1536


# ======================================================================
# Vector search
# ======================================================================


class TestVectorSearch:
    async def test_search_by_vector(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"content": "ICT risk management", "section": "Art 5"}},
                ]
            }
        }

        with patch.object(client, "_client", mock_es):
            results = await client.search_by_vector([0.1] * 1536, k=3)

        assert len(results) == 1
        assert results[0]["content"] == "ICT risk management"

    def test_vector_strategy_builds_knn_query(self) -> None:
        strategy = VectorSearchStrategy()
        body = strategy.build_query(embedding=[0.1, 0.2], k=3, num_candidates=20)
        assert "knn" in body
        assert body["knn"]["field"] == "embedding"
        assert body["knn"]["k"] == 3


# ======================================================================
# RAG context assembly
# ======================================================================


class TestBuildRagContext:
    async def test_returns_empty_when_no_results(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.search.return_value = {"hits": {"hits": []}}

        with patch.object(client, "_client", mock_es):
            ctx = await client.build_rag_context("audit logging")

        assert ctx == ""

    async def test_includes_rules_and_context(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()

        # First call (search_rules) returns rules, second (search_context) returns context
        mock_es.search.side_effect = [
            {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "rule_id": "R-001",
                                "rule_description": "Must have audit logging",
                                "severity": "high",
                                "condition": "has_annotation(@AuditLog)",
                            }
                        }
                    ]
                }
            },
            {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "section": "Chapter II",
                                "article": "Article 5",
                                "content": "Financial entities shall implement "
                                "ICT risk management.",
                            }
                        }
                    ]
                }
            },
        ]

        with patch.object(client, "_client", mock_es):
            ctx = await client.build_rag_context("audit logging")

        assert "R-001" in ctx
        assert "audit logging" in ctx.lower()
        assert "Article 5" in ctx
        assert "ICT risk management" in ctx


# ======================================================================
# Strategy patterns
# ======================================================================


class TestSearchStrategies:
    def test_rules_strategy_with_regulation_filter(self) -> None:
        strategy = RulesSearchStrategy()
        body = strategy.build_query(query="logging", regulation_id="dora-2025")
        assert "filter" in body["query"]["bool"]

    def test_rules_strategy_without_filter(self) -> None:
        strategy = RulesSearchStrategy()
        body = strategy.build_query(query="logging")
        assert "filter" not in body["query"]["bool"]

    def test_context_strategy_respects_limit(self) -> None:
        strategy = ContextSearchStrategy()
        body = strategy.build_query(query="risk", limit=3)
        assert body["size"] == 3
