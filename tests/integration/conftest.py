"""Shared fixtures for integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests.helpers import EXAMPLE_PLUGIN_PATH, SAMPLE_JAVA


@pytest.fixture
def example_plugin_path() -> Path:
    """Path to the example regulation plugin YAML."""
    return EXAMPLE_PLUGIN_PATH


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """Create a minimal fixture repository with a Java source file."""
    repo_dir = tmp_path / "fixture-repo"
    repo_dir.mkdir()
    src_dir = repo_dir / "src" / "main" / "java" / "com" / "example" / "service"
    src_dir.mkdir(parents=True)
    (src_dir / "PaymentService.java").write_text(SAMPLE_JAVA)
    return repo_dir


@pytest.fixture
def lite_db(tmp_path: Path) -> Path:
    """Return a temporary SQLite database path."""
    return tmp_path / "e2e_test.db"
