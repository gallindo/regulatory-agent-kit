"""Shared pytest fixtures for regulatory-agent-kit tests."""

import pytest


@pytest.fixture
def sample_regulation_path() -> str:
    """Path to the sample DORA regulation plugin."""
    return "regulations/dora/dora-ict-risk-2025.yaml"
