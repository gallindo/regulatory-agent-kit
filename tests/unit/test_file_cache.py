"""Tests for file analysis cache — Lite Mode SQLite backend and high-level service."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from regulatory_agent_kit.database.lite import (
    LiteFileAnalysisCacheRepository,
    create_tables,
)
from regulatory_agent_kit.tools.file_cache import FileAnalysisCache
from regulatory_agent_kit.util.hashing import compute_cache_key

# ------------------------------------------------------------------
# LiteFileAnalysisCacheRepository (SQLite)
# ------------------------------------------------------------------


class TestLiteFileAnalysisCacheRepository:
    async def test_put_and_get(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        repo = LiteFileAnalysisCacheRepository(db)

        await repo.put(
            cache_key="abc123" + "0" * 58,
            repo_url="https://github.com/org/svc",
            file_path="src/Main.java",
            result={"matched_rules": [{"rule_id": "EX-001"}]},
            ttl_days=7,
        )

        row = await repo.get("abc123" + "0" * 58)
        assert row is not None
        assert row["repo_url"] == "https://github.com/org/svc"
        assert row["file_path"] == "src/Main.java"

    async def test_get_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        repo = LiteFileAnalysisCacheRepository(db)
        assert await repo.get("nonexistent" + "0" * 53) is None

    async def test_put_replaces_existing_entry(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        repo = LiteFileAnalysisCacheRepository(db)

        key = "k" * 64
        await repo.put(key, "url", "path", {"v": 1})
        await repo.put(key, "url", "path", {"v": 2})

        row = await repo.get(key)
        assert row is not None
        assert '"v": 2' in row["result"]

    async def test_delete_expired_removes_old_entries(self, tmp_path: Path) -> None:
        import aiosqlite

        db = tmp_path / "test.db"
        await create_tables(db)
        repo = LiteFileAnalysisCacheRepository(db)

        # Insert a valid entry with TTL 30
        await repo.put("valid00" + "0" * 57, "url", "path", {"new": True}, ttl_days=30)
        # Manually insert an expired entry with a past expires_at
        async with aiosqlite.connect(str(db)) as conn:
            await conn.execute(
                """
                INSERT INTO file_analysis_cache
                    (cache_key, repo_url, file_path, result, created_at, expires_at)
                VALUES (?, ?, ?, ?, datetime('now', '-2 days'), datetime('now', '-1 days'))
                """,
                ("expired" + "0" * 57, "url", "path", '{"old": true}'),
            )
            await conn.commit()

        deleted = await repo.delete_expired()
        assert deleted >= 1

        # Valid entry should still be there
        assert await repo.get("valid00" + "0" * 57) is not None

    async def test_delete_expired_returns_zero_when_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        repo = LiteFileAnalysisCacheRepository(db)
        assert await repo.delete_expired() == 0


# ------------------------------------------------------------------
# FileAnalysisCache (high-level service)
# ------------------------------------------------------------------


class TestFileAnalysisCache:
    async def test_store_and_lookup(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0")

        content = "public class Foo {}"
        result = {"matched_rules": [{"rule_id": "R-001", "severity": "high"}]}

        await cache.store(content, "https://repo", "Foo.java", result)
        cached = await cache.lookup(content, "https://repo", "Foo.java")

        assert cached is not None
        assert cached["matched_rules"][0]["rule_id"] == "R-001"

    async def test_lookup_miss_returns_none(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0")

        result = await cache.lookup("new content", "url", "file.py")
        assert result is None

    async def test_different_plugin_version_misses(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)

        cache_v1 = FileAnalysisCache(store, plugin_version="1.0.0")
        cache_v2 = FileAnalysisCache(store, plugin_version="2.0.0")

        content = "class Svc {}"
        await cache_v1.store(content, "url", "Svc.java", {"v": 1})

        # Same content but different plugin version => miss
        assert await cache_v2.lookup(content, "url", "Svc.java") is None

    async def test_different_content_misses(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0")

        await cache.store("content A", "url", "file.py", {"v": "a"})
        assert await cache.lookup("content B", "url", "file.py") is None

    async def test_hit_and_miss_counters(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0")

        content = "class X {}"
        await cache.store(content, "url", "X.java", {"ok": True})

        await cache.lookup(content, "url", "X.java")  # hit
        await cache.lookup("other", "url", "Y.java")  # miss

        assert cache.hits == 1
        assert cache.misses == 1
        assert cache.hit_rate == 0.5

    async def test_hit_rate_zero_when_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0")
        assert cache.hit_rate == 0.0

    async def test_clean_expired(self, tmp_path: Path) -> None:
        import aiosqlite

        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0")

        # Manually insert an already-expired entry
        async with aiosqlite.connect(str(db)) as conn:
            await conn.execute(
                """
                INSERT INTO file_analysis_cache
                    (cache_key, repo_url, file_path, result, created_at, expires_at)
                VALUES (?, ?, ?, ?, datetime('now', '-2 days'), datetime('now', '-1 days'))
                """,
                ("stale0" + "0" * 58, "url", "old.py", '{"stale": true}'),
            )
            await conn.commit()

        count = await cache.clean_expired()
        assert count >= 1

    async def test_custom_ttl(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        await create_tables(db)
        store = LiteFileAnalysisCacheRepository(db)
        cache = FileAnalysisCache(store, plugin_version="1.0.0", ttl_days=30)

        content = "class Long {}"
        await cache.store(content, "url", "Long.java", {"ok": True})
        # Should still be valid (30 day TTL)
        assert await cache.lookup(content, "url", "Long.java") is not None


# ------------------------------------------------------------------
# Cache key determinism
# ------------------------------------------------------------------


class TestCacheKeyDeterminism:
    def test_same_inputs_produce_same_key(self) -> None:
        k1 = compute_cache_key("content", "1.0", "0.1.0")
        k2 = compute_cache_key("content", "1.0", "0.1.0")
        assert k1 == k2

    def test_different_content_produces_different_key(self) -> None:
        k1 = compute_cache_key("content A", "1.0", "0.1.0")
        k2 = compute_cache_key("content B", "1.0", "0.1.0")
        assert k1 != k2

    def test_different_plugin_version_produces_different_key(self) -> None:
        k1 = compute_cache_key("content", "1.0", "0.1.0")
        k2 = compute_cache_key("content", "2.0", "0.1.0")
        assert k1 != k2

    def test_key_is_64_hex_chars(self) -> None:
        key = compute_cache_key("x", "v", "a")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)
