"""Tests for cache key hashing (Phase 4)."""

from __future__ import annotations

from regulatory_agent_kit.util.hashing import compute_cache_key


class TestComputeCacheKey:
    def test_returns_64_char_hex(self) -> None:
        result = compute_cache_key("content", "1.0.0", "0.1.0")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        a = compute_cache_key("same", "1.0", "1.0")
        b = compute_cache_key("same", "1.0", "1.0")
        assert a == b

    def test_content_sensitive(self) -> None:
        a = compute_cache_key("content_a", "1.0", "1.0")
        b = compute_cache_key("content_b", "1.0", "1.0")
        assert a != b

    def test_plugin_version_sensitive(self) -> None:
        a = compute_cache_key("same", "1.0", "1.0")
        b = compute_cache_key("same", "2.0", "1.0")
        assert a != b

    def test_agent_version_sensitive(self) -> None:
        a = compute_cache_key("same", "1.0", "1.0")
        b = compute_cache_key("same", "1.0", "2.0")
        assert a != b
