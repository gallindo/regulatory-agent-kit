"""Shared pytest fixtures for regulatory-agent-kit tests."""

import pytest


@pytest.fixture
def sample_regulation_path() -> str:
    """Path to the sample example regulation plugin."""
    return "regulations/examples/example.yaml"
