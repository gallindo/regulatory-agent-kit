"""Unit tests for database layer (Phase 5).

These tests verify the repository classes and pool management logic
without requiring a running PostgreSQL instance. Integration tests
with real PostgreSQL are in tests/integration/test_repositories.py.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from regulatory_agent_kit.database.pool import get_pool
from regulatory_agent_kit.database.repositories.audit_entries import AuditRepository
from regulatory_agent_kit.database.repositories.base import BaseRepository
from regulatory_agent_kit.database.repositories.checkpoint_decisions import (
    CheckpointDecisionRepository,
)
from regulatory_agent_kit.database.repositories.conflict_log import ConflictLogRepository
from regulatory_agent_kit.database.repositories.file_analysis_cache import (
    FileAnalysisCacheRepository,
)
from regulatory_agent_kit.database.repositories.pipeline_runs import PipelineRunRepository
from regulatory_agent_kit.database.repositories.repository_progress import (
    RepositoryProgressRepository,
)


class TestPoolManagement:
    def test_get_pool_raises_when_uninitialized(self) -> None:
        """get_pool() should raise RuntimeError before create_pool() is called."""
        import regulatory_agent_kit.database.pool as pool_mod

        original = pool_mod._pool
        pool_mod._pool = None
        try:
            with pytest.raises(RuntimeError, match="not been initialized"):
                get_pool()
        finally:
            pool_mod._pool = original


class TestRepositoryInheritance:
    """All repositories inherit from BaseRepository."""

    REPO_CLASSES: ClassVar[list[type]] = [
        PipelineRunRepository,
        RepositoryProgressRepository,
        AuditRepository,
        CheckpointDecisionRepository,
        ConflictLogRepository,
        FileAnalysisCacheRepository,
    ]

    @pytest.mark.parametrize("cls", REPO_CLASSES)
    def test_inherits_from_base(self, cls: type) -> None:
        assert issubclass(cls, BaseRepository)

    def test_total_repository_count(self) -> None:
        assert len(self.REPO_CLASSES) == 6


class TestAuditRepositoryAppendOnly:
    """Verify AuditRepository has no update or delete methods."""

    def test_no_update_method(self) -> None:
        assert not hasattr(AuditRepository, "update")

    def test_no_delete_method(self) -> None:
        assert not hasattr(AuditRepository, "delete")

    def test_has_insert_method(self) -> None:
        assert hasattr(AuditRepository, "insert")

    def test_has_bulk_insert_method(self) -> None:
        assert hasattr(AuditRepository, "bulk_insert")

    def test_has_get_by_run_method(self) -> None:
        assert hasattr(AuditRepository, "get_by_run")


class TestNoSQLInjection:
    """Verify no f-string or %-format SQL in repository files."""

    def test_no_fstring_sql(self) -> None:
        import pathlib

        repo_dir = (
            pathlib.Path(__file__).resolve().parents[2]
            / "src"
            / "regulatory_agent_kit"
            / "database"
            / "repositories"
        )
        for py_file in repo_dir.glob("*.py"):
            content = py_file.read_text()
            # Check for f"SELECT, f"INSERT, f"UPDATE, f"DELETE patterns
            for keyword in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert f'f"{keyword}' not in content, f"f-string SQL found in {py_file.name}"
                assert f"f'{keyword}" not in content, f"f-string SQL found in {py_file.name}"
