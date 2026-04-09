"""Tests for the plugin registry — models, API routes, and loader integration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from regulatory_agent_kit.api.main import app
from regulatory_agent_kit.api.routes.plugins import clear_registry, seed_plugin
from regulatory_agent_kit.models.registry import (
    PluginRegistryEntry,
    PluginSearchResult,
    PublishRequest,
    SearchQuery,
)
from regulatory_agent_kit.plugins.loader import PluginLoader

EXAMPLE_PLUGIN = Path(__file__).resolve().parents[2] / "regulations" / "examples" / "example.yaml"


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestRegistryModels:
    def test_plugin_registry_entry_validation(self) -> None:
        entry = PluginRegistryEntry(
            plugin_id="test-plugin",
            name="Test Plugin",
            latest_version="1.0.0",
            published_at=datetime.now(UTC),
        )
        assert entry.plugin_id == "test-plugin"
        assert entry.downloads == 0
        assert entry.tags == []

    def test_search_result_pagination(self) -> None:
        result = PluginSearchResult(entries=[], total=0, page=1, limit=20)
        assert result.total == 0

    def test_publish_request_requires_yaml(self) -> None:
        with pytest.raises(Exception):
            PublishRequest(yaml_content="")  # min_length=1

    def test_search_query_defaults(self) -> None:
        query = SearchQuery()
        assert query.page == 1
        assert query.limit == 20

    def test_search_query_limit_bounds(self) -> None:
        with pytest.raises(Exception):
            SearchQuery(limit=0)
        with pytest.raises(Exception):
            SearchQuery(limit=200)


# ---------------------------------------------------------------------------
# Loader integration
# ---------------------------------------------------------------------------


class TestLoaderFromString:
    def test_load_from_string(self) -> None:
        loader = PluginLoader()
        yaml_content = EXAMPLE_PLUGIN.read_text(encoding="utf-8")
        plugin = loader.load_from_string(yaml_content)
        assert plugin.id == "example-audit-logging-2025"
        assert len(plugin.rules) == 2

    def test_load_from_string_invalid_yaml(self) -> None:
        from regulatory_agent_kit.exceptions import PluginLoadError

        loader = PluginLoader()
        with pytest.raises(PluginLoadError):
            loader.load_from_string("not: [valid: yaml: {{")

    def test_load_from_string_invalid_schema(self) -> None:
        from regulatory_agent_kit.exceptions import PluginValidationError

        loader = PluginLoader()
        with pytest.raises(PluginValidationError):
            loader.load_from_string("id: test\nname: test\n")


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_in_memory_registry():
    """Clear in-memory registry before each test."""
    clear_registry()
    yield
    clear_registry()


class TestPluginRegistryAPI:
    @pytest.fixture
    def sample_entry(self) -> dict:
        return {
            "plugin_id": "test-regulation-2025",
            "name": "Test Regulation",
            "latest_version": "1.0.0",
            "jurisdiction": "EU",
            "authority": "Test Authority",
            "description": "A test regulation plugin.",
            "author": "tester",
            "published_at": datetime.now(UTC),
            "downloads": 0,
            "tags": ["test", "eu"],
            "certification_tier": "technically_valid",
            "metadata": {},
        }

    async def test_search_empty_registry(self) -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/plugins")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["entries"] == []

    async def test_search_with_seeded_plugin(self, sample_entry: dict) -> None:
        seed_plugin(sample_entry)
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/plugins", params={"q": "test"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["entries"][0]["plugin_id"] == "test-regulation-2025"

    async def test_get_plugin(self, sample_entry: dict) -> None:
        seed_plugin(sample_entry)
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/plugins/test-regulation-2025")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Regulation"

    async def test_get_plugin_not_found(self) -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/plugins/nonexistent")
        assert response.status_code == 404

    async def test_publish_valid_plugin(self) -> None:
        yaml_content = EXAMPLE_PLUGIN.read_text(encoding="utf-8")
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/plugins",
                json={
                    "yaml_content": yaml_content,
                    "author": "test-author",
                    "tags": ["example"],
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["plugin_id"] == "example-audit-logging-2025"
        assert data["author"] == "test-author"

    async def test_publish_invalid_yaml(self) -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/plugins",
                json={"yaml_content": "not valid: {{", "author": "", "tags": []},
            )
        assert response.status_code == 422

    async def test_search_by_jurisdiction(self, sample_entry: dict) -> None:
        seed_plugin(sample_entry)
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/plugins", params={"jurisdiction": "EU"}
            )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_list_versions_empty(self) -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/plugins/nonexistent/versions")
        assert response.status_code == 200
        assert response.json() == []
