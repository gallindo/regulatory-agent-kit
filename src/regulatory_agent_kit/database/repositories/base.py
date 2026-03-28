"""Base repository with parameterized query helpers."""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection  # noqa: TC002
from psycopg.rows import dict_row


class BaseRepository:
    """Thin base class providing query helper methods using parameterized SQL."""

    def __init__(self, conn: AsyncConnection[Any]) -> None:
        self._conn = conn

    async def _fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Execute a query and return one row as a dict, or None."""
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            row = await cur.fetchone()
            return dict(row) if row else None

    async def _fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dicts."""
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def _execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        """Execute a query without returning results."""
        async with self._conn.cursor() as cur:
            await cur.execute(query, params)
