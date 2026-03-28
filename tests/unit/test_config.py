"""Tests for application configuration."""

from regulatory_agent_kit.config import Settings


def test_default_settings() -> None:
    """Settings should load with sensible defaults."""
    settings = Settings()
    assert settings.rak_cache_ttl_days == 7
    assert settings.rak_log_level == "INFO"
