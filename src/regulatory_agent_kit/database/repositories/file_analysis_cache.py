"""Repository for rak.file_analysis_cache table."""

from __future__ import annotations

from typing import Any

from regulatory_agent_kit.database.repositories.base import BaseRepository


class FileAnalysisCacheRepository(BaseRepository):
    """CRUD operations for file_analysis_cache."""

    async def get(self, cache_key: str) -> dict[str, Any] | None:
        """Get a cached analysis result by key."""
        return await self._fetch_one(
            """
            SELECT * FROM rak.file_analysis_cache
            WHERE cache_key = %s AND expires_at > now()
            """,
            (cache_key,),
        )

    async def put(
        self,
        cache_key: str,
        repo_url: str,
        file_path: str,
        result: dict[str, Any],
        ttl_days: int = 7,
    ) -> None:
        """Insert or update a cache entry with TTL-based expiration."""
        await self._execute(
            """
            INSERT INTO rak.file_analysis_cache
                (cache_key, repo_url, file_path, result, expires_at)
            VALUES (%s, %s, %s, %s, now() + make_interval(days => %s))
            ON CONFLICT (cache_key) DO UPDATE SET
                result = EXCLUDED.result,
                expires_at = EXCLUDED.expires_at
            """,
            (cache_key, repo_url, file_path, result, ttl_days),
        )

    async def delete_expired(self) -> int:
        """Delete expired cache entries, returning the count removed."""
        row = await self._fetch_one(
            """
            WITH deleted AS (
                DELETE FROM rak.file_analysis_cache
                WHERE expires_at < now()
                RETURNING 1
            )
            SELECT count(*)::int AS deleted_count FROM deleted
            """
        )
        return row["deleted_count"] if row else 0
