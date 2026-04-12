"""Automated partition management for audit_entries table.

Provides application-level partition rotation: creates future monthly
partitions ahead of time and archives old ones by exporting to JSONL
then detaching from the parent table.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class PartitionInfo:
    """Metadata about a table partition."""

    name: str
    start_date: date
    end_date: date
    row_count: int = 0


@dataclass
class PartitionManager:
    """Manages time-based partitioning for audit_entries.

    Creates monthly partitions ahead of time and archives old ones.
    Works with PostgreSQL range partitioning by timestamp.
    """

    schema: str = "rak"
    table: str = "audit_entries"
    months_ahead: int = 3
    retention_months: int = 12
    archive_dir: Path | None = None

    def partition_name(self, year: int, month: int) -> str:
        """Generate partition table name for a given year and month."""
        return f"{self.table}_y{year}m{month:02d}"

    def month_range(self, year: int, month: int) -> tuple[str, str]:
        """Return (start, end) ISO date strings for a monthly partition.

        Args:
            year: Partition year.
            month: Partition month (1-12).

        Returns:
            Tuple of (start_date, end_date) as ISO-format strings where
            end_date is the first day of the following month.
        """
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return start.isoformat(), end.isoformat()

    def parse_bound_expr(self, expr: str) -> tuple[date, date]:
        """Parse a PostgreSQL partition bound expression into dates.

        Args:
            expr: Bound expression like
                  ``FOR VALUES FROM ('2025-01-01') TO ('2025-02-01')``.

        Returns:
            Tuple of (start_date, end_date).

        Raises:
            ValueError: If the expression does not contain two dates.
        """
        matches = re.findall(r"'(\d{4}-\d{2}-\d{2})'", expr)
        if len(matches) < 2:
            msg = f"Cannot parse partition bound expression: {expr}"
            raise ValueError(msg)
        return date.fromisoformat(matches[0]), date.fromisoformat(matches[1])

    def compute_future_months(
        self,
        reference_date: date | None = None,
    ) -> list[tuple[int, int]]:
        """Return (year, month) pairs for current month + months_ahead.

        Args:
            reference_date: Date to compute from; defaults to today.

        Returns:
            List of (year, month) tuples covering the window.
        """
        ref = reference_date or date.today()
        base = ref.year * 12 + (ref.month - 1)
        result: list[tuple[int, int]] = []
        for offset in range(self.months_ahead + 1):
            year, month_idx = divmod(base + offset, 12)
            result.append((year, month_idx + 1))
        return result

    def compute_cutoff_date(
        self,
        reference_date: date | None = None,
    ) -> date:
        """Compute the retention cutoff date.

        Partitions whose ``end_date`` is on or before this date are
        eligible for archival.

        Args:
            reference_date: Date to compute from; defaults to today.

        Returns:
            The cutoff date.
        """
        ref = reference_date or date.today()
        cutoff_year = ref.year
        cutoff_month = ref.month - self.retention_months
        while cutoff_month <= 0:
            cutoff_month += 12
            cutoff_year -= 1
        return date(cutoff_year, cutoff_month, 1)

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------

    async def list_partitions(
        self,
        pool: AsyncConnectionPool,
    ) -> list[PartitionInfo]:
        """List existing partitions for the audit table.

        Args:
            pool: Psycopg 3 async connection pool.

        Returns:
            Sorted list of ``PartitionInfo`` for each child partition.
        """
        query = """
            SELECT
                c.relname AS name,
                pg_catalog.pg_get_expr(c.relpartbound, c.oid) AS bound_expr
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_inherits i ON c.oid = i.inhrelid
            JOIN pg_catalog.pg_class p ON i.inhparent = p.oid
            JOIN pg_catalog.pg_namespace n ON p.relnamespace = n.oid
            WHERE n.nspname = %s AND p.relname = %s
            ORDER BY c.relname;
        """
        partitions: list[PartitionInfo] = []
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(query, (self.schema, self.table))
            rows = await cur.fetchall()
            for row in rows:
                name: str = row[0]
                bound: str = row[1]
                start_date, end_date = self.parse_bound_expr(bound)
                count_query = f"SELECT count(*) FROM {self.schema}.{name}"  # noqa: S608
                await cur.execute(count_query)
                count_row = await cur.fetchone()
                count = count_row[0] if count_row else 0
                partitions.append(
                    PartitionInfo(
                        name=name,
                        start_date=start_date,
                        end_date=end_date,
                        row_count=count,
                    )
                )
        return partitions

    async def create_partition(
        self,
        pool: AsyncConnectionPool,
        year: int,
        month: int,
    ) -> bool:
        """Create a partition for the given month if it does not exist.

        Args:
            pool: Psycopg 3 async connection pool.
            year: Partition year.
            month: Partition month (1-12).

        Returns:
            ``True`` if the partition was created, ``False`` if it
            already existed.
        """
        name = self.partition_name(year, month)
        start_str, end_str = self.month_range(year, month)

        check_query = """
            SELECT 1 FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = %s AND c.relname = %s;
        """
        create_ddl = (
            f"CREATE TABLE IF NOT EXISTS {self.schema}.{name} "
            f"PARTITION OF {self.schema}.{self.table} "
            f"FOR VALUES FROM ('{start_str}') TO ('{end_str}');"
        )

        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(check_query, (self.schema, name))
            if await cur.fetchone():
                logger.debug("Partition %s already exists", name)
                return False
            await cur.execute(create_ddl)
            await conn.commit()
            logger.info(
                "Created partition %s (%s to %s)",
                name,
                start_str,
                end_str,
            )
            return True

    async def ensure_future_partitions(
        self,
        pool: AsyncConnectionPool,
        reference_date: date | None = None,
    ) -> list[str]:
        """Create partitions for the current month plus ``months_ahead``.

        Args:
            pool: Psycopg 3 async connection pool.
            reference_date: Date to compute from; defaults to today.

        Returns:
            Names of newly created partitions.
        """
        created: list[str] = []
        for year, month in self.compute_future_months(reference_date):
            name = self.partition_name(year, month)
            if await self.create_partition(pool, year, month):
                created.append(name)
        return created

    async def archive_partition(
        self,
        pool: AsyncConnectionPool,
        partition: PartitionInfo,
    ) -> Path | None:
        """Export partition data to JSONL and detach it from the parent.

        Args:
            pool: Psycopg 3 async connection pool.
            partition: The partition to archive.

        Returns:
            Path to the JSONL archive file, or ``None`` if no
            ``archive_dir`` is configured.
        """
        if not self.archive_dir:
            logger.warning("No archive_dir configured, skipping archive")
            return None

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = self.archive_dir / f"{partition.name}.jsonl"

        async with pool.connection() as conn, conn.cursor() as cur:
            cols = "entry_id, run_id, event_type, timestamp, payload, signature"
            tbl = f"{self.schema}.{partition.name}"
            select_query = f"SELECT {cols} FROM {tbl} ORDER BY timestamp"  # noqa: S608
            await cur.execute(select_query)
            rows = await cur.fetchall()

            with archive_path.open("w") as f:
                for row in rows:
                    entry = _row_to_dict(row)
                    f.write(json.dumps(entry) + "\n")

            await cur.execute(
                f"ALTER TABLE {self.schema}.{self.table} "
                f"DETACH PARTITION {self.schema}.{partition.name};"
            )
            await conn.commit()
            logger.info(
                "Archived %d rows from %s to %s",
                len(rows),
                partition.name,
                archive_path,
            )

        return archive_path

    async def rotate(
        self,
        pool: AsyncConnectionPool,
    ) -> dict[str, Any]:
        """Run full rotation: create future partitions, archive old ones.

        Args:
            pool: Psycopg 3 async connection pool.

        Returns:
            Summary dict with ``partitions_created``,
            ``partitions_archived``, and ``reference_date``.
        """
        today = date.today()

        created = await self.ensure_future_partitions(pool, today)

        archived: list[str] = []
        cutoff = self.compute_cutoff_date(today)

        partitions = await self.list_partitions(pool)
        for part in partitions:
            if part.end_date <= cutoff:
                result = await self.archive_partition(pool, part)
                if result:
                    archived.append(part.name)

        return {
            "partitions_created": created,
            "partitions_archived": archived,
            "reference_date": today.isoformat(),
        }


def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a raw audit_entries row tuple to a serialisable dict."""
    return {
        "entry_id": str(row[0]),
        "run_id": str(row[1]),
        "event_type": row[2],
        "timestamp": (row[3].isoformat() if isinstance(row[3], datetime) else str(row[3])),
        "payload": (row[4] if isinstance(row[4], dict) else json.loads(row[4]) if row[4] else {}),
        "signature": row[5] or "",
    }
