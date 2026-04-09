"""Pydantic v2 models for the plugin registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PluginVersion(BaseModel):
    """A single published version of a regulation plugin."""

    version: str
    changelog: str = ""
    yaml_hash: str = Field(..., min_length=64, max_length=64)
    published_at: datetime


class PluginRegistryEntry(BaseModel):
    """Metadata for a published regulation plugin in the registry."""

    plugin_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    latest_version: str
    jurisdiction: str = ""
    authority: str = ""
    description: str = ""
    author: str = ""
    published_at: datetime
    downloads: int = 0
    tags: list[str] = Field(default_factory=list)
    certification_tier: str = "technically_valid"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PluginSearchResult(BaseModel):
    """Paginated search result from the plugin registry."""

    entries: list[PluginRegistryEntry]
    total: int
    page: int = 1
    limit: int = 20


class PublishRequest(BaseModel):
    """Request payload for publishing a plugin to the registry."""

    yaml_content: str = Field(..., min_length=1)
    author: str = ""
    tags: list[str] = Field(default_factory=list)


class SearchQuery(BaseModel):
    """Query parameters for searching the registry."""

    query: str = ""
    jurisdiction: str | None = None
    tags: list[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
