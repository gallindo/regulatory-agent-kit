"""Tests for SearchClient graceful degradation (Phase 7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from regulatory_agent_kit.tools.search_client import SearchClient

# ======================================================================
# Graceful degradation when ES is unavailable
# ======================================================================


class TestSearchClientDegradation:
    """Verify SearchClient returns empty results when ES is unreachable."""

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
            # Should not raise
            await client.ensure_index()

    async def test_index_regulation_does_not_raise_on_error(self) -> None:
        client = SearchClient(es_url="http://localhost:9999")
        mock_es = AsyncMock()
        mock_es.index.side_effect = ConnectionError("Connection refused")

        mock_plugin = AsyncMock()
        mock_plugin.id = "dora-2025"
        mock_plugin.name = "DORA ICT Risk"
        mock_plugin.jurisdiction = "EU"
        mock_plugin.authority = "EBA"
        mock_plugin.rules = []

        with patch.object(client, "_client", mock_es):
            # Should not raise
            await client.index_regulation(mock_plugin)

    async def test_close_handles_errors(self) -> None:
        client = SearchClient()
        mock_es = AsyncMock()
        mock_es.close.side_effect = RuntimeError("close failed")
        client._client = mock_es

        # Should not raise
        await client.close()
        assert client._client is None
