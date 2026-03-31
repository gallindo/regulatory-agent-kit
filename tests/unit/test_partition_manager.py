"""Tests for the audit_entries partition manager."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from regulatory_agent_kit.database.partition_manager import (
    PartitionInfo,
    PartitionManager,
    _row_to_dict,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Pure logic tests (no database)
# ---------------------------------------------------------------------------


class TestPartitionName:
    """Tests for partition_name()."""

    def test_standard_month(self) -> None:
        pm = PartitionManager()
        assert pm.partition_name(2025, 3) == "audit_entries_y2025m03"

    def test_december(self) -> None:
        pm = PartitionManager()
        assert pm.partition_name(2025, 12) == "audit_entries_y2025m12"

    def test_january(self) -> None:
        pm = PartitionManager()
        assert pm.partition_name(2026, 1) == "audit_entries_y2026m01"

    def test_custom_table(self) -> None:
        pm = PartitionManager(table="custom_log")
        assert pm.partition_name(2025, 6) == "custom_log_y2025m06"


class TestMonthRange:
    """Tests for month_range()."""

    def test_mid_year(self) -> None:
        pm = PartitionManager()
        start, end = pm.month_range(2025, 6)
        assert start == "2025-06-01"
        assert end == "2025-07-01"

    def test_december_wraps_year(self) -> None:
        pm = PartitionManager()
        start, end = pm.month_range(2025, 12)
        assert start == "2025-12-01"
        assert end == "2026-01-01"

    def test_january(self) -> None:
        pm = PartitionManager()
        start, end = pm.month_range(2026, 1)
        assert start == "2026-01-01"
        assert end == "2026-02-01"


class TestParseBoundExpr:
    """Tests for parse_bound_expr()."""

    def test_standard_format(self) -> None:
        pm = PartitionManager()
        expr = "FOR VALUES FROM ('2025-01-01') TO ('2025-02-01')"
        start, end = pm.parse_bound_expr(expr)
        assert start == date(2025, 1, 1)
        assert end == date(2025, 2, 1)

    def test_december_boundary(self) -> None:
        pm = PartitionManager()
        expr = "FOR VALUES FROM ('2025-12-01') TO ('2026-01-01')"
        start, end = pm.parse_bound_expr(expr)
        assert start == date(2025, 12, 1)
        assert end == date(2026, 1, 1)

    def test_invalid_expression_raises(self) -> None:
        pm = PartitionManager()
        with pytest.raises(ValueError, match="Cannot parse"):
            pm.parse_bound_expr("GARBAGE")

    def test_single_date_raises(self) -> None:
        pm = PartitionManager()
        with pytest.raises(ValueError, match="Cannot parse"):
            pm.parse_bound_expr("FOR VALUES FROM ('2025-01-01')")


class TestComputeFutureMonths:
    """Tests for compute_future_months()."""

    def test_default_three_ahead(self) -> None:
        pm = PartitionManager(months_ahead=3)
        months = pm.compute_future_months(date(2025, 10, 15))
        assert months == [
            (2025, 10),
            (2025, 11),
            (2025, 12),
            (2026, 1),
        ]

    def test_zero_ahead(self) -> None:
        pm = PartitionManager(months_ahead=0)
        months = pm.compute_future_months(date(2025, 6, 1))
        assert months == [(2025, 6)]

    def test_wraps_across_year_boundary(self) -> None:
        pm = PartitionManager(months_ahead=5)
        months = pm.compute_future_months(date(2025, 11, 1))
        assert months == [
            (2025, 11),
            (2025, 12),
            (2026, 1),
            (2026, 2),
            (2026, 3),
            (2026, 4),
        ]

    def test_january_reference(self) -> None:
        pm = PartitionManager(months_ahead=2)
        months = pm.compute_future_months(date(2026, 1, 1))
        assert months == [(2026, 1), (2026, 2), (2026, 3)]


class TestComputeCutoffDate:
    """Tests for compute_cutoff_date()."""

    def test_standard_cutoff(self) -> None:
        pm = PartitionManager(retention_months=12)
        cutoff = pm.compute_cutoff_date(date(2026, 3, 15))
        assert cutoff == date(2025, 3, 1)

    def test_cutoff_wraps_year(self) -> None:
        pm = PartitionManager(retention_months=6)
        cutoff = pm.compute_cutoff_date(date(2025, 3, 1))
        assert cutoff == date(2024, 9, 1)

    def test_short_retention(self) -> None:
        pm = PartitionManager(retention_months=1)
        cutoff = pm.compute_cutoff_date(date(2025, 1, 1))
        assert cutoff == date(2024, 12, 1)

    def test_long_retention(self) -> None:
        pm = PartitionManager(retention_months=24)
        cutoff = pm.compute_cutoff_date(date(2026, 6, 1))
        assert cutoff == date(2024, 6, 1)


class TestRowToDict:
    """Tests for the _row_to_dict helper."""

    def test_with_datetime_timestamp(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0)
        row = ("id1", "run1", "analysis_complete", ts, {"key": "val"}, "sig123")
        result = _row_to_dict(row)
        assert result["entry_id"] == "id1"
        assert result["run_id"] == "run1"
        assert result["event_type"] == "analysis_complete"
        assert result["timestamp"] == "2025-06-15T12:00:00"
        assert result["payload"] == {"key": "val"}
        assert result["signature"] == "sig123"

    def test_with_string_timestamp(self) -> None:
        row = ("id1", "run1", "evt", "2025-06-15", '{"a": 1}', "sig")
        result = _row_to_dict(row)
        assert result["timestamp"] == "2025-06-15"
        assert result["payload"] == {"a": 1}

    def test_null_payload_and_signature(self) -> None:
        row = ("id1", "run1", "evt", "ts", None, None)
        result = _row_to_dict(row)
        assert result["payload"] == {}
        assert result["signature"] == ""


# ---------------------------------------------------------------------------
# Async method tests with mock pool
# ---------------------------------------------------------------------------


def _make_mock_pool() -> tuple[MagicMock, MagicMock, AsyncMock]:
    """Build a mock AsyncConnectionPool with nested async context managers.

    ``pool.connection()`` is a synchronous call that returns an async
    context manager (matching psycopg_pool's API).  ``conn.cursor()``
    follows the same pattern.  The cursor itself is an ``AsyncMock``
    so that ``await cur.execute(...)`` works naturally.
    """
    pool = MagicMock()
    conn = MagicMock()
    cur = AsyncMock()

    # pool.connection() -> sync call returning async context manager -> conn
    conn_ctx = AsyncMock()
    conn_ctx.__aenter__ = AsyncMock(return_value=conn)
    conn_ctx.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = conn_ctx

    # conn.cursor() -> sync call returning async context manager -> cur
    cur_ctx = AsyncMock()
    cur_ctx.__aenter__ = AsyncMock(return_value=cur)
    cur_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.cursor.return_value = cur_ctx

    # conn.commit() must be awaitable
    conn.commit = AsyncMock()

    return pool, conn, cur


class TestListPartitions:
    """Tests for list_partitions()."""

    async def test_returns_parsed_partitions(self) -> None:
        pool, _conn, cur = _make_mock_pool()
        cur.fetchall.side_effect = [
            # First call: partition list query
            [
                ("audit_entries_y2025m01", "FOR VALUES FROM ('2025-01-01') TO ('2025-02-01')"),
                ("audit_entries_y2025m02", "FOR VALUES FROM ('2025-02-01') TO ('2025-03-01')"),
            ],
            # Second call: count for first partition (won't be used directly,
            # fetchone handles counts)
        ]
        cur.fetchone.side_effect = [(42,), (17,)]

        pm = PartitionManager()
        result = await pm.list_partitions(pool)

        assert len(result) == 2
        assert result[0].name == "audit_entries_y2025m01"
        assert result[0].start_date == date(2025, 1, 1)
        assert result[0].end_date == date(2025, 2, 1)
        assert result[0].row_count == 42
        assert result[1].row_count == 17

    async def test_empty_table(self) -> None:
        pool, _conn, cur = _make_mock_pool()
        cur.fetchall.return_value = []

        pm = PartitionManager()
        result = await pm.list_partitions(pool)

        assert result == []


class TestCreatePartition:
    """Tests for create_partition()."""

    async def test_creates_new_partition(self) -> None:
        pool, conn, cur = _make_mock_pool()
        # check query returns None (partition does not exist)
        cur.fetchone.return_value = None

        pm = PartitionManager()
        created = await pm.create_partition(pool, 2025, 6)

        assert created is True
        # Should have executed check + create + commit
        assert cur.execute.call_count == 2
        conn.commit.assert_awaited_once()

    async def test_skips_existing_partition(self) -> None:
        pool, conn, cur = _make_mock_pool()
        # check query returns a row (partition exists)
        cur.fetchone.return_value = (1,)

        pm = PartitionManager()
        created = await pm.create_partition(pool, 2025, 6)

        assert created is False
        # Only the check query should have been executed
        assert cur.execute.call_count == 1
        conn.commit.assert_not_awaited()


class TestEnsureFuturePartitions:
    """Tests for ensure_future_partitions()."""

    async def test_creates_missing_partitions(self) -> None:
        pool, _conn, cur = _make_mock_pool()
        # All partitions are new (check returns None each time)
        cur.fetchone.return_value = None

        pm = PartitionManager(months_ahead=2)
        created = await pm.ensure_future_partitions(pool, date(2025, 11, 1))

        assert len(created) == 3
        assert "audit_entries_y2025m11" in created
        assert "audit_entries_y2025m12" in created
        assert "audit_entries_y2026m01" in created

    async def test_skips_all_existing(self) -> None:
        pool, _conn, cur = _make_mock_pool()
        # All partitions exist
        cur.fetchone.return_value = (1,)

        pm = PartitionManager(months_ahead=2)
        created = await pm.ensure_future_partitions(pool, date(2025, 6, 1))

        assert created == []


class TestArchivePartition:
    """Tests for archive_partition()."""

    async def test_no_archive_dir_returns_none(self) -> None:
        pool, _, _ = _make_mock_pool()
        pm = PartitionManager(archive_dir=None)
        partition = PartitionInfo(
            name="audit_entries_y2024m01",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
        )
        result = await pm.archive_partition(pool, partition)
        assert result is None

    async def test_exports_and_detaches(self, tmp_path: Path) -> None:
        pool, conn, cur = _make_mock_pool()

        ts = datetime(2024, 1, 15, 10, 30, 0)
        cur.fetchall.return_value = [
            ("eid1", "rid1", "scan_start", ts, {"k": "v"}, "sig1"),
        ]

        pm = PartitionManager(archive_dir=tmp_path / "archives")
        partition = PartitionInfo(
            name="audit_entries_y2024m01",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
        )

        result = await pm.archive_partition(pool, partition)

        assert result is not None
        assert result.exists()
        assert result.name == "audit_entries_y2024m01.jsonl"

        lines = result.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["entry_id"] == "eid1"
        assert entry["payload"] == {"k": "v"}

        # Verify detach was called
        detach_calls = [
            call for call in cur.execute.await_args_list if "DETACH PARTITION" in str(call)
        ]
        assert len(detach_calls) == 1
        conn.commit.assert_awaited_once()


class TestRotate:
    """Tests for the full rotate() method."""

    async def test_rotate_creates_and_archives(self, tmp_path: Path) -> None:
        pm = PartitionManager(
            months_ahead=1,
            retention_months=12,
            archive_dir=tmp_path / "archives",
        )

        # We'll mock the sub-methods to test orchestration
        created_names = ["audit_entries_y2026m03", "audit_entries_y2026m04"]
        pm.ensure_future_partitions = AsyncMock(return_value=created_names)

        old_partition = PartitionInfo(
            name="audit_entries_y2024m06",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 7, 1),
            row_count=100,
        )
        recent_partition = PartitionInfo(
            name="audit_entries_y2025m12",
            start_date=date(2025, 12, 1),
            end_date=date(2026, 1, 1),
            row_count=50,
        )
        pm.list_partitions = AsyncMock(
            return_value=[old_partition, recent_partition],
        )
        pm.archive_partition = AsyncMock(
            return_value=tmp_path / "archives" / "audit_entries_y2024m06.jsonl",
        )

        pool = AsyncMock()
        result = await pm.rotate(pool)

        assert result["partitions_created"] == created_names
        assert "audit_entries_y2024m06" in result["partitions_archived"]
        # Recent partition should NOT be archived
        pm.archive_partition.assert_awaited_once_with(pool, old_partition)
